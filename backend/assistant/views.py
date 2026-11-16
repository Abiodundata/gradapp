from django.conf import settings
from django.db.models import Count
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import StudentProfile
from programs.serializers import GraduateProgramSerializer

from . import llm
from .models import ChatMessage, Conversation
from .qa import answer_question
from .recommendations import profile_is_empty, recommend
from .serializers import (
    AskSerializer,
    ChatMessageSerializer,
    ConversationDetailSerializer,
    ConversationSerializer,
    SendMessageSerializer,
)


class AIStatusView(APIView):
    def get(self, request):
        return Response({
            "ai_enabled": llm.is_configured(),
            "web_search_enabled": llm.is_configured() and settings.AI_WEB_SEARCH_ENABLED,
        })


class RecommendationsView(APIView):
    """Get Personalized Recommendations use case."""

    def get(self, request):
        profile, _ = StudentProfile.objects.get_or_create(user=request.user)
        try:
            limit = max(1, min(int(request.query_params.get("limit", 10)), 50))
        except ValueError:
            limit = 10
        recommendations = recommend(profile, limit=limit)

        results = []
        for rec in recommendations:
            program_data = GraduateProgramSerializer(rec.program, context={"request": request}).data
            results.append({
                "program": program_data,
                "score": rec.score,
                "breakdown": rec.breakdown,
                "reasons": rec.reasons,
                "cautions": rec.cautions,
                "matched_faculty": rec.matched_faculty,
            })

        summary = None
        if request.query_params.get("explain", "").lower() in {"true", "1"} and recommendations:
            summary = self._summarize(profile, results[:3])

        return Response({
            "profile_complete": not profile_is_empty(profile),
            "ai_enabled": llm.is_configured(),
            "summary": summary,
            "results": results,
        })

    @staticmethod
    def _summarize(profile, top):
        lines = [
            f"- {item['program']['name']} at {item['program']['university']['name']} (fit {item['score']}/100). "
            f"Reasons: {' '.join(item['reasons'])} Cautions: {' '.join(item['cautions']) or 'none'}"
            for item in top
        ]
        return llm.complete(
            system=(
                "You explain graduate-program recommendations to a student in 3-4 friendly sentences. "
                "Use only the facts given. Describe fit, never admission chances. No headings or lists."
            ),
            messages=[{
                "role": "user",
                "content": f"Student interests: {profile.academic_interests} {profile.research_interests}\n"
                           f"Top matches:\n" + "\n".join(lines),
            }],
            max_tokens=300,
        )


class AskView(APIView):
    """Ask AI Questions use case."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"

    def post(self, request):
        serializer = AskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        profile = None
        if data["use_profile"]:
            profile, _ = StudentProfile.objects.get_or_create(user=request.user)
        result = answer_question(
            data["question"], profile=profile, history=data.get("history"), search_web=data["search_web"]
        )
        return Response(result, status=status.HTTP_200_OK)


class ConversationViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Saved Ask AI conversations: start a new chat, continue, rename or delete one."""

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return (
            Conversation.objects.filter(user=self.request.user)
            .annotate(message_count=Count("messages"))
            .order_by("-updated_at")
        )

    def get_serializer_class(self):
        return ConversationDetailSerializer if self.action == "retrieve" else ConversationSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"], throttle_classes=[ScopedRateThrottle])
    def messages(self, request, pk=None):
        """Ask a question in this conversation. Both turns are saved."""
        conversation = self.get_object()
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        history = [
            {"role": message.role, "content": message.content}
            for message in conversation.messages.order_by("-created_at", "-id")[:6]
        ][::-1]
        profile = None
        if data["use_profile"]:
            profile, _ = StudentProfile.objects.get_or_create(user=request.user)
        result = answer_question(data["question"], profile=profile, history=history, search_web=data["search_web"])

        user_message = ChatMessage.objects.create(
            conversation=conversation, role=ChatMessage.Role.USER, content=data["question"]
        )
        assistant_message = ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.Role.ASSISTANT,
            content=result["answer"],
            sources=result["sources"],
            ai_powered=result["ai_powered"],
            web_searched=result.get("web_searched", False),
        )
        if conversation.title == "New conversation" or not conversation.title:
            conversation.title = data["question"][:80] + ("…" if len(data["question"]) > 80 else "")
        conversation.save()  # bumps updated_at so recent chats sort first

        return Response(
            {
                "conversation": ConversationSerializer(
                    self.get_queryset().get(pk=conversation.pk), context={"request": request}
                ).data,
                "messages": ChatMessageSerializer([user_message, assistant_message], many=True).data,
                "saved": result.get("saved", []),
            },
            status=status.HTTP_201_CREATED,
        )

    def get_throttles(self):
        if self.action == "messages":
            self.throttle_scope = "ai"
        return super().get_throttles()

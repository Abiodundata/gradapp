from rest_framework import serializers

from .models import ChatMessage, Conversation


class AskSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=1000, trim_whitespace=True)
    use_profile = serializers.BooleanField(default=True)
    search_web = serializers.BooleanField(default=False)
    history = serializers.ListField(child=serializers.DictField(), required=False, default=list, max_length=20)


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ("id", "role", "content", "sources", "ai_powered", "web_searched", "created_at")
        read_only_fields = fields


class ConversationSerializer(serializers.ModelSerializer):
    message_count = serializers.IntegerField(read_only=True, default=0)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ("id", "title", "created_at", "updated_at", "message_count", "last_message")
        read_only_fields = ("id", "created_at", "updated_at", "message_count", "last_message")

    def get_last_message(self, obj):
        last = obj.messages.order_by("-created_at", "-id").first()
        return last.content[:120] if last else ""


class ConversationDetailSerializer(ConversationSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ("messages",)


class SendMessageSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=1000, trim_whitespace=True)
    use_profile = serializers.BooleanField(default=True)
    search_web = serializers.BooleanField(default=False)

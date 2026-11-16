from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AIStatusView, AskView, ConversationViewSet, RecommendationsView


router = DefaultRouter()
router.register("conversations", ConversationViewSet, basename="conversation")

urlpatterns = [
    path("recommendations/", RecommendationsView.as_view(), name="recommendations"),
    path("ai/ask/", AskView.as_view(), name="ai-ask"),
    path("ai/status/", AIStatusView.as_view(), name="ai-status"),
    *router.urls,
]

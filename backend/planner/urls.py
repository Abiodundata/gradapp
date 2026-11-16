from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DeadlinesView, SavedProgramViewSet


router = DefaultRouter()
router.register("saved-programs", SavedProgramViewSet, basename="saved-program")

urlpatterns = [path("deadlines/", DeadlinesView.as_view(), name="deadlines"), *router.urls]

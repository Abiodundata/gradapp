from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CurrentUserView, ManageUsersViewSet, RegisterView, StudentProfileView


router = DefaultRouter()
router.register("users", ManageUsersViewSet, basename="managed-user")

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("me/", CurrentUserView.as_view(), name="current_user"),
    path("profile/", StudentProfileView.as_view(), name="student_profile"),
]

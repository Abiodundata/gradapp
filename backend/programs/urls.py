from rest_framework.routers import DefaultRouter

from .views import FacultyViewSet, FundingOpportunityViewSet, GraduateProgramViewSet, UniversityViewSet


router = DefaultRouter()
router.register("universities", UniversityViewSet, basename="university")
router.register("programs", GraduateProgramViewSet, basename="program")
router.register("faculty", FacultyViewSet, basename="faculty")
router.register("funding", FundingOpportunityViewSet, basename="funding")

urlpatterns = router.urls

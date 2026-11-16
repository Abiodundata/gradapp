from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from gradapp.testutils import PASSWORD, make_user


User = get_user_model()


class AuthenticationTests(APITestCase):
    def setUp(self):
        cache.clear()  # reset throttling counters between tests

    def register(self, **overrides):
        payload = {
            "username": "student1",
            "email": "student1@example.com",
            "first_name": "Test",
            "last_name": "Student",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        }
        payload.update(overrides)
        return self.client.post(reverse("register"), payload, format="json")

    def test_registration_creates_user_and_profile(self):
        response = self.register()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="student1")
        self.assertTrue(hasattr(user, "student_profile"))

    def test_password_mismatch_returns_readable_message(self):
        response = self.register(password_confirm="Different!2026")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["message"], "Password confirm: Passwords do not match.")

    def test_duplicate_email_and_username_rejected(self):
        self.register()
        response = self.register(username="student2", email="STUDENT1@example.com")
        self.assertIn("email already exists", response.data["error"]["message"])
        response = self.register(username="Student1", email="new@example.com")
        self.assertIn("already taken", response.data["error"]["message"])

    def test_login_returns_tokens_and_staff_flag(self):
        make_user("student1")
        response = self.client.post(reverse("login"), {"username": "student1", "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertFalse(response.data["user"]["is_staff"])

    def test_invalid_login_returns_readable_message(self):
        response = self.client.post(reverse("login"), {"username": "nobody", "password": "wrong"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["message"], "Invalid username or password.")

    def test_logout_blacklists_refresh_token(self):
        make_user("student1")
        tokens = self.client.post(reverse("login"), {"username": "student1", "password": PASSWORD}, format="json").data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(self.client.post(reverse("logout"), {"refresh": tokens["refresh"]}, format="json").status_code, 204)
        refresh = self.client.post(reverse("token_refresh"), {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_rejects_another_users_token(self):
        make_user("student1")
        other = make_user("student2")
        tokens = self.client.post(reverse("login"), {"username": "student1", "password": PASSWORD}, format="json").data
        self.client.force_authenticate(other)
        response = self.client.post(reverse("logout"), {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_profile_requires_authentication(self):
        response = self.client.get(reverse("student_profile"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_update_profile(self):
        user = make_user("student1")
        self.client.force_authenticate(user=user)
        response = self.client.patch(
            reverse("student_profile"),
            {
                "intended_degree_level": "masters",
                "previous_field_of_study": "Computer Science",
                "gpa": "3.75",
                "research_interests": "Artificial intelligence",
                "preferred_programs": "Computer Science, Data Science",
                "funding_requirement": "required",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["intended_degree_level"], "masters")
        self.assertEqual(response.data["funding_requirement"], "required")

    def test_profile_rejects_boolean_funding_requirement(self):
        """Regression test: Iteration 1 frontend sent true/false here."""
        self.client.force_authenticate(user=make_user("student1"))
        response = self.client.patch(reverse("student_profile"), {"funding_requirement": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ManageUsersTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin", staff=True)
        self.student = make_user("student")

    def test_students_cannot_manage_users(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(reverse("managed-user-list")).status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_list_and_search_users(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("managed-user-list"), {"search": "stud"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([user["username"] for user in response.data["results"]], ["student"])

    def test_admin_can_deactivate_user(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(reverse("managed-user-detail", args=[self.student.id]), {"is_active": False}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)

    def test_admin_cannot_deactivate_self(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(reverse("managed-user-detail", args=[self.admin.id]), {"is_active": False}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_cannot_change_username(self):
        self.client.force_authenticate(self.admin)
        self.client.patch(reverse("managed-user-detail", args=[self.student.id]), {"username": "hacked"}, format="json")
        self.student.refresh_from_db()
        self.assertEqual(self.student.username, "student")


class HealthCheckTests(APITestCase):
    def test_health_check(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")

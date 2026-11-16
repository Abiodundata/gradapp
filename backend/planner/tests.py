from datetime import date, timedelta

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from gradapp.testutils import make_funding, make_program, make_university, make_user

from .models import SavedProgram


class SavedProgramTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.other = make_user("other")
        self.university = make_university()
        self.program = make_program(self.university)
        self.client.force_authenticate(self.user)

    def save(self, program=None):
        return self.client.post(reverse("saved-program-list"), {"program_id": (program or self.program).id}, format="json")

    def test_save_and_list_program(self):
        self.assertEqual(self.save().status_code, status.HTTP_201_CREATED)
        response = self.client.get(reverse("saved-program-list"))
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["program"]["id"], self.program.id)
        program = self.client.get(reverse("program-detail", args=[self.program.id])).data
        self.assertTrue(program["is_saved"])

    def test_cannot_save_twice(self):
        self.save()
        response = self.save()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already saved", response.data["error"]["message"])

    def test_users_only_see_their_own_saved_programs(self):
        entry = SavedProgram.objects.create(user=self.other, program=self.program)
        self.assertEqual(self.client.get(reverse("saved-program-list")).data["count"], 0)
        self.assertEqual(self.client.get(reverse("saved-program-detail", args=[entry.id])).status_code, 404)
        self.assertEqual(self.client.delete(reverse("saved-program-detail", args=[entry.id])).status_code, 404)

    def test_update_status_notes_and_personal_deadline(self):
        entry_id = self.save().data["id"]
        target = (date.today() + timedelta(days=5)).isoformat()
        response = self.client.patch(
            reverse("saved-program-detail", args=[entry_id]),
            {"status": "preparing", "notes": "Ask for letters", "personal_deadline": target},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status_display"], "Preparing application")

    def test_remove_saved_program(self):
        entry_id = self.save().data["id"]
        self.assertEqual(self.client.delete(reverse("saved-program-detail", args=[entry_id])).status_code, 204)
        self.assertFalse(SavedProgram.objects.exists())


class DeadlineTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        university = make_university()
        self.soon = make_program(university, "Data Science", days=7)
        self.later = make_program(university, "Statistics", days=90)
        self.past = make_program(university, "History", days=-3)
        self.undated = make_program(university, "Physics", days=None)
        for program in (self.soon, self.later, self.past, self.undated):
            SavedProgram.objects.create(user=self.user, program=program)
        SavedProgram.objects.filter(program=self.later).update(personal_deadline=date.today() + timedelta(days=60))
        make_funding("Data Science Assistantship", university, self.soon, days=20)
        unrelated = make_program(make_university("Elsewhere University"), "Biology")
        make_funding("Unrelated Fellowship", unrelated.university, unrelated, days=5)

    def test_deadlines_are_combined_and_sorted(self):
        response = self.client.get(reverse("deadlines"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        kinds = [(item["kind"], item["days_left"]) for item in response.data["results"]]
        self.assertEqual(kinds, [("application", 7), ("funding", 20), ("personal", 60), ("application", 90)])
        self.assertEqual(response.data["results"][0]["urgency"], "urgent")
        self.assertEqual([p["program_name"] for p in response.data["saved_without_deadline"]], ["Physics"])

    def test_past_deadlines_optional(self):
        response = self.client.get(reverse("deadlines"), {"include_past": "true"})
        self.assertEqual(response.data["results"][0]["urgency"], "past")

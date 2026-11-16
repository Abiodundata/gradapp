from unittest import mock

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from gradapp.testutils import make_faculty, make_funding, make_program, make_university, make_user


class RecommendationTests(APITestCase):
    def setUp(self):
        texas = make_university("Texas Example University")
        canada = make_university("Northern University", city="Toronto", state="Ontario", country="Canada")
        self.ml = make_program(texas, "Machine Learning", tuition_per_year=18000, funding_available=True, minimum_gpa="3.00",
                               description="Deep learning and computer vision.")
        self.history = make_program(texas, "History", tuition_per_year=15000)
        self.expensive = make_program(canada, "Artificial Intelligence", tuition_per_year=60000, description="Machine learning research.")
        self.phd = make_program(texas, "Machine Learning", degree="doctoral")
        make_faculty(texas, "Dr. Vision", "computer vision, robotics", [self.ml])
        self.user = make_user(
            intended_degree_level="masters", research_interests="machine learning, computer vision",
            preferred_locations="Texas", tuition_budget=25000, gpa="3.50", funding_requirement="required",
        )
        self.client.force_authenticate(self.user)

    def test_ranks_best_fit_first_with_reasons(self):
        response = self.client.get(reverse("recommendations"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(results[0]["program"]["id"], self.ml.id)
        self.assertTrue(response.data["profile_complete"])
        self.assertTrue(any("Dr. Vision" in reason for reason in results[0]["reasons"]))
        self.assertEqual(results[0]["matched_faculty"][0]["matched_areas"], ["computer vision"])
        self.assertLessEqual(results[0]["score"], 100)

    def test_respects_intended_degree_level(self):
        ids = [item["program"]["id"] for item in self.client.get(reverse("recommendations")).data["results"]]
        self.assertNotIn(self.phd.id, ids)

    def test_cautions_explain_poor_fit(self):
        results = {item["program"]["id"]: item for item in self.client.get(reverse("recommendations")).data["results"]}
        cautions = " ".join(results[self.expensive.id]["cautions"])
        self.assertIn("well above your", cautions)
        self.assertIn("Not in your preferred locations", cautions)
        self.assertIn("need funding", cautions)

    def test_empty_profile_is_flagged(self):
        self.client.force_authenticate(make_user("newbie"))
        response = self.client.get(reverse("recommendations"))
        self.assertFalse(response.data["profile_complete"])

    def test_ai_summary_when_requested(self):
        with mock.patch("assistant.views.llm.complete", return_value="Great fit overall.") as complete:
            response = self.client.get(reverse("recommendations"), {"explain": "true"})
        self.assertEqual(response.data["summary"], "Great fit overall.")
        self.assertIn("Machine Learning", complete.call_args.kwargs["messages"][0]["content"])


class AskAITests(APITestCase):
    def setUp(self):
        university = make_university()
        self.program = make_program(university, "Data Science", description="Statistics and machine learning.")
        self.faculty = make_faculty(university, "Dr. Stats", "machine learning, statistics", [self.program])
        self.funding = make_funding("Machine Learning Fellowship", university, self.program)
        self.client.force_authenticate(make_user(research_interests="machine learning"))

    def ask(self, question, **extra):
        return self.client.post(reverse("ai-ask"), {"question": question, **extra}, format="json")

    def test_fallback_without_api_key_returns_sources(self):
        response = self.ask("Which programs cover machine learning?")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["ai_powered"])
        refs = [source["ref"] for source in response.data["sources"]]
        self.assertEqual(refs, [f"P{self.program.id}", f"F{self.faculty.id}", f"G{self.funding.id}"])
        self.assertIn(f"[P{self.program.id}]", response.data["answer"])

    def test_ai_answer_is_grounded_in_records(self):
        with mock.patch("assistant.qa.llm.complete", return_value=f"Try Data Science [P{self.program.id}].") as complete:
            response = self.ask("Which programs cover machine learning?", history=[
                {"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"},
            ])
        self.assertTrue(response.data["ai_powered"])
        system, messages = complete.call_args.args[0], complete.call_args.args[1]
        self.assertIn("ONLY the records", system)
        self.assertEqual([m["role"] for m in messages], ["user", "assistant", "user"])
        self.assertIn(f"[P{self.program.id}] Data Science", messages[-1]["content"])

    def test_no_matching_records(self):
        response = self.ask("zzzz qqqq", use_profile=False)
        self.assertEqual(response.data["sources"], [])
        self.assertIn("couldn't find", response.data["answer"])

    def test_question_is_required(self):
        response = self.ask("   ")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_status_endpoint(self):
        self.assertEqual(self.client.get(reverse("ai-status")).data, {"ai_enabled": False, "web_search_enabled": False})


class OpenAIClientTests(APITestCase):
    """The OpenAI wrapper used by every AI feature."""

    def _response(self, text):
        message = mock.Mock(content=text)
        return mock.Mock(choices=[mock.Mock(message=message)])

    def test_not_configured_returns_none_without_calling_api(self):
        from . import llm

        with self.settings(OPENAI_API_KEY=""), mock.patch.object(llm, "_get_client") as get_client:
            self.assertIsNone(llm.complete("system", [{"role": "user", "content": "hi"}]))
        get_client.assert_not_called()

    def test_sends_system_prompt_and_model(self):
        from . import llm

        client = mock.Mock()
        client.chat.completions.create.return_value = self._response("  Hello there.  ")
        with self.settings(OPENAI_API_KEY="sk-test", OPENAI_MODEL="gpt-test", AI_REASONING_TOKEN_HEADROOM=100), \
             mock.patch.object(llm, "_get_client", return_value=client):
            reply = llm.complete("Be brief.", [{"role": "user", "content": "hi"}], max_tokens=50)
        self.assertEqual(reply, "Hello there.")
        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-test")
        self.assertEqual(kwargs["messages"][0], {"role": "system", "content": "Be brief."})
        self.assertEqual(kwargs["messages"][1], {"role": "user", "content": "hi"})
        self.assertEqual(kwargs["max_completion_tokens"], 150)

    def test_api_errors_fall_back_to_none(self):
        from . import llm

        client = mock.Mock()
        client.chat.completions.create.side_effect = RuntimeError("invalid api key")
        with self.settings(OPENAI_API_KEY="sk-test"), mock.patch.object(llm, "_get_client", return_value=client):
            self.assertIsNone(llm.complete("system", [{"role": "user", "content": "hi"}]))

    def test_empty_reply_is_treated_as_unavailable(self):
        from . import llm

        client = mock.Mock()
        client.chat.completions.create.return_value = self._response(None)
        with self.settings(OPENAI_API_KEY="sk-test"), mock.patch.object(llm, "_get_client", return_value=client):
            self.assertIsNone(llm.complete("system", [{"role": "user", "content": "hi"}]))

    def test_ask_uses_openai_when_key_is_set(self):
        from . import llm

        university = make_university()
        program = make_program(university, "Data Science", description="Machine learning.")
        client = mock.Mock()
        client.chat.completions.create.return_value = self._response(f"See [P{program.id}].")
        self.client.force_authenticate(make_user())
        with self.settings(OPENAI_API_KEY="sk-test"), mock.patch.object(llm, "_get_client", return_value=client):
            response = self.client.post(reverse("ai-ask"), {"question": "machine learning programs"}, format="json")
            status_response = self.client.get(reverse("ai-status"))
        self.assertTrue(response.data["ai_powered"])
        self.assertEqual(response.data["answer"], f"See [P{program.id}].")
        self.assertEqual(status_response.data, {"ai_enabled": True, "web_search_enabled": True})


class AskRetrievalQualityTests(APITestCase):
    """Regression tests for questions students actually asked."""

    def setUp(self):
        texas = make_university("Texas Example University")
        canada = make_university("Northern University", city="Toronto", state="Ontario", country="Canada")
        self.health = make_program(texas, "Public Health", funding_details="Merit scholarships available.")
        self.cs_ms = make_program(texas, "Computer Science", description="Sample data for demonstration only.")
        self.cs_phd = make_program(texas, "Computer Science", degree="doctoral", funding_available=True)
        self.ds_canada = make_program(canada, "Data Science", description="Sample data for demonstration only.")
        self.closed_phd = make_program(canada, "Physics", degree="doctoral", funding_available=True, days=-3)
        self.intl = make_funding("Global Scholarship", canada, None, funding_type="scholarship", international_eligible=True)
        self.domestic = make_funding("Residents Scholarship", texas, None, funding_type="scholarship", international_eligible=False)
        self.closed = make_funding("Expired Scholarship", texas, None, funding_type="scholarship", days=-1)
        self.assistantship = make_funding("Teaching Assistantship", texas, self.cs_ms, funding_type="assistantship")
        self.client.force_authenticate(make_user())

    def refs(self, question):
        response = self.client.post(reverse("ai-ask"), {"question": question, "use_profile": False}, format="json")
        return [source["ref"] for source in response.data["sources"]]

    def test_international_scholarships_question(self):
        refs = self.refs("What scholarships are open to international students?")
        self.assertEqual(refs, [f"G{self.intl.id}"])  # no domestic-only, expired, or non-scholarship funding, no programs

    def test_degree_level_and_location_are_respected(self):
        refs = self.refs("Compare computer science master's programs in Texas")
        self.assertEqual(refs[0], f"P{self.cs_ms.id}")
        self.assertNotIn(f"P{self.cs_phd.id}", refs)
        self.assertNotIn(f"P{self.ds_canada.id}", refs)

    def test_generic_funding_question_lists_open_funded_programs(self):
        refs = self.refs("Which PhD programs have funding?")
        self.assertEqual(refs[0], f"P{self.cs_phd.id}")
        self.assertNotIn(f"P{self.closed_phd.id}", refs)

    def test_program_name_outranks_incidental_words(self):
        refs = self.refs("Tell me about the Data Science program at Northern University")
        self.assertEqual(refs[0], f"P{self.ds_canada.id}")


class OpenAIClientConfigTests(APITestCase):
    def tearDown(self):
        from . import llm

        llm._client = None

    def test_empty_base_url_falls_back_to_openai(self):
        """Regression: Docker Compose sets OPENAI_BASE_URL="" when unused."""
        import os

        from . import llm

        llm._client = None
        with self.settings(OPENAI_API_KEY="sk-test", OPENAI_BASE_URL=""), mock.patch.dict(os.environ, {"OPENAI_BASE_URL": ""}):
            client = llm._get_client()
        self.assertEqual(str(client.base_url).rstrip("/"), "https://api.openai.com/v1")

    def test_custom_base_url_is_used(self):
        from . import llm

        llm._client = None
        with self.settings(OPENAI_API_KEY="sk-test", OPENAI_BASE_URL="https://example-proxy.test/v1"):
            client = llm._get_client()
        self.assertEqual(str(client.base_url).rstrip("/"), "https://example-proxy.test/v1")

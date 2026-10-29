"""Regression checks for the production filter policy; no applications sent."""
import unittest
from contextlib import ExitStack
from unittest import mock

import SeekBot as bot
import config
from sample_profile import COVER_LETTER_TEMPLATE


class AccurateApplicationTests(unittest.TestCase):
    def setUp(self):
        self.filters = {
            "keywords": ["Customer Service Officer", "Sales Associate"],
            "related_roles": ["Customer Support", "Sales Support"],
            "allow_related_roles": False,
            "exact_position_match": True,
            "location": ["Melbourne Victoria,Australia"],
            "job_type": ["full time"], "strict_job_type": True,
            "experience": ["2 years"], "current_salary": [60000],
        }
        self.metadata = {"location": "Melbourne VIC", "job_type": "Full time", "salary": "$60,000 - $65,000"}
        self.detail = "Provide customer service. Requires 2 years experience."
        patcher = mock.patch.dict(bot.JOB_FILTERS_CFG, self.filters, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        bot.VALIDATED_JOB_CONTEXT.clear()
        self.addCleanup(bot.VALIDATED_JOB_CONTEXT.clear)

    def evaluate(self, title, **kwargs):
        return bot.evaluate_configured_job_filters(title, self.detail, job_metadata=self.metadata, **kwargs)

    def test_exact_positions_and_metadata_suffixes_pass(self):
        for title in ["Sales Associate", "Customer Service Officer", "Customer Service Officer - Melbourne", "Customer-Service Officer (Full time)"]:
            with self.subTest(title=title):
                self.assertTrue(self.evaluate(title)["eligible"])

    def test_wrong_positions_fail_even_with_matching_words_in_description(self):
        self.detail += " Customer Service Officer Sales Associate Melbourne full time"
        for title in ["Sales", "Sales Manager", "Associate Sales Manager", "Customer Support", "Sales Support", "Customer Service Officer Manager", "Customer Service Manager / Officer", "Customer Service Officer / Sales Manager", "Senior Customer Service Officer", "Customer Service Officer Team Leader", "", "Customer Service Officers"]:
            with self.subTest(title=title):
                self.assertFalse(self.evaluate(title)["eligible"])

    def test_config_roles_are_used_without_explicit_arguments(self):
        self.assertTrue(self.evaluate("Sales Associate")["eligible"])
        self.assertFalse(self.evaluate("Project Engineer")["eligible"])

    def test_documents_are_prepared_even_when_continue_is_available(self):
        for active_step in ("choose documents", "answer employer questions"):
            with self.subTest(active_step=active_step), mock.patch.object(bot, "get_active_application_step", return_value=active_step):
                self.assertTrue(bot.should_prepare_active_application(object(), phase="pre_review", step_name="CONTINUE"))

    def test_question_options_match_configured_salary_and_visa(self):
        self.assertIn("65k", bot.get_choice_answer_tokens("expected_salary", ["65000"]))
        self.assertIn("I have a graduate temporary work visa", bot.get_choice_answer_tokens("visa_type", ["485 Temporary Graduate"]))
        self.assertEqual(bot.get_configured_answer_for_context("What's your expected annual base salary?", {"expected_salary": [65000]}), ("expected_salary", ["65000"]))

    def test_licence_and_certificate_answers_are_not_guessed(self):
        browser = mock.Mock(page_source="Driver's licence, Australia, RSA")
        with mock.patch.object(bot, "answer_common_select_questions", return_value=False), mock.patch.object(bot, "answer_common_input_questions", return_value=False), mock.patch.object(bot, "answer_common_radio_questions", return_value=False):
            self.assertFalse(bot.answer_known_employer_questions(browser))
            browser.find_elements.assert_not_called()

    def test_decision_applies_only_to_matching_position(self):
        for title, expected in [("Sales Associate", "APPLY"), ("Sales Manager", "SKIP")]:
            with self.subTest(title=title):
                result = self.evaluate(title)
                decision = bot.build_job_decision(
                    "12345", "https://au.seek.com/job/12345", "Example", title, self.detail,
                    result, bot.evaluate_match(title, self.detail),
                    client_context=bot.build_client_context(filters=self.filters),
                )
                self.assertEqual(decision["decision"], expected)

    def test_missing_target_roles_fail_closed(self):
        self.assertFalse(self.evaluate("Sales Associate", filters={**self.filters, "keywords": []})["eligible"])

    def test_city_required_not_state_or_country(self):
        for location in ["Sydney NSW Australia", "Geelong Victoria Australia", "Australia", "Melbourneville VIC", ""]:
            with self.subTest(location=location):
                self.metadata["location"] = location
                self.detail += " Offices in Melbourne VIC Australia."
                self.assertFalse(self.evaluate("Sales Associate")["eligible"])

    def test_work_type_required_from_advertised_field(self):
        for job_type in ["Contract", "Casual", "Part time", ""]:
            with self.subTest(job_type=job_type):
                self.metadata["job_type"] = job_type
                self.detail += " A full time team supports this role."
                self.assertFalse(self.evaluate("Sales Associate")["eligible"])

    def test_salary_and_experience_failures_are_hard_gates(self):
        self.metadata["salary"] = "$45,000 - $50,000"
        self.assertFalse(self.evaluate("Sales Associate")["eligible"])
        self.metadata["salary"] = "$60,000 - $65,000"
        self.detail = "Requires 5 years experience."
        self.assertFalse(self.evaluate("Sales Associate")["eligible"])

    def test_zero_experience_does_not_disable_experience_filter(self):
        self.filters["experience"] = ["0 years"]
        self.assertFalse(self.evaluate("Sales Associate", filters=self.filters)["eligible"])

    def test_global_exclusions_block_an_otherwise_matching_job(self):
        with mock.patch.object(bot, "EXCLUDE_KEYWORDS", ["commission only"]):
            self.detail += " Commission only role."
            self.assertFalse(self.evaluate("Sales Associate")["eligible"])

    def validate_context(self):
        bot.VALIDATED_JOB_CONTEXT.update(job_id="12345", title="Sales Associate", detail=self.detail, metadata=dict(self.metadata))

    def check_submit(self, url="https://www.seek.com.au/job/12345/apply/review", title="Review your application"):
        with mock.patch.object(bot, "get_current_job_identity", return_value={"url": url, "title": title}):
            return bot.revalidate_current_job_title_before_submit(object())["title_match"]

    def test_verified_job_can_submit_with_generic_review_heading(self):
        self.validate_context()
        self.assertTrue(self.check_submit())
        self.assertTrue(self.check_submit(title="Sales Associate"))

    def test_different_job_id_or_title_cannot_submit(self):
        self.validate_context()
        self.assertFalse(self.check_submit(url="https://au.seek.com/job/99999/apply"))
        self.assertFalse(self.check_submit(title="Customer Service Officer"))
        self.assertFalse(self.check_submit(url="https://example.com/job/12345/apply"))
        self.assertFalse(self.check_submit(url="https://au.seek.com/apply"))

    def test_unvalidated_job_cannot_submit(self):
        self.assertFalse(self.check_submit(title="Sales Associate"))

    def test_changed_filters_rechecked_before_submit(self):
        self.validate_context()
        bot.JOB_FILTERS_CFG["location"] = ["Sydney NSW"]
        self.assertFalse(self.check_submit())

    def test_submit_flow_never_clicks_when_job_identity_changed(self):
        self.validate_context()
        driver = mock.Mock(current_url="https://au.seek.com/job/99999/apply")
        values = {
            "refresh_active_apply_state": True, "classify_current_location": "internal",
            "is_external_apply": False, "is_application_submitted": False,
            "get_current_flow_phase": "pre_review", "get_apply_page_signature": "signature",
            "get_primary_action_name": "SUBMIT_APPLICATION", "should_prepare_active_application": False,
            "is_employer_questions_step": False, "get_primary_action_selectors": ["//button"],
            "get_current_job_identity": {"url": driver.current_url, "title": "Sales Associate"},
        }
        with ExitStack() as stack:
            for name, value in values.items():
                stack.enter_context(mock.patch.object(bot, name, return_value=value))
            submit = stack.enter_context(mock.patch.object(bot, "hard_submit_application"))
            click = stack.enter_context(mock.patch.object(bot, "click_first_match"))
            self.assertEqual(bot.run_quick_apply_flow(driver), "title_mismatch_final_check")
            submit.assert_not_called()
            click.assert_not_called()


class ProductionConfigTests(unittest.TestCase):
    def test_complete_cover_letter_body_is_preserved_for_different_jobs(self):
        template = COVER_LETTER_TEMPLATE
        original_body = template.split("\n\n", 2)[2]
        for role, company in [("Customer Service Representative", "Example's Supplies"), ("Customer Service Officer", "Sample Employer"), ("Sales Associate", "Example & Company Pty Ltd")]:
            with self.subTest(role=role, company=company):
                letter = bot.build_cover_letter_text(template, company, role)
                self.assertEqual(bot.rewrite_cover_letter_for_current_job(template, company, role), letter)
                self.assertIn(f"{role} position at {company}", letter)
                self.assertEqual(letter.split("\n\n", 2)[2], original_body)
                self.assertIn("sample training", letter)
                self.assertIn("Kind regards,\nExample Applicant", letter)
                self.assertNotIn("{position}", letter)
                self.assertNotIn("{company}", letter)

    def test_explicit_placeholders_do_not_rewrite_other_company_or_position_words(self):
        template = "Applying for {position} at {company}.\n\nMy previous Company Position remains unchanged."
        self.assertEqual(bot.build_cover_letter_text(template, "Position Company Pty Ltd", "Sales Associate"), "Applying for Sales Associate at Position Company Pty Ltd.\n\nMy previous Company Position remains unchanged.")

    def test_cached_driver_for_another_browser_major_is_not_used(self):
        with mock.patch.object(bot.os.path, "isdir", return_value=True), mock.patch.object(bot.os, "walk", return_value=[(r"C:\cache\154.0.1.2", [], ["chromedriver.exe"])]):
            self.assertEqual(bot.find_local_chromedriver("156.0.1.2"), "")

    def test_manager_fallback_to_incompatible_driver_is_rejected(self):
        with mock.patch.object(bot, "find_local_chromedriver", return_value=""), mock.patch.object(bot.SeleniumManager, "binary_paths", return_value={"driver_path": "driver.exe"}), mock.patch.object(bot.os.path, "isfile", return_value=True), mock.patch.object(bot.subprocess, "run", return_value=mock.Mock(stdout="ChromeDriver 154.0.1.2")):
            with self.assertRaisesRegex(RuntimeError, "incompatible"):
                bot.resolve_chromedriver("156.0.1.2")

    def test_testing_does_not_rewrite_user_preferences(self):
        filters = config.CONFIG["resume"]["job_filters"]
        self.assertEqual(filters["location"], [config.LOCATION] if config.LOCATION else [])
        self.assertEqual(filters["experience"], [f"{config.EXPERIENCE_YEARS} years"] if config.EXPERIENCE_YEARS is not None else [])
        self.assertEqual(filters["expected_salary"], [config.EXPECTED_SALARY] if config.EXPECTED_SALARY is not None else [])
        self.assertFalse(config.CONFIG["matching"]["allow_related_roles"])
        self.assertTrue(config.CONFIG["matching"]["exact_position_match"])


if __name__ == "__main__":
    unittest.main()

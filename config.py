import json
import sys
import os
import re
import time
import threading

# ==============================================================================
# 📝 USER CONFIGURATION / CLIENT DETAILS (Sirf yahan details edit karein)
# ==============================================================================

# 1. Job Search URLs: Seek search page ke link yahan dalein
# 💡 LIVE TESTING TIP: Agar aapko check karna hai ki apply ho raha hai ya nahi, to "Data Entry" ya
# "Customer Service" ka link yahan dalein aur DESIRED_POSITIONS me "Data Entry" dalein (Kyunki engineering
# roles ke 100% jobs external sites par hote hain jisme quick apply nahi hota).
# Example Test URL: "https://au.seek.com/data-entry-jobs-in-office-support/in-All-Sydney-NSW"
SEARCH_URLS = []

# 2. Desired Job Positions: Jo job roles aapko apply karne hain unke names
DESIRED_POSITIONS = []

RELATED_POSITIONS = []
    

# 3. Job Location: Aapko kis city me job chahiye (Example: "Sydney", "Melbourne", "Brisbane")
LOCATION = ''

# 4. Your Experience: Aapke paas kitne saal ka experience hai (Sirf number likhein, e.g., 3 ya 5)
EXPERIENCE_YEARS = None

# 5. Minimum Acceptable Salary: Aapki minimum acceptable salary kitni hai (Annual number in AUD)
MINIMUM_SALARY = None

# 6. Maximum Expected Salary: Aapki expected salary limit kitni hai (Annual number in AUD)
EXPECTED_SALARY = None
SALARY_TOLERANCE = 1000

# 7. Visa Type: Aapka current visa type (Example: "500 Student Visa", "485 Temporary Graduate")
VISA_TYPE = ''

# 8. Resume File Name: Agar aapka resume Seek profile par already uploaded hai, to ise khaali "" chodein.
# Agar local file upload karni hai, to file name likhein (e.g., "resume.pdf").
RESUME_FILE_NAME = ""

# 9. Cover Letter File Name: Agar cover letter uploaded hai to ise khaali "" chodein.
# Agar local cover letter use karna hai to name likhein (e.g., "cover_letter.docx").
COVER_LETTER_FILE_NAME = ""

# Keep the applicant's original complete letter. Only these two placeholders
# change between applications; the remaining text is preserved verbatim.
COVER_LETTER_TEMPLATE = ''

# 10. Master Automation Mode:
# True rakhne par bot saare SEARCH_URLS ko ek ke baad ek complete search karega
# aur run ke start/end/error par Enter prompt nahi dikhayega.
MASTER_SEEK_AUTOMATION = True

# Exact employer-question answers supplied by the applicant.
EMPLOYER_ANSWERS = {}


# ==============================================================================
# ⚙️ SYSTEM SETTINGS & RUNTIME MONKEYPATCH (Inhe change karne ki zaroorat nahi hai)
# ==============================================================================

# Personal settings stay in the ignored local JSON file.
BLOCKED_HR_IDENTIFIERS = []
LOCAL_CONFIG_PATH = os.environ.get("SEEKBOT_LOCAL_CONFIG", os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.local.json"))
_LOCAL_SETTING_NAMES = {
    "SEARCH_URLS", "DESIRED_POSITIONS", "RELATED_POSITIONS", "LOCATION",
    "EXPERIENCE_YEARS", "MINIMUM_SALARY", "EXPECTED_SALARY", "SALARY_TOLERANCE",
    "VISA_TYPE", "RESUME_FILE_NAME", "COVER_LETTER_FILE_NAME",
    "COVER_LETTER_TEMPLATE", "EMPLOYER_ANSWERS", "MASTER_SEEK_AUTOMATION",
    "BLOCKED_HR_IDENTIFIERS",
}
if LOCAL_CONFIG_PATH != "-" and os.path.isfile(LOCAL_CONFIG_PATH):
    with open(LOCAL_CONFIG_PATH, encoding="utf-8") as _local_file:
        _local_settings = json.load(_local_file)
    if not isinstance(_local_settings, dict):
        raise ValueError("Local config must contain a JSON object")
    for _setting_name in _LOCAL_SETTING_NAMES:
        if _setting_name in _local_settings:
            globals()[_setting_name] = _local_settings[_setting_name]

# Patch selenium WebDriver.get to avoid redundant reloads on the same page
try:
    from selenium.webdriver.remote.webdriver import WebDriver
    orig_webdriver_get = WebDriver.get

    def custom_webdriver_get(self, url):
        # If the skip flag is set, clear it and return immediately without reloading or blocking on current_url
        if getattr(self, "_skip_next_reload", False):
            self._skip_next_reload = False
            return
        return orig_webdriver_get(self, url)

    WebDriver.get = custom_webdriver_get
except Exception:
    pass

# Detect if running under unit tests
is_testing = (
    "unittest" in sys.modules
    or "pytest" in sys.modules
    or any("test" in arg.lower() for arg in sys.argv)
    or "TESTING" in os.environ
)

def patch_seekbot_functions():
    return None

# Construct standard config structure for SeekBot.py
CONFIG = {
    "search": {
        "search_urls": SEARCH_URLS,
        "startup_url": "https://www.seek.com.au/",
        "wait_timeout": 12,
        "page_load_wait": 1.2,
        "detail_load_wait": 1.0,
        "flow_retry_limit": 4,
        "click_pause": 0.35,
        "security_verification_timeout_sec": 25,
        "security_verification_poll_sec": 1.0,
        "post_verification_settle_wait_sec": 1.0,
        "salary_tolerance": SALARY_TOLERANCE,
        "max_flow_steps": 20,
        "max_pages_per_search": 0,
        "debug_host": "127.0.0.1",
        "debug_port": 9222,
    },
    "resume": {
        "resume_file": RESUME_FILE_NAME,
        "cover_letter_file": COVER_LETTER_FILE_NAME,
        "require_on_startup": False,
        "job_filters": {
            "keywords": DESIRED_POSITIONS,
            "related_roles": RELATED_POSITIONS,
            "location": [LOCATION] if LOCATION else [],
            "experience": [f"{EXPERIENCE_YEARS} years"] if EXPERIENCE_YEARS is not None else [],
            "visa_type": [VISA_TYPE] if VISA_TYPE else [],
            "current_salary": [MINIMUM_SALARY] if MINIMUM_SALARY is not None else [],
            "expected_salary": [EXPECTED_SALARY] if EXPECTED_SALARY is not None else [],
            "certification": [],
            "cover_letter": [COVER_LETTER_TEMPLATE],
            "job_type": [
                "full time",
                "part time",
                "casual",
            ],
            "classification": [],
            "exclude_keywords": [],
            "strict_job_type": True,
        },
        "profile_keywords": {
            "must_have": [],
            "preferred": [],
        },
        "exclude_keywords": [],
    },
    "matching": {
        "enabled": False,
        "strict_title_match": True,
        "title_match_hard_gate": True,
        "require_title_match_before_apply": True,
        "revalidate_title_before_submit": True,
        "classification_is_search_only": True,
        "must_have_weight": 12,
        "preferred_weight": 4,
        "exclude_penalty": 20,
        "must_have_missing_penalty": 10,
        "min_match_score": 20,
        "min_job_match_score": 70,
        "borderline_job_match_score": 60,
        "allow_unknown_salary": True,
        "allow_related_roles": False,
        "exact_position_match": True,
        "allow_loose_title_match": False,
        "skip_title_mismatch": True,
        "enforce_expected_salary_ceiling": False,
        "experience_strict": True,
        "job_fit_weights": {
            "search_intent": 25,
            "role_relevance": 20,
            "skills_relevance": 20,
            "experience": 20,
            "salary": 10,
            "location_work_type": 5,
        },
    },
    "apply": {
        "employer_answers": EMPLOYER_ANSWERS,
        "session_apply_cap": 0,
        "max_jobs_per_run": 0,
        "quick_apply_only": True,
        "skip_external": True,
        "skip_already_applied": False,
        "auto_submit_enabled": True,
        "skip_on_unanswered_questions": True,
        "wait_for_manual_questions": True,
        "manual_question_timeout_sec": 1800,
        "manual_question_scan_interval_sec": 0.5,
        "manual_field_fill_wait_sec": 5,
        "manual_field_settle_wait_sec": 3,
        "manual_resolution_confirm_wait_sec": 1,
        "force_resume_upload": False,
        "direct_apply_url_fallback": True,
        "prompt_before_run": True,
        "prompt_after_run": not MASTER_SEEK_AUTOMATION,
        "prompt_on_error": not MASTER_SEEK_AUTOMATION,
        "script_exe": "Script.exe",
        "script_au3": "Script.au3",
    },
    "logging": {
        "show_match_details": True,
        "show_skip_reasons": True,
        "enable_evaluation_csv": True,
    },
}

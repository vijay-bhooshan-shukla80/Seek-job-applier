"""Local-profile isolation tests use fictional settings only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class PrivateConfigTests(unittest.TestCase):
    def read_config(self, profile_path):
        script = "import config,json; print(json.dumps({'search': config.SEARCH_URLS, 'visa': config.VISA_TYPE, 'letter': config.CONFIG['resume']['job_filters']['cover_letter'], 'answers': config.CONFIG['apply']['employer_answers']}))"
        result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1], env={**os.environ, "SEEKBOT_LOCAL_CONFIG": profile_path}, text=True, capture_output=True, check=True)
        return json.loads(result.stdout)

    def test_no_local_profile_means_no_applicant_data(self):
        self.assertEqual(self.read_config("-"), {"search": [], "visa": "", "letter": [""], "answers": {}})

    def test_local_json_preserves_full_letter_and_answers(self):
        letter = "Hi,\n\nApplying for {position} at {company}.\n\nFictional qualifications remain unchanged.\n\nExample Applicant"
        answers = {"Which sample training option do you choose?": "Complete training"}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profile.json"
            path.write_text(json.dumps({"SEARCH_URLS": ["https://www.seek.com.au/example-jobs"], "VISA_TYPE": "example permit", "COVER_LETTER_TEMPLATE": letter, "EMPLOYER_ANSWERS": answers}), encoding="utf-8")
            result = self.read_config(str(path))
        self.assertEqual(result["letter"], [letter])
        self.assertEqual(result["answers"], answers)
        self.assertEqual(result["visa"], "example permit")

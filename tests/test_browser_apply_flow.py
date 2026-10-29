"""Opt-in end-to-end tests in Chrome against a local job-site fixture.

Run: $env:SEEK_BROWSER_TESTS='1'; python -m unittest discover -s tests -p test_browser_apply_flow.py -v
No external job application is created.
"""
import csv
import os
import tempfile
import threading
import unittest
from collections import Counter
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from unittest import mock

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

import SeekBot as bot
from sample_profile import COVER_LETTER_TEMPLATE, JOB_FILTERS, EMPLOYER_ANSWERS


@unittest.skipUnless(os.environ.get("SEEK_BROWSER_TESTS") == "1", "Opt-in Chrome integration test")
class BrowserApplyFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.submissions = []
        cls.payloads = []
        cls.external_opens = []
        submissions = cls.submissions
        payloads = cls.payloads
        external_opens = cls.external_opens

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/external":
                    external_opens.append(path)
                job_id = path.split("/")[2] if path.startswith("/job/") else ""
                if "/apply" in path:
                    content = '''<h1 data-automation="job-detail-title">Sales Associate</h1>
                        <span data-automation="advertiser-name">Fixture Employer</span>
                        <nav id="steps"></nav><div id="stage"></div>
                        <script>
                        let step = 0;
                        const names = ['Choose documents', 'Answer employer questions', 'Update SEEK Profile', 'Review and submit'];
                        const answers = {letter:'Construction Labourer at Wrong Employer', visa:'citizen', salary:'30000', vaccine:'unknown'};
                        function advance() { step++; render(); }
                        function render() {
                          document.getElementById('steps').innerHTML = names.map((n,i) => `<button type="submit" ${i===step?'aria-current="step"':''}>${n}</button>`).join('');
                          let html = '';
                          if (step === 0) html = `<label for="letter">Write a cover letter</label><textarea id="letter" oninput="answers.letter=this.value"></textarea><button data-testid="continue-button" onclick="if(answers.letter.includes('Sales Associate') && !answers.letter.includes('Construction Labourer')) advance()">Continue</button>`;
                          if (step === 1) html = `<label for="visa">Which statement describes your right to work in Australia?</label>
                            <select id="visa" onchange="answers.visa=this.value"><option value="citizen">I'm an Australian citizen</option><option value="graduate">I have a graduate temporary work visa</option></select>
                            <label for="salary">What's your expected annual base salary?</label><select id="salary" onchange="answers.salary=this.value"><option value="30000">$30k</option><option value="65000">$65k</option></select>
                            <label for="vaccine">Which sample training option do you choose?</label><select id="vaccine" onchange="answers.vaccine=this.value"><option value="vaccinated">Complete training</option><option value="unknown">Other training</option></select>
                            <button data-testid="continue-button" onclick="if(answers.visa==='graduate' && answers.salary==='65000' && answers.vaccine==='vaccinated') advance()">Continue</button>`;
                          if (step === 2) html = `<h2>Update SEEK Profile</h2><button data-testid="continue-button" onclick="advance()">Continue</button>`;
                          if (step === 3) html = `<h2>Review your application</h2><form method="post" action="/job/__JOB_ID__/submit"><input type="hidden" name="letter"><input type="hidden" name="visa"><input type="hidden" name="salary"><input type="hidden" name="vaccine"><button type="submit" data-testid="submit-application-button">Submit application</button></form>`;
                          document.getElementById('stage').innerHTML=html;
                          if(step===0) document.getElementById('letter').value=answers.letter;
                          if(step===3) for(const key in answers) document.querySelector(`[name=${key}]`).value=answers[key];
                        }
                        render();
                        </script>'''.replace('__JOB_ID__', job_id)
                elif job_id:
                    title = "Sales Manager" if job_id == "10002" else "Sales Associate"
                    target = "99999" if job_id == "10003" else job_id
                    apply_href = "/external" if job_id in ("10004", "10005") else f"/job/{target}/apply"
                    apply_label = "Apply" if job_id in ("10004", "10006") else "Quick apply"
                    content = f'''<h1 data-automation="job-detail-title">{title}</h1>
                        <span data-automation="advertiser-name">Fixture Employer</span>
                        <span data-automation="job-detail-location">Melbourne VIC</span>
                        <span data-automation="job-detail-work-type">Full time</span>
                        <span data-automation="job-detail-salary">$60,000 - $65,000</span>
                        <article data-automation="jobAdDetails">Sales Associate duties providing customer service.
                        Requires 2 years experience.</article>
                        <a data-automation="job-detail-apply" href="{apply_href}">{apply_label}</a>'''
                else:
                    content = "<h1>Fixture</h1>"
                self.respond(content)

            def do_POST(self):
                submissions.append(self.path)
                payloads.append(parse_qs(self.rfile.read(int(self.headers.get('Content-Length', '0'))).decode()))
                self.respond('<h1>Keep it up</h1><p>Your application has been sent to Fixture Employer</p>')

            def respond(self, content):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(("<!doctype html><html><head><title>Local application test</title></head><body><main>" + content + "</main></body></html>").encode())

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.server.daemon_threads = True
        cls.addClassCleanup(cls.server.server_close)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.addClassCleanup(cls.server.shutdown)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        options = Options()
        options.binary_location = bot.find_chrome_binary()
        options.add_argument("--headless=new")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--window-size=1280,1000")
        options.add_argument("--remote-debugging-port=0")
        cls.driver = bot.configure_driver_runtime(webdriver.Chrome(service=Service(bot.resolve_chromedriver(browser_binary=options.binary_location)), options=options))
        cls.addClassCleanup(cls.driver.quit)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="seekbot-flow-")
        self.addCleanup(self.temp.cleanup)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.dict(bot.JOB_FILTERS_CFG, JOB_FILTERS, clear=True))
        self.stack.enter_context(mock.patch.dict(bot.APPLY_CFG, {"employer_answers": EMPLOYER_ANSWERS}))
        original_domain_check = bot.is_seek_domain
        self.stack.enter_context(mock.patch.object(bot, "is_seek_domain", side_effect=lambda url: urlparse(url).netloc == urlparse(self.base).netloc or original_domain_check(url)))
        values = {"LOG_DIR": self.temp.name, "SCREENSHOT_DIR": os.path.join(self.temp.name, "screenshots"),
                  "CSV_LOG_PATH": os.path.join(self.temp.name, "applied.csv"),
                  "EVALUATION_CSV_LOG_PATH": os.path.join(self.temp.name, "evaluation.csv"),
                  "DETAIL_LOAD_WAIT": 0.1, "CLICK_PAUSE": 0.15, "TODAY_SUBMITTED_JOB_KEYS": set(),
                  "MANUAL_FIELD_FILL_WAIT": 0, "MANUAL_FIELD_SETTLE_WAIT": 0,
                  "MANUAL_RESOLUTION_CONFIRM_WAIT": 0, "MANUAL_QUESTION_TIMEOUT": 2,
                  "MAX_FLOW_STEPS": 4}
        for name, value in values.items():
            self.stack.enter_context(mock.patch.object(bot, name, value))
        bot.clear_active_apply_state()
        self.submissions.clear()
        self.payloads.clear()
        self.external_opens.clear()
        self.addCleanup(bot.clear_active_apply_state)

    def process(self, job_id):
        stats = Counter()
        url = f"{self.base}/job/{job_id}"
        bot.process_job_url(self.driver, {"url": url, "key": url, "title": "Sales Associate", "list_quick_apply": True}, 1, stats)
        return stats

    def test_matching_job_reaches_actual_submit_and_confirmation(self):
        stats = self.process("10001")
        self.assertEqual(stats["applied"], 1, stats)
        self.assertEqual(self.submissions, ["/job/10001/submit"])
        # Browser form submission uses CRLF line endings; the textarea uses LF.
        self.assertEqual(self.payloads[0]["letter"][0].replace("\r\n", "\n"), bot.build_cover_letter_text(COVER_LETTER_TEMPLATE, "Fixture Employer", "Sales Associate"))
        self.assertNotIn("Construction Labourer", self.payloads[0]["letter"][0])
        self.assertEqual(self.payloads[0]["visa"], ["graduate"])
        self.assertEqual(self.payloads[0]["salary"], ["65000"])
        self.assertEqual(self.payloads[0]["vaccine"], ["vaccinated"])
        with open(bot.CSV_LOG_PATH, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "submitted")

    def test_wrong_position_is_never_submitted(self):
        stats = self.process("10002")
        self.assertEqual(stats["skipped_filtered"], 1, stats)
        self.assertEqual(self.submissions, [])

    def test_full_cover_letter_is_restored_and_only_names_change_between_jobs(self):
        self.driver.get(f"{self.base}/job/10001/apply")
        original_body = COVER_LETTER_TEMPLATE.split("\n\n", 2)[2]
        for role, company in [("Sales Associate", "Fixture Employer"), ("Customer Service Representative", "Example's Supplies")]:
            with self.subTest(role=role, company=company):
                bot.set_active_job_context(company, role)
                self.assertTrue(bot.answer_common_input_questions(self.driver))
                letter = self.driver.find_element("id", "letter").get_attribute("value")
                self.assertEqual(letter, bot.build_cover_letter_text(COVER_LETTER_TEMPLATE, company, role))
                self.assertEqual(letter.split("\n\n", 2)[2], original_body)
        self.assertEqual(self.submissions, [])

    def test_external_and_plain_apply_links_are_not_opened(self):
        for job_id in ("10004", "10005", "10006"):
            with self.subTest(job_id=job_id):
                handles = list(self.driver.window_handles)
                stats = self.process(job_id)
                self.assertEqual(stats["skipped_no_quick_apply"], 1, stats)
                self.assertEqual(self.driver.current_url, f"{self.base}/job/{job_id}")
                self.assertEqual(self.driver.window_handles, handles)
                self.assertEqual(self.external_opens, [])
                self.assertEqual(self.submissions, [])

    def test_redirect_to_different_job_is_never_submitted(self):
        stats = self.process("10003")
        self.assertEqual(stats["skipped_filtered"], 1, stats)
        self.assertEqual(self.submissions, [])

    def test_debug_driver_attaches_to_matching_browser(self):
        address = self.driver.capabilities["goog:chromeOptions"]["debuggerAddress"]
        host, port = address.rsplit(":", 1)
        with mock.patch.object(bot, "DEBUG_HOST", host), mock.patch.object(bot, "DEBUG_PORT", int(port)), mock.patch.object(bot, "DEBUG_URL", f"http://{address}/json/version"):
            attached = bot.build_debug_driver()
            try:
                self.assertEqual(attached.capabilities["browserVersion"], self.driver.capabilities["browserVersion"])
                self.assertTrue(bot.verify_driver_session(attached))
            finally:
                attached.service.stop()


if __name__ == "__main__":
    unittest.main()

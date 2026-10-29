"""Fictional applicant data for offline/browser tests, never a real profile."""

COVER_LETTER_TEMPLATE = """Hi,

I am applying for {position} position at {company}.

This fictional applicant has completed sample training and has practical experience in a sample workplace. These details are test fixtures, not a real person's qualifications.

The applicant's skills, background, availability and work authorisation remain unchanged between jobs.

Thank you for considering my application.

Kind regards,
Example Applicant"""

JOB_FILTERS = {
    "keywords": ["Customer Service Representative", "Customer Service Officer", "Sales Associate"],
    "related_roles": [], "location": ["Melbourne Victoria,Australia"],
    "experience": ["2 years"], "current_salary": [60000], "expected_salary": [65000],
    "visa_type": ["485 Temporary Graduate"], "cover_letter": [COVER_LETTER_TEMPLATE],
    "job_type": ["full time", "part time", "casual"], "strict_job_type": True,
}

EMPLOYER_ANSWERS = {"Which sample training option do you choose?": "Complete training"}

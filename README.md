# SeekBot
A bot that automatically applies for jobs on seek.com.au


Written in Python


W.I.P


This is my first python project.


SeekBot.py - Main Source Code


Script.exe - AutoIT Script that uploads the cover letter


Script.au3 - Main Source for Script.exe

Job matching
------------

Copy `config.local.example.json` to `config.local.json`, fill in your search
preferences and candidate details there, then run
`python SeekBot.py`. Restart a running bot after changing the configuration.
`config.local.json` is Git-ignored. Keep your full cover letter, contact details,
visa information and employer-question answers in that local file. The tracked
`config.py` contains neutral defaults and loads local settings automatically.
Existing local profiles continue to work without publishing personal data.
The bot resolves a compatible ChromeDriver into the project's ignored
`.cache/selenium` folder. It rejects cached drivers from a different Chrome major
version instead of repeatedly trying an incompatible driver.

The default policy requires an exact normalized position. For example, `Sales
Associate` matches `Sales Associate - Melbourne`, but rejects `Sales Manager`,
`Senior Sales Associate` and `Sales Associate / Team Leader`. Unrecognized title
qualifiers are skipped; add the full acceptable title to `DESIRED_POSITIONS`.
Related roles are disabled by default. To opt into them explicitly, set
`matching.allow_related_roles` to `True`.

Location and work type are checked against the advertised job fields. Missing
required fields cause a skip, and matching words elsewhere in the description
cannot satisfy these filters. Experience and salary checks still follow the
configured policy: unknown salary remains allowed by default, and
`EXPECTED_SALARY` is an application answer unless
`matching.enforce_expected_salary_ceiling` is enabled.

Before automatic submission the bot checks the job ID, position and the
configured filters again. An unrelated tab or an unverified application is
blocked. A generic review heading is accepted only for the previously verified
job ID.

The active application step is read from SEEK's current-step marker. Documents
and employer questions are prepared before Continue, including forms whose
dropdowns initially display an incorrect default. `EXPECTED_SALARY = 65000`
maps to `$65k`; a configured graduate visa maps to the graduate temporary
work visa option. Other answers can be supplied by exact question text in
`EMPLOYER_ANSWERS`. The bot does not guess licence/certificate answers.

The complete original letter is stored in `COVER_LETTER_TEMPLATE` in `config.local.json`.
Only `{position}` and `{company}` are replaced for each application; the rest of
the letter, including experience, qualifications and contact information, stays
unchanged. A configured full template also restores the letter if SEEK retained
a shortened version from a previous application. A sent application is counted only after SEEK confirms it,
including its "Your application has been sent" success message.

Run the offline regression suite with `python -m unittest discover -s tests -q`.
These tests do not send applications. Real advertisements and website changes
still require live verification; no matcher can guarantee 100% accuracy.

For the optional Chrome integration tests in PowerShell:

```powershell
$env:SEEK_BROWSER_TESTS = '1'
python -m unittest discover -s tests -p test_browser_apply_flow.py -v
```

These browser tests use a local server and cover documents, employer questions,
profile, review, submission confirmation, and rejection of unrelated jobs.

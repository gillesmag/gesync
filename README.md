# gesync
`gesync` synchronizes the Guichet Etudiant calendar to Google Calendar

## Requirements

- Python 3.x

## Usage

1. Follow the step 1 found at [Python Quickstart | Google Calendar](https://developers.google.com/calendar/quickstart/python). This will enable the Google Calendar API on the developer console ang give you a credentials.json file.
2. Add the `credentials.json` to the repository's directory.
3. `$ cp creds_template.py creds.py` and add username and password in `creds.py`.
4. Install the required dependencies: `pip install -r requirements.txt`
5. `$ cp courses_template.py courses.py` and specify a list of courses that you want to import into your calendar (if needed)
5. Run the script (example):
```
(venv) $ python3 main.py "University" "2018-12-21"
```

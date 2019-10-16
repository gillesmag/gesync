import requests
from requests_ntlm import HttpNtlmAuth

import json
import re
from courses import COURSES


REQUEST_VERIFICATION_REGEX = r"<input\sname=\"__RequestVerificationToken\"\stype=\"hidden\"\svalue=\"([a-zA-Z0-9_-]+)\" />"


class GuichetEtudiant:
    base_url = "https://inscription.uni.lu/Inscriptions/Student/GuichetEtudiant"
    date_format = "%Y-%m-%dT00:00:00"

    def __init__(self, username, password):
        self.__authenticate(username, password)

    def get_student_formation(self):
        return self.__request(self.__session.post, "/getStudentFormation")

    def get_events(self, start_date, end_date):
        # Get formation ids
        student_formation = self.get_student_formation()
        formations = json.loads(student_formation.content)
        formation_ids = [f["idForm"] for f in formations]

        events = self.get_event_in_period(formation_ids, start_date, end_date)

        # filter only needed keys
        # TODO: kinda complicated and cumbersome, should rewrite this
        # should use a proper object for this that decodes
        # (and encodes) this structure
        
        # Add only selected courses if specified, else all.
        if COURSES:
            events = [e for e in events if e["Cours"] in COURSES]
        
        print("The following courses will be added to the calendar:")
        courses = {e['Cours'] for e in events}
        for c in courses:
            print(f"- {c}" )

        keys = [
            "DateDebut", "DateFin", "Local",
            "Enseignant", "Cours", "Title",
            "LibelleType", "TypeCPE", "IsAllDay"
        ]
        return [dict((key, value) for key, value in event.items() if key in keys) for event in events]

    def get_agenda_page(self):
        return self.__session.post(GuichetEtudiant.base_url + "/Agenda")

    def get_event_in_period(self, formation_ids, start_date, end_date):
        return self.__request(self.__session.post, "/getEventInPeriode", data={
            "start": start_date.strftime(self.date_format),
            "end": end_date.strftime(self.date_format),
            "formations": formation_ids,
            "groupFilter": "all",
        }).json()

    def __request(self, method, uri, data={}):
        if not data.get("__RequestVerificationToken"):
            data["__RequestVerificationToken"] = self.__token

        return method(GuichetEtudiant.base_url + uri, data=data)

    def __authenticate(self, username, password):
        """ Using NTLM authentication, fetch the agenda page and parse out the
        "__RequestVerificationToken" for use in subsequent requests"""
        self.__session = requests.Session()
        self.__session.auth = HttpNtlmAuth('\\' + username, password)
        agenda = self.get_agenda_page()
        token_line = re.compile(REQUEST_VERIFICATION_REGEX)
        self.__token = token_line.findall(str(agenda.content))[0]

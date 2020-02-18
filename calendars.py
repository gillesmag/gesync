from datetime import datetime, time
import json

from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools

import rfc3339

class GoogleCalendar:
    def __init__(self, name, credentials_path="credentials.json"):
        store = file.Storage("token.json")
        creds = store.get()
        if not creds or creds.invalid:
            flow = client.flow_from_clientsecrets(
                credentials_path,
                'https://www.googleapis.com/auth/calendar',
            )
            creds = tools.run_flow(flow, store)

        self.service = build("calendar", "v3", http=creds.authorize(Http()))
        self.calendar_id = self.find_calendar_id(name)
        if self.calendar_id is None:
            raise ValueError("No given calendar found")


    def find_calendar_id(self, calendar_name):
        calendar_list = self.service.calendarList()
        request = calendar_list.list()
        while request is not None:
            cal_list = request.execute()
            for calendar_entry in cal_list['items']:
                if calendar_entry['summary'] == calendar_name:
                    return calendar_entry["id"]
            request = calendar_list.list_next(request, cal_list)
            page_token = calendar_list.get('nextPageToken')
        return None


    def insert_events(self, events):
        """ Inserts events into the Google Calendar """
        batch = self.service.new_batch_http_request()
        date_fmt = "%Y/%m/%d %H:%M"
        for event in events:
            start_date = datetime.strptime(event["DateDebut"], date_fmt)
            end_date = datetime.strptime(event["DateFin"], date_fmt)
            event = {
                'summary': event["Title"],
                'location': event["Local"],
                'start': {
                    'dateTime': rfc3339.rfc3339(start_date),
                    'timeZone': 'Europe/Luxembourg'
                },
                'end': {
                    'dateTime': rfc3339.rfc3339(end_date),
                    'timeZone': 'Europe/Luxembourg'
                },
                'extendedProperties': {
                    'private': {
                        'sync-application': 'gesync',
                    },
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 15},
                    ],
                },
            }
            batch.add(
                self.service.events().insert(calendarId=self.calendar_id, body=event),
                callback=GoogleCalendar.__handle_request_error
            )
        batch.execute()


    def clear_from_midnight(self):
        """ Clears events in calendar from midnight on. """

        batch = self.service.new_batch_http_request()
        midnight = datetime.combine(datetime.now().date(), time())
        page_token = None
        event_ids = set()

        while True:
            events_results = self.service.events().list(
                calendarId=self.calendar_id, pageToken=page_token,
                timeMin=midnight.isoformat() + "Z"
            ).execute()

            for e in events_results.get("items", []):
                extendedProperties = e.get("extendedProperties")
                if extendedProperties:
                    private = extendedProperties.get("private")
                    if private:
                        sync_application = private.get("sync-application")
                        if sync_application == 'gesync':
                            event_ids.add(e["id"])

            page_token = events_results.get("nextPageToken")
            if not page_token:
                break

        for event_id in event_ids:
            batch.add(
                self.service.events().delete(
                    calendarId=self.calendar_id, eventId=event_id
                ),
                callback=GoogleCalendar.__handle_request_error
            )

        batch.execute()

    @staticmethod
    def __handle_request_error(request_id, response, exception):
        if exception is None:
            return
        error = json.loads(exception.content).get("error")
        if error.get("code") != 410:  # Resource already deleted
            print("Error:", error.get("message"))

from datetime import datetime, time
import argparse
import json

from googleapiclient.discovery import build
# from googleapiclient.errors import HttpError
from httplib2 import Http
from oauth2client import file, client, tools

from guichet_etudiant import GuichetEtudiant

import rfc3339

from creds import USERNAME, PASSWORD

SCOPES = 'https://www.googleapis.com/auth/calendar'


def find_calendar_id(service, calendar_name):
    calendar_list = service.calendarList()
    request = calendar_list.list()
    while request is not None:
        cal_list = request.execute()
        for calendar_entry in cal_list['items']:
            if calendar_entry['summary'] == calendar_name:
                return calendar_entry["id"]
        request = calendar_list.list_next(request, cal_list)
        page_token = calendar_list.get('nextPageToken')
    return None


def insert_events(service, calendar_id, events):
    """ Inserts events into the Google Calendar """
    batch = service.new_batch_http_request()
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
            service.events().insert(calendarId=calendar_id, body=event),
            callback=handle_request_error
        )
    batch.execute()


def handle_request_error(request_id, response, exception):
    if exception is not None:
        error = json.loads(exception.content).get("error")
        if error.get("code") != 410:  # Resource already deleted:
            print("Error:", error.get("message"))


# Clears events in calendar from midnight on
def clear_from_midnight(service, calendar_id):
    batch = service.new_batch_http_request()
    midnight = datetime.combine(datetime.now().date(), time())
    page_token = None
    event_ids = set()

    while True:
        events_results = service.events().list(
            calendarId=calendar_id, pageToken=page_token,
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
            service.events().delete(
                calendarId=calendar_id, eventId=event_id
            ),
            callback=handle_request_error
        )

    batch.execute()


def main():
    date_fmt = "%Y-%m-%d"
    parser = argparse.ArgumentParser(
        description="Sync uni.lu Guichet Etudiant with Google Calendar",
        parents=[tools.argparser]
    )
    parser.add_argument(
        "calendar", type=str,
        help="Google Calendar name into which to add events."
    )
    parser.add_argument(
        "end_date", type=str,
        help="End date (format: yyyy-mm-dd)"
    )
    parser.add_argument(
        "--start_date", type=str, required=False,
        default=datetime.now().strftime(date_fmt),
        help="Start date (format: yyyy-mm-dd)"
    )
    flags = parser.parse_args()

    calendar_summary = flags.calendar
    start_date = datetime.strptime(flags.start_date, date_fmt)
    end_date = datetime.strptime(flags.end_date, date_fmt)

    store = file.Storage("token.json")
    creds = store.get()
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets("credentials.json", SCOPES)
        creds = tools.run_flow(flow, store, flags)

    service = build("calendar", "v3", http=creds.authorize(Http()))
    calendar_id = find_calendar_id(service, calendar_summary)
    if not calendar_id:
        raise ValueError("No given calendar found")

    print("Clearing gesync events in calendar \"{}\"".format(calendar_summary))
    clear_from_midnight(service, calendar_id)
    
    guichet_etudiant = GuichetEtudiant(USERNAME, PASSWORD)
    print("Fetching new events from GuichetEtudiant...")
    events = guichet_etudiant.get_events(start_date, end_date)
    print("Inserting events into calendar...")
    insert_events(service, calendar_id, events)
    print("done.")


if __name__ == '__main__':
    main()

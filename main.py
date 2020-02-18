from datetime import timedelta, datetime, date
import argparse

from calendars import GoogleCalendar
from guichet_etudiant import GuichetEtudiant, AuthenticationError

from configparser import ConfigParser

import re
import os.path

import click
import inquirer

def compute_period(expression, start_date):
    match = re.match(r"^(\d+)([dmy])$", expression)
    if match is None or match.groups() is None:
        raise ValueError(f"period {expression} is not specified in the appropriate format")
    amount, unit = match.groups()
    unit_multipliers = {"d": 1, "m": 30, "y": 365}
    days = int(amount) * unit_multipliers[unit]
    return start_date + timedelta(days=days)

def initialize_configuration(config):
    config['general'] = {}
    config['credentials'] = {}
    config['courses'] = {}

    print('General configuration options:')
    config['general']['calendar'] = click.prompt("Google Calendar name", type=str)
    while True:
        config['general']['period'] = click.prompt("Period of time to fetch data (units: d[ay]/m[onth]/y[ear], example: 10d)", type=str)
        try:
            start_date = date.today()
            end_date = compute_period(config['general']['period'], start_date)
        except ValueError:
            click.secho("Wrong format! Please try again.")
            continue
        else:
            break

    print()
    print("Guichet Etudiant credentials:")

    while True:
        username = click.prompt("Username")
        password = click.prompt("Password", hide_input=True)

        config['credentials']['username'] = username
        config['credentials']['password'] = password

        try:
            ge = GuichetEtudiant(username, password)
            break
        except AuthenticationError as e:
            print()
            print(e)
            print("Please try logging in again!")

    courses = list(set(e["Cours"] for e in ge.get_events(start_date, end_date)))
    answers = inquirer.prompt([inquirer.Checkbox(
        'courses',
        message="Select which courses you would like to synchronize",
        choices=courses,
        default=courses,
    )], theme=inquirer.themes.GreenPassion())['courses']

    config['courses'] = {a: None for a in answers}

    with open('config.ini', 'w') as configfile:
        config.write(configfile)

    exit()

def main():
    config = ConfigParser(allow_no_value=True)
    # Don't convert options to lowercase (which is the default for ConfigParser)
    config.optionxform = str

    config_path = 'config.ini'
    if os.path.exists(config_path):
        config.read(config_path)
    else:
        initialize_configuration(config)
    
    date_fmt = "%Y-%m-%d"
    parser = argparse.ArgumentParser(
        description="Sync uni.lu Guichet Etudiant with Google Calendar"
    )
    parser.add_argument(
        "--calendar", type=str,
        help="Google Calendar name into which to add events."
    )
    parser.add_argument(
        "--end_date", type=str,
        help="End date (format: yyyy-mm-dd)"
    )
    parser.add_argument(
        "--start_date", type=str,
        default=datetime.now().strftime(date_fmt),
        help="Start date (format: yyyy-mm-dd)"
    )
    parser.add_argument(
        "--clear", action='store_true',
        help="Only clear calendar, do not import any courses."
    )
    flags = parser.parse_args()

    if flags.calendar:
        calendar_name = flags.calendar
    else:
        calendar_name = config['general']['calendar']

    if flags.start_date:
        start_date = datetime.strptime(flags.start_date, date_fmt).date()
    else:
        start_date = date.today()

    if flags.end_date:
        end_date = datetime.strptime(flags.end_date, date_fmt).date()
    else:
        end_date = compute_period(config['general']['period'], start_date)

    username = config['credentials']['username']
    password = config['credentials']['password']

    course_selection = config['courses']

    cal = GoogleCalendar(calendar_name)

    try:
        guichet_etudiant = GuichetEtudiant(username, password, list(course_selection))
    except AuthenticationError:
        print("Invalid username/password, please update the config.ini in case your credentials have changed.")
        exit()

    if flags.clear:
        print(f"Only clearing gesync events in calendar '{calendar_name}'")
        cal.clear_from_midnight()
        return

    cal.clear_from_midnight()
    
    print("Fetching new events from GuichetEtudiant...")
    events = guichet_etudiant.get_events(start_date, end_date)
    print("Inserting events into calendar...")
    cal.insert_events(events)


if __name__ == '__main__':
    main()

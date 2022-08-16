import pygsheets
from datetime import datetime

gc = pygsheets.authorize(service_file='client_secret.json')

def get_meetup_schedule():
    sh = gc.open('Meetup Schedule')
    wks = sh[0]
    all_records = wks.get_all_records()
    records_to_send = []
    for record in all_records:
        if datetime.strptime(record['Date'], '%d/%m/%Y %H:%M:%S') > datetime.now():
            records_to_send.append(record)

    return records_to_send

def get_past_meetups():
    sh = gc.open('Meetup Schedule')
    wks = sh[0]
    all_records = wks.get_all_records()
    records_to_send = []
    for record in all_records:
        if datetime.strptime(record['Date'], '%d/%m/%Y %H:%M:%S') < datetime.now():
            records_to_send.append(record)

    return records_to_send

if __name__ == '__main__':
    print('None2')
    print(get_meetup_schedule())

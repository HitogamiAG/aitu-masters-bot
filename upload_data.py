from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from db import ShortInfoTable, FullInfoTable
import json
import os

global topics
topics = ['Brief description:', 'Host Institution(s):', 'Level/Field(s) of study:',
            'Number of Awards:', 'Target group:', 'Scholarship value/inclusions/duration:',
            'Eligibility:', 'Application instructions:', 'Website:']

def check_consistence(dictionary):
    if len(dictionary) != 9:
        to_add = list(set(topics) - set(dictionary.keys()))
        for el in to_add:
            dictionary[el] = 'Not found'
        return dictionary
    else:
        return dictionary

def upload_data_main(session: Session):
    with open('./json_files/short_scholarship_data.json') as f:
        short_scholarship_data = json.load(f)
    
    list_to_add = []
    for key, values in short_scholarship_data.items():
        list_to_add.append(ShortInfoTable(
            scholarship_id = int(key),
            title = values['title'],
            link = values['link'],
            university_title = values['university_title'],
            deadline = values['deadline'],
            country = values['country'],

            #ToDo
            actual_deadline = "2023-12-31",
            comment = None,

            rating = 0
        ))
    
    session.add_all(list_to_add)
    del short_scholarship_data

    list_to_add2 = []
    with open('./json_files/full_scholarship_data.json') as f:
        full_scholarship_data = json.load(f)
    for key, values in full_scholarship_data.items():
        values = check_consistence(values)
        list_to_add2.append(FullInfoTable(
            scholarship_id = int(key),
            description = values['Brief description:'],
            field = values['Level/Field(s) of study:'],
            scholarship_amount = values['Number of Awards:'],
            audithory = values['Target group:'],
            scholarship_value = values['Scholarship value/inclusions/duration:'],
            website = values['Website:']
        ))
    session.add_all(list_to_add2)
    del full_scholarship_data

    session.commit()

if __name__ == '__main__':

    engine = create_engine(os.environ.get('DATABASE_URL').replace('postgres', 'postgresql+psycopg2'))
    session = Session(bind=engine)
    upload_data_main(session)


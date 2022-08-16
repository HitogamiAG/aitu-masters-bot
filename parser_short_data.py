import requests
from bs4 import BeautifulSoup
import json
from multiprocessing.pool import ThreadPool
import os

short_scholarship_data = {}

URL_TO_PARSE = os.getenv('website_url')

def clear_string(string):
    return string.encode('ascii', 'ignore').decode().replace('\n', '').replace('\r', '').replace('\t', '')

def search_function(page_id: int):
    URL = f'{URL_TO_PARSE}/{page_id}/'
    page = requests.get(URL)
    soup = BeautifulSoup(page.content, 'html.parser')

    job_elements = soup.find_all('div', class_ = 'post clearfix')

    for job_element in job_elements:

        # Name of scholarship
        title = job_element.find('a').text

        # link to scholarship page
        link = job_element.find('a')['href']

        # id
        id = int(job_element.find('a')['href'].split('/')[3])

        # exception for one error (p.30 Top 25...)
        if id == 9346:
            continue

        subjob_elements = job_element.find_all('div', class_ = 'post_column_1')

        # University title
        try:
            university_title = subjob_elements[0].find('em').text
        except:
            try:
                university_title = str(list(subjob_elements[0].children)[0]).split('<br/>')[0][3:]
            except:
                print('exception')
                print(page_id)
                print(title)
                university_title = 'None'

        # Country
        c = 0
        for i in subjob_elements[1].find('p').children:
            if len(i) == 1 or len(i) == 0:
                continue
            else:
                if c == 0:
                    # Deadline
                    deadline = i[1:]
                elif c == 1:
                    # Country
                    country = i[11:]
                elif c == 2:
                    # Study_start
                    study_start_date = i[1:]
                c+=1

        # Last update
        last_update = job_element.find('div', class_ = 'left').text

        # Closed
        if last_update.find('CURRENTLY CLOSED'):
            closed = True
        else:
            closed = False
        
        short_scholarship_data[id] = {
            'title' : clear_string(title),
            'link' : link,
            'university_title' : clear_string(university_title),
            'deadline' : clear_string(deadline),
            'country' : clear_string(country),
            'stury_start_date' : clear_string(study_start_date),
            'last_update' : clear_string(last_update),
            'closed?' : closed
        }

if __name__ == '__main__':

    page_list = [i for i in range(1, 38)]
    
    with ThreadPool(processes=8) as pool:
        pool.map(search_function, page_list)

    with open('./json_files/short_scholarship_data.json', 'w') as f:
        json.dump(short_scholarship_data, f)
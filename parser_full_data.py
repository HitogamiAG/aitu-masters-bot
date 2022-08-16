import requests
from bs4 import BeautifulSoup
import json
from multiprocessing.pool import ThreadPool
from difflib import SequenceMatcher

def similar(a: str, b):

    max_similarity_string = None
    max_score_similarity = 0

    for string in b:
        similarity_score = SequenceMatcher(None, a, string).ratio()
        if similarity_score > max_score_similarity:
            max_score_similarity = similarity_score
            max_similarity_string = string
    if max_score_similarity>0.5:
        return max_similarity_string
    else:
        return 0

full_scholarship_data = {}

topics = ['Brief description:', 'Host Institution(s):', 'Level/Field(s) of study:',
            'Number of Awards:', 'Target group:', 'Scholarship value/inclusions/duration:',
            'Eligibility:', 'Application instructions:', 'Website:']

def clear_string(string):
    return string.encode('ascii', 'ignore').decode().replace('\n', '').replace('\r', '').replace('\t', '')

def search_function(data):
    id, link = data

    full_scholarship_data[id] = {}

    if id == 2043:
        full_scholarship_data[id] = {}
        return None

    URL = link
    page = requests.get(URL)
    soup = BeautifulSoup(page.content, 'html.parser')

    job_element = soup.find('div', class_ = 'entry clearfix')

    p_elements = job_element.find_all(['p', 'ul'])[3:]


    first_search = True
    search_results = []
    try:
        for el in p_elements:

            if str(el).find('<ul class="">') != -1:
                li_elements = el.find_all('li')
                for li_el in li_elements:
                    search_results.append(clear_string(li_el.text))
                continue

            similar_topic = similar(el.text, topics)
            
            if similar_topic != 0 and first_search:
                topic = similar_topic
                c = 0
                search_results = []
                first_search = False
            elif similar_topic != 0 and not first_search:
                full_scholarship_data[id][topic] = '\n'.join(search_results)

                topic = similar_topic
                search_results = []
                c += 1
            else:
                search_results.append(clear_string(el.text))

        if len(search_results) != 0:
            full_scholarship_data[id][topic] = '\n'.join(search_results)
    except:
        print(link)



if __name__ == '__main__':
    with open('./json_files/short_scholarship_data.json') as f:
        short_scholarship_data = json.load(f)
    
    list_to_search = []

    for key, value in short_scholarship_data.items():

        id = int(key)
        link = value['link']
        list_to_search.append((id, link))
    
    with ThreadPool(processes=8) as pool:
        pool.map(search_function, list_to_search)
    
    """for key, value in full_scholarship_data[id].items():
        print(key)
        print(value)
        print('*'*30)"""

    with open('./json_files/full_scholarship_data.json', 'w') as f:\
        json.dump(full_scholarship_data, f)


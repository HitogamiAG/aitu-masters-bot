import logging
import os
from urllib import request
from aiogram import Bot, Dispatcher, types, executor

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from db_utils import *
from db import delete_schema, create_schema
from upload_data import upload_data_main

from google_sheet_parser import get_past_meetups, get_meetup_schedule
from typing import List

from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from aiogram.utils.callback_data import CallbackData
from aiogram.utils.executor import start_webhook, set_webhook, Executor

from custom_request_handler import CustomWebhookRequestHandler
from aiogram.contrib.middlewares.logging import LoggingMiddleware

### MSF
#-----------------------------------
class Form(StatesGroup):
    counter = State()
    waiting_for_country = State()
    waiting_for_sorting = State()
    waiting_for_order = State()
    message_id_list = State()

storage = MemoryStorage()
#-----------------------------------

### Callback_data
full_info_cb = CallbackData('full_info_cb', 'action', 'scholarship_id')
wishlist_cb = CallbackData('wishlist_cb', 'action', 'scholarship_id')
delete_data_cb = CallbackData('delete_data_cb', 'action', 'user_id')
#-----------------------------------

### APIs
#-----------------------------------

TOKEN = os.environ.get('bot_token')
HEROKU_APP_NAME = os.environ.get('HEROKU_APP_NAME')
DATABASE_URL = os.environ.get('DATABASE_URL')

bot = Bot(token=TOKEN)
dp = Dispatcher(bot=bot, storage=storage)

HEROKU_APP_NAME = os.getenv('HEROKU_APP_NAME')
WEBHOOK_HOST = f'https://{HEROKU_APP_NAME}.herokuapp.com'
WEBHOOK_PATH = f'/webhook/{TOKEN}'
WEBHOOK_URL = f'{WEBHOOK_HOST}{WEBHOOK_PATH}'
WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = os.getenv('PORT', default=8000)

async def on_startup(dispatcher):
    try:
        await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    except:
        pass

async def on_shutdown(dispatcher):
    try:
        await bot.delete_webhook()
    except:
        pass

engine = create_engine(DATABASE_URL.replace('postgres', 'postgresql+psycopg2'), pool_size=9, max_overflow=0)
session = Session(bind=engine)
#-----------------------------------

### ONLY FOR HEROKU
delete_schema(engine=engine)
create_schema(engine=engine)
upload_data_main(session=session)

### Start
#-----------------------------------
@dp.message_handler(commands=['start', 'restart'])
async def start_handler(event: types.Message, state: FSMContext):

    async with state.proxy() as proxy:
        proxy.setdefault('counter', 0)
        proxy.setdefault('message_id_list', [])
        proxy['message_id_list'].append(event.message_id)
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons1 = ['Menu']

    keyboard.add(*buttons1)

    add_new_user(event.from_id, session)

    message = await event.answer(
        f"""Hello, {event.from_user.get_mention(as_html=True)}!
Click on menu button to start using our bot""",
        parse_mode=types.ParseMode.HTML,
        reply_markup=keyboard
    )
    async with state.proxy() as proxy:
        proxy['message_id_list'].append(message['message_id'])
#-----------------------------------

### Menu
#-----------------------------------
@dp.message_handler(lambda message: message.text == "Menu", state='*')
async def execute_last_search(event: types.Message, state: FSMContext):

    async with state.proxy() as proxy:
        try:
            proxy['message_id_list'] = await delete_messages_in_list(event.chat.id, proxy['message_id_list'])
        except:
            proxy['message_id_list'] = []
        proxy['message_id_list'].append(event.message_id)
        proxy['counter'] = 0

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons1 = ['Last Search', 'New Search']
    buttons2 = ['My wishlist', 'Get wishlist as pdf']
    buttons3 = ['Useful information from our channel']
    buttons4 = ['Meetup Schedule', 'Meetup link bank']
    buttons5 = ['Authors & Credentials']
    buttons6 = ['Delete all my data from database']

    keyboard.add(*buttons1)
    keyboard.add(*buttons2)
    keyboard.add(*buttons3)
    keyboard.add(*buttons4)
    keyboard.add(*buttons5)
    keyboard.add(*buttons6)

    message = await event.answer(
"""Brief instruction:
\N{right-pointing magnifying glass} New search - set parameters for new search
\N{left-pointing magnifying glass} Last search - execute last search
\N{white medium star} My wishlist - your favourite scholarships
\N{page facing up} Get wishlist as pdf - generate pdf file with your scholarships
\N{information source} Useful information - hot topics from channel
\N{calendar} Meetup Schedule - Information about planned meetups
\N{floppy disk} Meetup link bank - Links to records of past meetups

Commands:
\N{globe with meridians} /id <scholarship id> - get scholarship info by its id
\N{anticlockwise downwards and upwards open circle arrows} /start or /restart if you stucked""", parse_mode=None,
        reply_markup=keyboard
    )
    async with state.proxy() as proxy:
        proxy['message_id_list'].append(message.message_id)
#-----------------------------------

### Search execution
#-----------------------------------
@dp.message_handler(lambda message: message.text == "Last Search")
async def execute_last_search(event: types.Message, state: FSMContext):
    is_found, _ = find_previous_search_parameters(event.from_id, session=session)

    if is_found:
        async with state.proxy() as proxy:
            proxy['counter'] = 0
            proxy['message_id_list'].append(event.message_id)
            await search(proxy['counter'], event, proxy)
    else:
        message = await event.answer("We can't find your last search options, try new search!")

        async with state.proxy() as proxy:
            proxy['message_id_list'].append(event.message_id)
            proxy['message_id_list'].append(message.message_id)

    None

async def search(page, event, proxy):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    _, search_params = find_previous_search_parameters(event.from_id, session)

    try:
        results = execute_search(country=search_params.country, sorting=search_params.sorting,
                                ascending=search_params.ascending, start= 5 * page,
                                quantity=5, session=session)
    except:
        results = []

    if page == 0:
        buttons = ['Menu', 'Next search']
        keyboard.add(*buttons)
        to_callback_data = [res.scholarship_id for res in results]
        is_end = False
    elif results.count() == 0:
        buttons = ['Previous search', 'Menu']
        keyboard.add(*buttons)
        to_print = "It's the end of search." 
        is_end = True 
    elif page > 0:
        buttons1 = ['Previous search', 'Next search']
        buttons2 = ['Menu']
        keyboard.add(*buttons1)
        keyboard.add(*buttons2)
        to_callback_data = [res.scholarship_id for res in results]
        is_end = False
    
    if is_end:
        message = await event.answer(to_print, parse_mode = types.ParseMode.HTML, reply_markup = keyboard)
        proxy['message_id_list'].append(message.message_id)
    else:
        message = await event.answer(f'Page {page + 1}', parse_mode = types.ParseMode.HTML, reply_markup = keyboard)
        proxy['message_id_list'].append(message.message_id)

        for result, scholarship_id in zip(results, to_callback_data):
            message = await event.answer(
f"""
\N{left-pointing magnifying glass} ID: {result.scholarship_id}
\N{school} University: {result.university_title}
\N{link symbol} Link: <a href="{result.link}">link</a>
\N{clock face one-thirty} Deadline: {result.deadline}
\N{earth globe europe-africa} Country: {result.country}
\N{page facing up} Comment: {result.comment}
\N{white medium star} Rating: {result.rating}
""", disable_web_page_preview=True,
            parse_mode=types.ParseMode.HTML,
            reply_markup=types.InlineKeyboardMarkup(row_width=1)\
                .add(types.InlineKeyboardButton('Full Info',\
                    callback_data=full_info_cb.new(action = 'get_full_info', scholarship_id = scholarship_id))))
            proxy['message_id_list'].append(message.message_id)

@dp.message_handler(lambda message: message.text == "Next search")
async def next_search(event: types.Message, state: FSMContext):
    
    async with state.proxy() as proxy:
        proxy['counter'] += 1
        try:
            proxy['message_id_list'] = await delete_messages_in_list(event.chat.id, proxy['message_id_list'])
        except:
            proxy['message_id_list'] = []
        proxy['message_id_list'].append(event.message_id)
        await search(proxy['counter'], event, proxy)

@dp.message_handler(lambda message: message.text == "Previous search")
async def past_search(event: types.Message, state: FSMContext):
    
    async with state.proxy() as proxy:
        proxy['counter'] -= 1
        try:
            proxy['message_id_list'] = await delete_messages_in_list(event.chat.id, proxy['message_id_list'])
        except:
            proxy['message_id_list'] = []
        proxy['message_id_list'].append(event.message_id)
        await search(proxy['counter'], event, proxy)
#-----------------------------------

### Get full info about scholarship + add to wishlist
#-----------------------------------

@dp.callback_query_handler(full_info_cb.filter(action = 'get_full_info'), state='*')
async def show_full_info(query: types.CallbackQuery, callback_data: dict, state: FSMContext):
    scholarship_id = callback_data['scholarship_id']

    short_info, full_info = get_full_data(scholarship_id=scholarship_id, session=session)

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add('Get back')

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton('Add to wishlist', callback_data=wishlist_cb.new(action = 'add_to_wishlist', scholarship_id = short_info.scholarship_id)))

    async with state.proxy() as proxy:

        message = await query.message.answer(f'\N{pushpin} Title: {short_info.title}', reply_markup=keyboard)
        proxy['message_id_list'].append(message.message_id)

        message = await query.message.answer(
f"""
\N{left-pointing magnifying glass} ID: {short_info.scholarship_id}
\N{school} University: {short_info.university_title}
\N{link symbol} Link: <a href="{short_info.link}">link</a>
\N{clock face one-thirty} Deadline: {short_info.deadline}
\N{earth globe europe-africa} Country: {short_info.country}
\N{page facing up} Comment: {short_info.comment}
\N{white medium star} Rating: {short_info.rating}
\N{books} Description: {full_info.description}
\N{personal computer} Field of Study: {full_info.field}
\N{envelope} Amount of scholarships: {full_info.scholarship_amount}
\N{credit card} Scholarship value: {full_info.scholarship_value}
\N{graduation cap} Audithory: {full_info.audithory}
""", reply_markup=kb, disable_web_page_preview=True, parse_mode=types.ParseMode.HTML)
        proxy['message_id_list'].append(message.message_id)

@dp.callback_query_handler(wishlist_cb.filter(action = 'add_to_wishlist'), state='*')
async def insert_wishlist(query: types.CallbackQuery, callback_data: dict, state: FSMContext):

    result = add_to_wishlist(query.from_user.id, callback_data['scholarship_id'], session=session)

    if result:
        await bot.answer_callback_query(callback_query_id=query.id, text='Succesfully added to wishlist', show_alert=True)
    else:
        await bot.answer_callback_query(callback_query_id=query.id, text='This scholarship is already in your wishlist', show_alert=True)

@dp.message_handler(lambda message: message.text == "Get back")
async def get_back(event: types.Message, state: FSMContext):
    async with state.proxy() as proxy:

        try:
            proxy['message_id_list'] = await delete_messages_in_list(event.chat.id, proxy['message_id_list'])
        except:
            proxy['message_id_list'] = []
        proxy['message_id_list'].append(event.message_id)

        await search(proxy['counter'], event, proxy)
#-----------------------------------

### Search parameters
#-----------------------------------
@dp.message_handler(lambda message: message.text == "New Search")
async def execute_new_search(event: types.Message, state: FSMContext):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    country_list = get_country_list(session=session)
    for i, j in zip(country_list[0::2], country_list[1::2]):
        keyboard.add(*[i, j])
    if len(country_list) % 2 != 0:
        keyboard.add(country_list[-1])

    message = await event.answer("Choose location: ", reply_markup=keyboard)
    async with state.proxy() as proxy:
        proxy['message_id_list'].append(event.message_id)
        proxy['message_id_list'].append(message.message_id)

    await Form.waiting_for_country.set()

async def country_chosen(message: types.Message, state: FSMContext):
    await state.update_data(chosen_country = message.text)

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    keyboard.add('Alphabetical')
    keyboard.add('Popularity')
    keyboard.add('Deadline')

    message_2 = await message.answer('Выберите алго сорт:', reply_markup=keyboard)

    async with state.proxy() as proxy:
        proxy['message_id_list'].append(message.message_id)
        proxy['message_id_list'].append(message_2.message_id)

    await Form.waiting_for_sorting.set()

async def sorting_chosen(message: types.Message, state: FSMContext):
    await state.update_data(chosen_sorting = message.text)

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    keyboard.add('Ascending')
    keyboard.add('Descending')

    message_2 = await message.answer("Выберите порядок: ", reply_markup=keyboard)
    
    async with state.proxy() as proxy:
        proxy['message_id_list'].append(message.message_id)
        proxy['message_id_list'].append(message_2.message_id)

    await Form.waiting_for_order.set()

async def order_chosen(message: types.Message, state: FSMContext):
    await state.update_data(chosen_order = message.text)

    user_data = await state.get_data()

    message_2 = await message.answer('Saving your new parameters...')

    async with state.proxy() as proxy:
        proxy['message_id_list'].append(message.message_id)
        try:
            proxy['message_id_list'] = await delete_messages_in_list(message.chat.id, proxy['message_id_list'])
        except:
            proxy['message_id_list'] = []

    await state.finish()

    async with state.proxy() as proxy:
        proxy['counter'] = 0
        proxy['message_id_list'] = []
        proxy['message_id_list'].append(message_2.message_id)
        await update_search(message, user_data, proxy)

async def update_search(message: types.Message, user_data: dict, proxy):

    update_search_options(message.from_id, user_data['chosen_country'],
                          user_data['chosen_sorting'],
                          user_data['chosen_order'],
                          session)

    await search(0, message, proxy)
    return None

def register_handlers_food(dp: Dispatcher):
    dp.register_message_handler(execute_new_search, commands="start", state="*")
    dp.register_message_handler(country_chosen, state=Form.waiting_for_country)
    dp.register_message_handler(sorting_chosen, state=Form.waiting_for_sorting)
    dp.register_message_handler(order_chosen, state=Form.waiting_for_order)

#-----------------------------------

### Wishlist
#-----------------------------------
@dp.message_handler(lambda message: message.text == "My wishlist")
async def get_user_wishlist(event: types.Message, state: FSMContext):

    is_found = find_wishlist_results(event.from_id, session=session)

    if is_found:
        async with state.proxy() as proxy:
            proxy['counter'] = 0
            proxy['message_id_list'].append(event.message_id)
            await wishlist_search(proxy['counter'], event, proxy)

    else:
        message = await event.answer("Your wishlist is empty...")
        async with state.proxy() as proxy:
            proxy['message_id_list'].append(event.message_id)
            proxy['message_id_list'].append(message.message_id)

@dp.message_handler(lambda message: message.text == "Next wishlist")
async def next_wishlist(event: types.Message, state: FSMContext):
    
    async with state.proxy() as proxy:
        proxy['counter'] += 1
        try:
            proxy['message_id_list'] = await delete_messages_in_list(event.chat.id, proxy['message_id_list'])
        except:
            proxy['message_id_list'] = []
        proxy['message_id_list'].append(event.message_id)
        await wishlist_search(proxy['counter'], event, proxy)

@dp.message_handler(lambda message: message.text == "Previous wishlist")
async def past_wishlist(event: types.Message, state: FSMContext):
    
    async with state.proxy() as proxy:
        proxy['counter'] -= 1
        try:
            proxy['message_id_list'] = await delete_messages_in_list(event.chat.id, proxy['message_id_list'])
        except:
            proxy['message_id_list'] = []
        proxy['message_id_list'].append(event.message_id)
        await wishlist_search(proxy['counter'], event, proxy)
    
async def wishlist_search(page: int, event: types.Message, proxy: dict):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    short_info_res, full_info_res = get_wishlist(event.from_id, 3 * page, 3, session=session)

    if page == 0:
        buttons = ['Menu', 'Next wishlist']
        keyboard.add(*buttons)
        to_callback_data = [res.scholarship_id for res in short_info_res]
        is_end = False
    elif len(short_info_res) == 0:
        buttons = ['Previous wishlist', 'Menu']
        keyboard.add(*buttons)
        to_print = "It's the end of search." 
        is_end = True 
    elif page > 0:
        buttons1 = ['Previous wishlist', 'Next wishlist']
        buttons2 = ['Menu']
        keyboard.add(*buttons1)
        keyboard.add(*buttons2)
        to_callback_data = [res.scholarship_id for res in short_info_res]
        is_end = False
    
    proxy['message_id_list'].append(event.message_id)
    if is_end:
        message = await event.answer(to_print, parse_mode = types.ParseMode.HTML, reply_markup = keyboard)
        proxy['message_id_list'].append(message.message_id)
    else:
        message = await event.answer(f'Page {page + 1}', parse_mode = types.ParseMode.HTML, reply_markup = keyboard)
        proxy['message_id_list'].append(message.message_id)

        for short_info, full_info, scholarship_id in zip(short_info_res, full_info_res, to_callback_data):
            message = await event.answer(
f"""
\N{left-pointing magnifying glass} ID: {short_info.scholarship_id}
\N{pushpin} Title: {short_info.title}
\N{school} University: {short_info.university_title}
\N{link symbol} Link: <a href="{short_info.link}">link</a>
\N{clock face one-thirty} Deadline: {short_info.deadline}
\N{earth globe europe-africa} Country: {short_info.country}
\N{page facing up} Comment: {short_info.comment}
\N{white medium star} Rating: {short_info.rating}
\N{books} Description: {full_info.description}
\N{personal computer} Field of Study: {full_info.field}
\N{envelope} Amount of scholarships: {full_info.scholarship_amount}
\N{credit card} Scholarship value: {full_info.scholarship_value}
\N{graduation cap} Audithory: {full_info.audithory}
""", disable_web_page_preview=True,
            parse_mode=types.ParseMode.HTML,
            reply_markup=types.InlineKeyboardMarkup(row_width=1)\
                .add(types.InlineKeyboardButton('Delete from wishlist',\
                    callback_data=wishlist_cb.new(action = 'delete_from_wishlist', scholarship_id = scholarship_id))))
            proxy['message_id_list'].append(message.message_id)

@dp.callback_query_handler(wishlist_cb.filter(action = 'delete_from_wishlist'))
async def remove_from_wishlist(query: types.CallbackQuery, callback_data: dict):

    delete_from_wishlist(query.from_user.id, callback_data['scholarship_id'], session=session)
    await bot.answer_callback_query(callback_query_id=query.id, text='Succesfully deleted from wishlist', show_alert=True)

#-----------------------------------

### Get wishlist as pdf
#-----------------------------------
@dp.message_handler(lambda message: message.text == "Get wishlist as pdf")
async def get_wishlist_as_pdf(event: types.Message, state: FSMContext):
    to_send = generate_wishlist_pdf(event.from_id, session=session)
    await bot.send_document(event.from_id, to_send)
    async with state.proxy() as proxy:
        proxy['message_id_list'].append(event.message_id)
#-----------------------------------

### Useful info
#-----------------------------------
@dp.message_handler(lambda message: message.text == "Useful information from our channel")
async def get_useful_info(event: types.Message, state: FSMContext):

    results = get_links_to_channel(session=session)

    if len(results) == 0:
        message = await event.answer('Information not found...')
    else:
        to_print = '\n\n'.join([
            '\n'.join([f'\N{pushpin} Title: {result[0]}', f'\N{link symbol} Link: <a href="{result[1]}">link</a>']) for result in results
        ])
        message = await event.answer(to_print, parse_mode=types.ParseMode.HTML, disable_web_page_preview=True)

    async with state.proxy() as proxy:
        proxy['message_id_list'].append(event.message_id)
        proxy['message_id_list'].append(message.message_id)
#-----------------------------------

### Meetup Schedule
#-----------------------------------
@dp.message_handler(lambda message: message.text == "Meetup Schedule")
async def get_schedule(event: types.Message, state: FSMContext):
    message = await event.answer("Parsing schedule. Please, wait...")

    results = get_meetup_schedule()
    if len(results) != 0:
        to_print = '\n'.join([
f"""
\N{pushpin} Topic: {result['Topic']}
\N{smiling face with open mouth and smiling eyes} Person: {result['Person']}
\N{tear-off calendar} Date: {result['Date']}
\N{link symbol} Link: <a href="{result['Link']}">link</a>
\N{personal computer} Platform: {result['Platform']}
""" for result in results
    ])
    else:
        to_print = 'No scheduled events found...'

    message_2 = await event.answer(to_print, disable_web_page_preview=True, parse_mode=types.ParseMode.HTML)
    async with state.proxy() as proxy:
        proxy['message_id_list'].append(event.message_id)
        proxy['message_id_list'].append(message.message_id)
        proxy['message_id_list'].append(message_2.message_id)
#-----------------------------------

### Meetup link bank
#-----------------------------------
@dp.message_handler(lambda message: message.text == "Meetup link bank")
async def get_meetup_links(event: types.Message, state: FSMContext):
    message = await event.answer("Parsing link bank. Please, wait...")

    results = get_past_meetups()
    if len(results) != 0:
        to_print = '\n'.join([
f"""
\N{pushpin} Topic: {result['Topic']}
\N{smiling face with open mouth and smiling eyes} Person: {result['Person']}
\N{tear-off calendar} Date: {result['Date']}
\N{link symbol} Link: <a href="{result['Link']}">link</a>
\N{personal computer} Platform: {result['Platform']}
""" for result in results
    ])
    else:
        to_print = 'Past meetups not found...'

    message_2 = await event.answer(to_print, disable_web_page_preview=True, parse_mode=types.ParseMode.HTML)

    async with state.proxy() as proxy:
        proxy['message_id_list'].append(event.message_id)
        proxy['message_id_list'].append(message.message_id)
        proxy['message_id_list'].append(message_2.message_id)
#-----------------------------------

### Delete all my data from database
#-----------------------------------
@dp.message_handler(lambda message: message.text == "Delete all my data from database")
async def delete_all_user_data(event: types.Message, state: FSMContext):

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton('Button',
           callback_data=delete_data_cb.new(action = 'delete_all_user_data', user_id = event.from_id)))
    message = await event.answer('To delete your data put the button below', reply_markup=kb)
    async with state.proxy() as proxy:
        proxy['message_id_list'].append(event.message_id)
        proxy['message_id_list'].append(message.message_id)

@dp.callback_query_handler(delete_data_cb.filter(action = 'delete_all_user_data'), state='*')
async def delete_all_user_data(query: types.CallbackQuery, callback_data: dict, state: FSMContext):
    user_id = callback_data['user_id']
    delete_user_data_from_db(user_id, session=session)
    async with state.proxy() as proxy:
        try:
            proxy['message_id_list'] = await delete_messages_in_list(query.message.chat.id, proxy['message_id_list'])
        except:
            proxy['message_id_list'] = []
    await bot.answer_callback_query(callback_query_id=query.id, text='All your data was deleted. Please, type /start or /restart to launch bot again', show_alert=True)
#-----------------------------------

### Authors & Credentials
#-----------------------------------

@dp.message_handler(lambda message: message.text == 'Authors & Credentials')
async def print_credentials(event: types.Message, state: FSMContext):
    message = await event.answer(
"""
\N{high-speed train} Aitu masters chat: <a href="https://t.me/+WKjQ9KQr7cI5YmM6">Chat</a>
\N{high-speed train with bullet nose} Aitu masters channel: <a href="https://t.me/mastersAbroadd">Channel</a>

\N{smoking symbol} Bot created by Alexandr @HitogamiAG Gavrilko
\N{hot beverage} Scholarship data validated by Ayan @IamStillTryin Duisenov

\N{personal computer} Bot GitHub Repo: 
\N{credit card} Support us: 
""", parse_mode=types.ParseMode.HTML, disable_web_page_preview=True)
    async with state.proxy() as proxy:
        proxy['message_id_list'].append(event.message_id)
        proxy['message_id_list'].append(message.message_id)

#-----------------------------------

### Get scholarship by id
#-----------------------------------
@dp.message_handler(commands=['id'])
async def get_scholarship_by_id_alone(event: types.Message, state: FSMContext):
    id = int(event.get_args().split()[0])
    result = get_scholarship_by_id(id, session)
    if result:
        kb = types.InlineKeyboardMarkup(row_width=1)\
            .add(types.InlineKeyboardButton('Full Info',\
                        callback_data=full_info_cb.new(action = 'get_full_info_alone', scholarship_id = id)))

        message = await event.answer(
    f"""
    \N{left-pointing magnifying glass} ID: {result.scholarship_id}
    \N{school} University: {result.university_title}
    \N{link symbol} Link: <a href="{result.link}">link</a>
    \N{clock face one-thirty} Deadline: {result.deadline}
    \N{earth globe europe-africa} Country: {result.country}
    \N{page facing up} Comment: {result.comment}
    \N{white medium star} Rating: {result.rating}
    """, reply_markup=kb, disable_web_page_preview=True, parse_mode=types.ParseMode.HTML)
    else:
        message = await event.answer(f'Scholarship with id {id} not found...')
    async with state.proxy() as proxy:
        proxy['message_id_list'].append(event.message_id)
        proxy['message_id_list'].append(message.message_id)

@dp.callback_query_handler(full_info_cb.filter(action = 'get_full_info_alone'), state='*')
async def show_full_info_alone(query: types.CallbackQuery, callback_data: dict, state: FSMContext):
    scholarship_id = callback_data['scholarship_id']

    short_info, full_info = get_full_data(scholarship_id=scholarship_id, session=session)

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton('Add to wishlist', callback_data=wishlist_cb.new(action = 'add_to_wishlist', scholarship_id = short_info.scholarship_id)))

    async with state.proxy() as proxy:
        message = await query.message.answer(
f"""
\N{left-pointing magnifying glass} ID: {short_info.scholarship_id}
\N{school} University: {short_info.university_title}
\N{link symbol} Link: <a href="{short_info.link}">link</a>
\N{clock face one-thirty} Deadline: {short_info.deadline}
\N{earth globe europe-africa} Country: {short_info.country}
\N{page facing up} Comment: {short_info.comment}
\N{white medium star} Rating: {short_info.rating}
\N{books} Description: {full_info.description}
\N{personal computer} Field of Study: {full_info.field}
\N{envelope} Amount of scholarships: {full_info.scholarship_amount}
\N{credit card} Scholarship value: {full_info.scholarship_value}
\N{graduation cap} Audithory: {full_info.audithory}
""", reply_markup=kb, disable_web_page_preview=True, parse_mode=types.ParseMode.HTML)
        proxy['message_id_list'].append(message.message_id)

#-----------------------------------

### Message cleaner
#-----------------------------------
async def delete_messages_in_list(chat_id, msg_list: List):

    if msg_list.__len__ != 0:
        for msg_id in msg_list:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except:
                pass

    return []

#-----------------------------------

if __name__ == '__main__':
    register_handlers_food(dp)
    
    # Comment to run locally
    logging.basicConfig(level=logging.DEBUG)
    dp.middleware.setup(LoggingMiddleware())
    executor = Executor(dp, skip_updates=True)
    executor.on_startup(on_startup)
    executor.on_shutdown(on_shutdown)
    executor.start_webhook(webhook_path=WEBHOOK_PATH, request_handler=CustomWebhookRequestHandler, host = WEBAPP_HOST,
        port = WEBAPP_PORT)

    # Uncomment to run locally
    #executor.start_polling(dp, skip_updates=True)
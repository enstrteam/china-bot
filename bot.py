
import telebot
import datetime, time
import os
import csv
import openpyxl
import pandas as pd
import json
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from pycbrf import ExchangeRates, Banks
from dotenv import load_dotenv


load_dotenv()

token = os.getenv('TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')

bot =telebot.TeleBot(token)

START_MSG = """Привет! Это бот магазина <a href="https://192.168.0.1">CHINA.SHOP</a>, он быстро рассчитает стоимость вещи в рублях. 

Спасибо что обратились)"""

START_PICTURE_URL = 'hello.jpg'


def json_load(filename):
    with open(filename, 'r') as json_file:
        data = json.load(json_file)
        return data

data = json_load('data.json')

CATEGORIES = data['categories']
PROMO = data['promo']


def get_exchange_rates():
    today = datetime.date.today().isoformat()
    rates = ExchangeRates(today)
    return float(rates['CNY'].rate)

EXCHANGE_RATE = get_exchange_rates()


@bot.message_handler(commands=['start'])
def start_message(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('Калькулятор цены', callback_data='calc'))
    markup.add(types.InlineKeyboardButton('Отзывы 📢', url="http://192.168.0.1"))
    markup.add(types.InlineKeyboardButton('Другие наши источники 📌', callback_data='other'))
    with open(START_PICTURE_URL, 'rb') as f:
        image = f.read()
    bot.send_photo(message.chat.id, photo=image, caption=START_MSG, parse_mode='html', reply_markup=markup)

@bot.message_handler(commands=['excel'])
def export_to_excel(message):
    if message.from_user.id == ADMIN_ID:
        read_csv = pd.read_csv('database.csv')
        read_csv.to_excel('database.xlsx', index=False)
        with open('database.xlsx', 'rb') as f:
            bot.send_document(message.chat.id, f)
        bot.send_message(message.chat.id, 'Excel export success')
        
    

@bot.callback_query_handler(func=lambda callback:True)
def callback_handler(callback):
    if callback.data == 'calc':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('POIZON, Taobao 🇨🇳', callback_data='store'))
        markup.add(types.InlineKeyboardButton('Другое 🌐', callback_data='other_store'))
        bot.send_message(callback.message.chat.id, 'Выберите платформу для расчета стоимости', reply_markup=markup)
    if callback.data == 'store':
        markup = types.InlineKeyboardMarkup()
        for key,value in CATEGORIES.items():
            markup.add(types.InlineKeyboardButton(value['name'], callback_data=key))
        bot.send_message(callback.message.chat.id, 'Выберите категорию товара, от правильного выбора зависит конечная цена.', reply_markup=markup)
    if callback.data in CATEGORIES.keys():
        category = callback.data
        bot.send_message(callback.message.chat.id, f'Вы выбрали категорию: {CATEGORIES[callback.data]["name"]} {category}. Введите промокод.')
        # bot.register_next_step_handler_by_chat_id(callback.message.chat.id, cost_handler, args=[category])
        bot.register_next_step_handler_by_chat_id(callback.message.chat.id, promo_handler, args=[category])


def promo_handler(message,args):
    promo = message.text.strip()
    if promo in PROMO:
        bot.send_message(message.chat.id, 'Введите стоимость товара:')
        bot.register_next_step_handler(message, cost_handler, args=[*args, promo])
    else:
        bot.send_message(message.chat.id, 'Введите стоимость товара:')
        bot.register_next_step_handler(message, cost_handler, args=args)


def cost_handler(message, args):
    try:
        cost = float(message.text.strip())
    except ValueError:
        bot.send_message(message.chat.id, 'Введите число')
        bot.register_next_step_handler(message, cost_handler, args=args)
        return
    
    if cost < 0:
        bot.send_message(message.chat.id, 'Введите положительную сумму')
        bot.register_next_step_handler(message, cost_handler, args=args)
        return

    category_id = args[0]
    category = CATEGORIES[category_id]["name"]
    margin = CATEGORIES[category_id]["margin"]
    promo=""

    if len(args)>1:
        promo = args[1]
        promo_rate = PROMO[promo]
    else:
        promo_rate = 1
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('Еще расчет! 🔄', callback_data='calc'))
    markup.add(types.InlineKeyboardButton('Заказать! 👑', callback_data='order'))
    bot.send_message(message.chat.id, f'Итого <b>{round(cost * margin * promo_rate * EXCHANGE_RATE)}</b> руб. с учетом всех расходов.\nДля информации:\nКомиссия сервиса составила: {round(cost* (margin * promo_rate-1) * EXCHANGE_RATE)}\nКурс юаня: {EXCHANGE_RATE}\nКатегория: {category}',parse_mode='html', reply_markup=markup)

    with open('database.csv', 'a', encoding="UTF8") as f:
        writer = csv.writer(f, delimiter=',', lineterminator='\n')
        writer.writerow([message.from_user.id, message.from_user.username, f'{message.from_user.first_name} {message.from_user.last_name}', cost, category, promo, time.strftime("%Y-%m-%d %H:%M:%S",time.localtime())])

bot.polling()
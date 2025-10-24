import json
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.types.input_file import FSInputFile
from random import randrange
from dotenv import load_dotenv

# Через api буду получать дату, день недели, гороскоп или около того (мб какой сегодня праздник)
# Мб добавить что-то типа "анекдот дня"


load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
create_hw_post = False

with open("data/messages.json", "r", encoding="utf-8") as f:
    TEXTS = json.load(f)

with open("data/answers.json", "r", encoding="utf-8") as f:
    ANSWERS = json.load(f)


def create_hw_post_message(subject, hw_text, deadline):
    return "LOL"


@dp.message(CommandStart())
async def start(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Сообщение дня"),
             KeyboardButton(text="Создать пост с ДЗ"),
             KeyboardButton(text="Обновить список ДЗ"),
             KeyboardButton(text="Показать расписание"),
             KeyboardButton(text="Напоминание о делайнах"),
             KeyboardButton(text="Помощь")
             ]
        ],
        resize_keyboard=True
    )
    await message.answer(ANSWERS['start'])


@dp.message(F.text.in_(["/help", "Помощь"]))
async def help(message: types.Message):
    await message.answer(ANSWERS['help'])


@dp.message(F.text.in_(["Сообщение дня", '/day_message']))
async def day_message(message: types.Message):
    await message.answer(ANSWERS['day_message'][randrange(0, len(ANSWERS['day_message']))])
    # Добавить сюда получение гороскопа или чего-то прикольного через запрос на сервер


@dp.message(F.text.in_(["Создать пост с ДЗ", '/hw_post']))
async def hw_post(message: types.Message):
    global create_hw_post
    create_hw_post = True
    await message.answer(ANSWERS['create_hw_post'])


@dp.message(F.text.in_(["<UNK>"]))
async def unk(message: types.Message):
    ans = ANSWERS['unk']
    if create_hw_post:
        subject, hw_text, deadline = message.text.split("\n")
        ans = create_hw_post_message(subject, hw_text, deadline)
    await message.answer(ans)


@dp.message(F.text.in_(["Обновить список ДЗ", "/update_hw_post"]))
async def update_hw_post(message: types.Message):
    pass


@dp.message(F.text.in_(["Показать расписание", "/show schedule"]))
async def show_schedule(message: types.Message):
    await message.answer(ANSWERS['show_schedule'])
    # Пробегаемся циклом по всему расписанию, выделяем ни недели жирным шрифтом, расписание делаем с форматированными ссылками


@dp.message(F.text.in_(["Напоминание о делайнах", "/deadline_announce"]))
async def deadline_announce(message: types.Message):
    await message.answer(ANSWERS['deadline_announce'])
    # Пробегаюсь по дедлайнам и проверяю, какие есть ближайшие 3 дня, делю их по секциям и создаю пост


if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
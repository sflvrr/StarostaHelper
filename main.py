import json
import os
import html
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from random import choice
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()
TZ = ZoneInfo("Europe/Vienna")
WEEKDAY_RU = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())

with open("data/messages.json", "r", encoding="utf-8") as f:
    TEXTS = json.load(f)
with open("data/answers.json", "r", encoding="utf-8") as f:
    ANSWERS = json.load(f)

create_hw_post = False

def escape_md(text: str) -> str:
    return html.escape(text or "")

def read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def write_json(path: str, data) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def human_date(dt: datetime) -> str:
    months = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"]
    weekdays = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    return f"{dt.day} {months[dt.month-1]} {dt.year}, {weekdays[(dt.weekday())]} {dt:%H:%M}"

def format_link(text: str, link: str | None) -> str:
    if link:
        return f'<a href="{escape_md(link)}">{escape_md(text)}</a>'
    return escape_md(text)

def greeting_by_time(dt: datetime) -> str:
    h = dt.hour
    if 5 <= h <= 10:
        return "Доброе утро"
    if 11 <= h <= 16:
        return "Добрый день"
    return "Добрый вечер"

def current_iso_week_key(d: date) -> str:
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"

def days_keyboard() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="Пн"), KeyboardButton(text="Вт"), KeyboardButton(text="Ср")],
        [KeyboardButton(text="Чт"), KeyboardButton(text="Пт"), KeyboardButton(text="Сб")],
        [KeyboardButton(text="Вс")]
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

DEADLINES_PATH = "data/deadlines.json"

def load_deadlines() -> list[dict]:
    return read_json(DEADLINES_PATH, [])

def save_deadlines(items: list[dict]) -> bool:
    return write_json(DEADLINES_PATH, items)

def parse_due_dt(due_str: str | None) -> datetime | None:
    if not due_str:
        return None
    try:
        dt = datetime.fromisoformat(due_str)
        return dt.replace(tzinfo=dt.tzinfo or TZ).astimezone(TZ)
    except Exception:
        try:
            d = datetime.strptime(due_str, "%Y-%m-%d").date()
            return datetime(d.year, d.month, d.day, 23, 59, tzinfo=TZ)
        except Exception:
            return None

def prune_old_deadlines(grace_days: int = 3) -> int:
    items = load_deadlines()
    if not items:
        return 0
    now = datetime.now(TZ)
    keep = []
    removed = 0
    for it in items:
        due = parse_due_dt(it.get("due"))
        if not due:
            removed += 1
            continue
        if now - due > timedelta(days=grace_days):
            removed += 1
        else:
            keep.append(it)
    if removed:
        save_deadlines(keep)
    return removed

def format_deadline_line(item: dict) -> str:
    title = item.get("title", "Задание")
    subj = item.get("subject", "")
    link = item.get("link")
    due = parse_due_dt(item.get("due"))
    when = due.strftime("%H:%M") if due else "?"
    subj_fmt = f" <i>({escape_md(subj)})</i>" if subj else ""
    return f"• {format_link(title, link)}{subj_fmt} — <b>{when}</b>"

def get_deadlines_for_date(d: date) -> list[str]:
    items = load_deadlines()
    lines = []
    for it in items:
        due = parse_due_dt(it.get("due"))
        if due and due.date() == d:
            lines.append(format_deadline_line(it))
    def tkey(line: str):
        try:
            hhmm = line.rsplit("—", 1)[-1].strip()
            hhmm = hhmm.strip("<b>").strip("</b>")
            return datetime.strptime(hhmm, "%H:%M").time()
        except Exception:
            return datetime.strptime("99:99", "%H:%M").time()
    lines.sort(key=tkey)
    return lines

FACTS_PATH = "data/facts.json"

def load_facts() -> list[str]:
    return read_json(FACTS_PATH, [])

def get_random_fact() -> str:
    facts = load_facts()
    if not facts:
        return "Интересный факт недоступен."
    return choice(facts)

def load_specials():
    return read_json("data/special_lectures.json", {"added": {}, "deleted": {}})

def normalize_items(items: list[dict]) -> list[dict]:
    return [{
        "time": (it.get("time") or "").strip(),
        "title": (it.get("title") or "").strip(),
        "link": it.get("link")
    } for it in (items or [])]

def apply_specials_for_date(base_items: list[dict], date_str: str, specials: dict) -> list[dict]:
    base = normalize_items(base_items)
    added = normalize_items((specials.get("added", {}) or {}).get(date_str, []))
    deleted = normalize_items((specials.get("deleted", {}) or {}).get(date_str, []))
    def key(it): return (it.get("time",""), it.get("title",""))
    deleted_keys = {key(x) for x in deleted}
    base = [it for it in base if key(it) not in deleted_keys]
    combined = base + added
    def sort_key(it):
        try:
            return datetime.strptime(it.get("time","99:99"), "%H:%M").time()
        except Exception:
            return datetime.strptime("99:99", "%H:%M").time()
    combined.sort(key=sort_key)
    return combined

def collect_today_schedule_lines() -> list[str]:
    schedule = read_json("data/schedule.json", {})
    specials = load_specials()
    today = datetime.now(TZ).date()
    date_str = today.isoformat()
    base_items = []
    if schedule:
        week_key = current_iso_week_key(today)
        weekday_key = WEEKDAY_RU[today.weekday()]
        for day_block in schedule.get(week_key, []):
            if day_block.get("day") == weekday_key:
                base_items = day_block.get("items", [])
                break
    effective = apply_specials_for_date(base_items, date_str, specials)
    return [
        f"{escape_md(it.get('time',''))} — {format_link(it.get('title','Занятие'), it.get('link'))}"
        for it in effective
    ]

async def build_day_message_v2() -> str:
    now = datetime.now(TZ)
    greeting = greeting_by_time(now)
    today_lines = collect_today_schedule_lines()
    schedule_block = "<b>Сегодня у нас:</b>\n" + (
        "\n".join(f"• {line}" for line in today_lines) if today_lines
        else "• Похоже, на сегодня пар в расписании нет 🙂"
    )
    fact_line = get_random_fact()
    fact_block = f"<b>Факт дня:</b>\n{escape_md(fact_line)}"
    today = now.date()
    tomorrow = today + timedelta(days=1)
    today_deadlines = get_deadlines_for_date(today)
    tomorrow_deadlines = get_deadlines_for_date(tomorrow)
    if today_deadlines:
        today_dl_block = "<b>Сегодня такие дедлайны:</b>\n\n" + "\n\n".join(today_deadlines)
    else:
        today_dl_block = "Сегодня дедлайнов нет"
    if tomorrow_deadlines:
        tomorrow_dl_block = "\n<b>Завтра дедлайны:</b>\n\n" + "\n\n".join(tomorrow_deadlines)
    else:
        tomorrow_dl_block = "\nНа завтра дедлайнов нет" if today_deadlines else "\nНа завтра дедлайнов тоже нет"
    header = f"<b>Всем {greeting}!</b>"
    footer = "<b>Всем хорошего и продуктивного дня!</b>"
    return (
        f"{header}\n\n"
        f"{schedule_block}\n\n"
        f"{today_dl_block}\n"
        f"{tomorrow_dl_block}\n\n"
        f"{fact_block}\n\n"
        f"{footer}"
    )

def create_hw_post_message(subject: str, hw_text: str, deadline: str) -> str:
    subject = subject.strip().lstrip("#:>- ")
    hw_text = hw_text.strip()
    deadline_text = deadline.strip()
    due_show = deadline_text
    try:
        try:
            due_dt = datetime.fromisoformat(deadline_text).astimezone(TZ)
        except ValueError:
            due_dt = datetime.strptime(deadline_text, "%Y-%m-%d").replace(tzinfo=TZ)
        due_show = human_date(due_dt)
    except Exception:
        pass
    return (
        f"<b>ДЗ по {escape_md(subject)}!</b>\n"
        f"{escape_md(hw_text)}\n"
        f"<code>Дедлайн: {escape_md(due_show)}</code>"
    )

@dp.message(CommandStart())
async def start(message: types.Message):
    removed = prune_old_deadlines(grace_days=3)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Сообщение дня"),
             KeyboardButton(text="Создать пост с ДЗ")],
            [KeyboardButton(text="Обновить список ДЗ"),
             KeyboardButton(text="Показать расписание")],
            [KeyboardButton(text="Помощь")]
        ],
        resize_keyboard=True
    )
    msg = ANSWERS['start']
    if removed:
        msg += f"\n\n(Удалено просроченных дедлайнов: {removed})"
    await message.answer(msg, reply_markup=kb)

@dp.message(F.text.in_(["/help", "Помощь"]))
async def help(message: types.Message):
    await message.answer(ANSWERS['help'])

@dp.message(F.text.in_(["Сообщение дня", "/day_message"]))
async def day_message(message: types.Message):
    prune_old_deadlines(grace_days=3)
    text = await build_day_message_v2()
    await message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@dp.message(F.text.in_(["Создать пост с ДЗ", "/hw_post"]))
async def hw_post(message: types.Message):
    items = load_deadlines()
    if not items:
        await message.answer("Пока нет ни одного ДЗ 🎉")
        return
    def due_key(it):
        dt = parse_due_dt(it.get("due"))
        return dt or datetime.max.replace(tzinfo=TZ)
    items.sort(key=due_key)
    blocks = []
    for it in items:
        subject = it.get("subject") or "Предмет"
        text = it.get("title") or "Задание"
        due_str = it.get("due") or ""
        blocks.append(create_hw_post_message(subject, text, due_str))
    post = "\n\n" + "<b>Актуальные ДЗ</b>\n\n" + "\n\n".join(blocks)
    await message.answer(post, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@dp.message(F.text.in_(["Обновить список ДЗ", "/update_hw_post"]))
async def update_hw_post(message: types.Message):
    global create_hw_post
    create_hw_post = True
    await message.answer(
        "Пришлите 3 строки:\n"
        "1) Предмет\n2) Текст ДЗ\n3) Дедлайн (YYYY-MM-DD или YYYY-MM-DD HH:MM)\n\n"
        "Пример:\n"
        "Дискретная математика\nРазобрать 5 задач из листка #3\n2025-10-27 23:59"
    )

@dp.message(F.text.in_(["Показать расписание", "/show schedule"]))
async def show_schedule(message: types.Message):
    schedule = read_json("data/schedule.json", {})
    if not schedule:
        await message.answer("Расписание пока пустое. Загрузите data/schedule.json.")
        return
    parts = ["<b>Расписание</b>"]
    for week in sorted(schedule.keys()):
        parts.append(f"\n<b>{escape_md(week)}</b>")
        for day_block in schedule[week]:
            day_name = day_block.get("day", "?")
            items = day_block.get("items", [])
            if not items:
                continue
            lines = []
            for it in items:
                tm = escape_md(it.get("time", ""))
                title = it.get("title", "Занятие")
                link = it.get("link")
                lines.append(f"{tm} — {format_link(title, link)}")
            parts.append(f"<u>{escape_md(day_name)}</u>\n" + "\n".join(lines))
    await message.answer("\n".join(parts), parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@dp.message()
async def unk(message: types.Message):
    global create_hw_post
    ans = ANSWERS.get('unk', "Я вас не понял :(")
    if create_hw_post:
        try:
            lines = [l for l in (message.text or "").split("\n") if l.strip()]
            if len(lines) < 3:
                raise ValueError("Нужно 3 строки (предмет, текст, дедлайн).")
            subject, hw_text, deadline = lines[0], "\n".join(lines[1:-1]), lines[-1]
            data = load_deadlines()
            data.append({"title": hw_text, "subject": subject, "due": deadline})
            save_deadlines(data)
            ans = create_hw_post_message(subject, hw_text, deadline)
            create_hw_post = False
            await message.answer(ans, parse_mode=ParseMode.HTML)
            return
        except Exception as e:
            await message.answer(f"Ошибка ввода: {e}\nПопробуйте ещё раз тем же форматом.")
            return
    await message.answer(ans)

if __name__ == "__main__":
    prune_old_deadlines(grace_days=3)
    asyncio.run(dp.start_polling(bot))
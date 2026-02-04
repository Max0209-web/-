import asyncio
import os
import json
import secrets
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from supabase import create_client, Client
import logging

logging.basicConfig(level=logging.INFO)

# Конфигурация
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8524212627:AAGaH7zqqpPdo6ZMVryA62TcjLOvSG6aDY4')
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://rgsshworixeptoivrqlr.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'sb_publishable_2ly2CVhHRMrd_T_MHAk7Uw_pqfSCZGC')
WEB_APP_URL = os.getenv('WEB_APP_URL', 'https://max0209-web.github.io/-/')

# Инициализация
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_main_keyboard(family_id=None):
    keyboard = []
    if family_id:
        webapp_url = f"{WEB_APP_URL}/?family={family_id}"
        keyboard.append([KeyboardButton(text="📱 Календарь", web_app=WebAppInfo(url=webapp_url))])
        keyboard.append([KeyboardButton(text="➕ Быстро добавить")])
        keyboard.append([KeyboardButton(text="👨‍👩‍👧‍👦 Семья"), KeyboardButton(text="📅 Сегодня")])
    else:
        keyboard.append([KeyboardButton(text="👨‍👩‍👧‍👦 Создать семью")])
        keyboard.append([KeyboardButton(text="🔗 Присоединиться")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

async def get_user_family(user_id):
    result = supabase.table('users').select('family_id, families(name, code)').eq('telegram_id', user_id).execute()
    if result.data:
        return result.data[0]['family_id'], result.data[0]['families']
    return None, None

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    family_id, family_data = await get_user_family(user_id)
    
    if family_id:
        await message.answer(
            f"👋 Добро пожаловать в семью '{family_data['name']}'!\n\n"
            f"Все заметки видны всем членам семьи.\n"
            f"Используйте веб-календарь для удобного просмотра!",
            reply_markup=get_main_keyboard(family_id)
        )
    else:
        await message.answer(
            "👋 Привет! Я помогу вашей семье координировать расписание.\n\n"
            "📌 Все заметки видны всем членам семьи\n"
            "📱 Есть удобный веб-календарь\n"
            "🔔 Автоматические напоминания\n\n"
            "Создайте семью или присоединитесь:",
            reply_markup=get_main_keyboard()
        )

@dp.message(lambda message: message.text == "👨‍👩‍👧‍👦 Создать семью")
async def create_family(message: types.Message):
    family_code = secrets.token_hex(4).upper()
    family_id = f"family_{secrets.token_hex(8)}"
    
    supabase.table('families').insert({
        'id': family_id,
        'name': f"Семья {message.from_user.first_name}",
        'code': family_code,
        'theme_color': '#4CAF50'
    }).execute()
    
    supabase.table('users').insert({
        'telegram_id': message.from_user.id,
        'username': message.from_user.username,
        'full_name': message.from_user.full_name,
        'family_id': family_id,
        'role': 'admin',
        'avatar_color': '#2196F3'
    }).execute()
    
    webapp_url = f"{WEB_APP_URL}/?family={family_id}"
    
    await message.answer(
        f"🎉 Семья создана!\n\n"
        f"🏠 Название: Семья {message.from_user.first_name}\n"
        f"🔑 Код: <code>{family_code}</code>\n\n"
        f"📱 Ссылка на календарь:\n"
        f"<code>{webapp_url}</code>\n\n"
        f"Поделитесь кодом с членами семьи!",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(family_id)
    )

@dp.message(lambda message: message.text == "🔗 Присоединиться")
async def join_family_start(message: types.Message):
    await message.answer("Введите код семьи:")

@dp.message(lambda message: message.text and len(message.text) == 8)
async def join_family_process(message: types.Message):
    family_code = message.text.upper()
    
    result = supabase.table('families').select('id, name').eq('code', family_code).execute()
    
    if not result.data:
        await message.answer("❌ Семьи с таким кодом не найдено.")
        return
    
    family = result.data[0]
    
    supabase.table('users').insert({
        'telegram_id': message.from_user.id,
        'username': message.from_user.username,
        'full_name': message.from_user.full_name,
        'family_id': family['id'],
        'role': 'member',
        'avatar_color': '#FF9800'
    }).execute()
    
    webapp_url = f"{WEB_APP_URL}/?family={family['id']}"
    
    await message.answer(
        f"🎉 Вы присоединились к семье '{family['name']}'!\n\n"
        f"📱 Ссылка на календарь:\n"
        f"<code>{webapp_url}</code>\n\n"
        f"Теперь все заметки семьи будут видны вам!",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(family['id'])
    )

@dp.message(lambda message: message.text == "➕ Быстро добавить")
async def quick_add_start(message: types.Message):
    family_id, _ = await get_user_family(message.from_user.id)
    
    if not family_id:
        await message.answer("Сначала присоединитесь к семье!")
        return
    
    await message.answer("Введите название события одним сообщением:\n\nПример: 'Забрать детей 18:00'")

@dp.message(lambda message: len(message.text) > 5 and ' ' in message.text)
async def quick_add_process(message: types.Message):
    family_id, family_data = await get_user_family(message.from_user.id)
    
    if not family_id:
        return
    
    text = message.text
    words = text.split()
    
    time_part = None
    title_parts = []
    
    for word in words:
        if ':' in word and word.replace(':', '').isdigit():
            time_part = word
        else:
            title_parts.append(word)
    
    if not time_part:
        await message.answer("Укажите время в формате ЧЧ:ММ")
        return
    
    title = ' '.join(title_parts)
    today = datetime.now().strftime('%Y-%m-%d')
    
    note_data = {
        'family_id': family_id,
        'user_id': message.from_user.id,
        'title': title,
        'note_date': today,
        'note_time': time_part,
        'color_tag': '#4CAF50'
    }
    
    supabase.table('notes').insert(note_data).execute()
    
    family_members = supabase.table('users').select('telegram_id').eq('family_id', family_id).execute()
    
    for member in family_members.data:
        if member['telegram_id'] != message.from_user.id:
            try:
                await bot.send_message(
                    member['telegram_id'],
                    f"📢 Новая заметка от {message.from_user.full_name}:\n"
                    f"📌 {title}\n"
                    f"📅 Сегодня ⏰ {time_part}"
                )
            except:
                pass
    
    await message.answer(f"✅ Заметка добавлена для всей семьи!")

@dp.message(lambda message: message.text == "📅 Сегодня")
async def show_today(message: types.Message):
    family_id, family_data = await get_user_family(message.from_user.id)
    
    if not family_id:
        return
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    result = supabase.table('notes').select('*, users(full_name, avatar_color)').eq('family_id', family_id).eq('note_date', today).order('note_time').execute()
    
    if not result.data:
        await message.answer("🎉 На сегодня событий нет!")
        return
    
    response = f"📅 Заметки на сегодня:\n\n"
    
    for note in result.data:
        time_str = note['note_time'][:5] if isinstance(note['note_time'], str) else str(note['note_time'])
        author = note['users']['full_name'] if note['users'] else 'Неизвестно'
        
        response += f"⏰ {time_str} - {note['title']}\n"
        response += f"👤 {author}\n\n"
    
    await message.answer(response)

@dp.message(lambda message: message.text == "👨‍👩‍👧‍👦 Семья")
async def show_family(message: types.Message):
    family_id, family_data = await get_user_family(message.from_user.id)
    
    if not family_id:
        return
    
    members = supabase.table('users').select('full_name, role').eq('family_id', family_id).execute()
    
    response = f"🏠 Семья: {family_data['name']}\n"
    response += f"🔑 Код: {family_data['code']}\n\n"
    response += f"👥 Участники ({len(members.data)}):\n"
    
    for member in members.data:
        role_icon = "👑" if member['role'] == 'admin' else "👤"
        response += f"{role_icon} {member['full_name']}\n"
    
    await message.answer(response)

async def send_reminders():
    today = datetime.now().strftime('%Y-%m-%d')
    current_time = datetime.now().strftime('%H:%M')
    
    result = supabase.table('notes').select('*, families(name), users(telegram_id, full_name)').eq('note_date', today).execute()
    
    for note in result.data:
        note_time = note['note_time'][:5] if isinstance(note['note_time'], str) else str(note['note_time'])
        
        if note_time <= current_time:
            family_name = note['families']['name'] if note['families'] else 'Семья'
            author_name = note['users']['full_name'] if note['users'] else 'Неизвестно'
            
            members = supabase.table('users').select('telegram_id').eq('family_id', note['family_id']).execute()
            
            for member in members.data:
                try:
                    await bot.send_message(
                        member['telegram_id'],
                        f"🔔 НАПОМИНАНИЕ\n\n"
                        f"📌 {note['title']}\n"
                        f"⏰ {note_time}\n"
                        f"👤 {author_name}"
                    )
                except:
                    pass

async def reminder_scheduler():
    while True:
        await asyncio.sleep(60)
        await send_reminders()

async def main():
    asyncio.create_task(reminder_scheduler())
    
    print("🤖 Бот запущен с Supabase!")
    print(f"🌐 Web App: {WEB_APP_URL}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

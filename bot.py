import asyncio
import logging
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    WebAppInfo,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import Database
import hashlib

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота
API_TOKEN = 'YOUR_BOT_TOKEN'
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database()
scheduler = AsyncIOScheduler()

# URL вашего Web App (нужно будет настроить)
WEB_APP_URL = "https://your-domain.com/family-calendar-webapp"

# Состояния FSM
class JoinFamily(StatesGroup):
    waiting_for_code = State()

class CreateFamily(StatesGroup):
    waiting_for_name = State()

# Клавиатуры
def get_main_keyboard(user_role='member', family_id=None):
    # Генерируем уникальный URL для Web App с user_id и family_id
    if family_id:
        webapp_url = f"{WEB_APP_URL}?user_id={hashlib.md5(str(family_id).encode()).hexdigest()}"
    else:
        webapp_url = WEB_APP_URL
    
    keyboard = [
        [KeyboardButton(text="📱 Открыть веб-приложение", web_app=WebAppInfo(url=webapp_url))],
        [KeyboardButton(text="👨‍👩‍👧‍👦 Моя семья")],
        [KeyboardButton(text="➕ Быстрое добавление")]
    ]
    
    if user_role == 'admin':
        keyboard.append([KeyboardButton(text="⚙️ Управление")])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

# Команда старта
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_info = db.get_user_family(message.from_user.id)
    
    if user_info:
        family_id, family_name, role, avatar_color, theme_color = user_info
        await message.answer(
            f"👋 Добро пожаловать в семейный календарь!\n\n"
            f"🏠 Семья: <b>{family_name}</b>\n"
            f"👤 Ваша роль: {'👑 Админ' if role == 'admin' else '👤 Участник'}\n\n"
            f"📱 Используйте <b>веб-приложение</b> для удобного просмотра "
            f"и управления календарем!",
            parse_mode="HTML",
            reply_markup=get_main_keyboard(role, family_id)
        )
    else:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="👨‍👩‍👧‍👦 Создать семью")],
                [KeyboardButton(text="🔗 Присоединиться")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            "👋 Привет! Я помогу вашей семье координировать расписание.\n\n"
            "📌 Все заметки видны всем членам семьи\n"
            "📱 Есть удобное веб-приложение с календарем\n"
            "🔔 Автоматические напоминания\n\n"
            "Создайте семью или присоединитесь:",
            reply_markup=keyboard
        )

# Быстрое добавление заметки
@dp.message(F.text == "➕ Быстрое добавление")
async def quick_add_note(message: types.Message, state: FSMContext):
    user_info = db.get_user_family(message.from_user.id)
    
    if not user_info:
        await message.answer("Сначала присоединитесь к семье!")
        return
    
    family_id = user_info[0]
    
    # Пример быстрого добавления через инлайн-клавиатуру
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Добавить текст", callback_data="quick_text")],
        [InlineKeyboardButton(text="🎂 День рождения", callback_data="quick_birthday")],
        [InlineKeyboardButton(text="🛒 Покупки", callback_data="quick_shopping")],
        [InlineKeyboardButton(text="🏥 Врач", callback_data="quick_doctor")],
        [InlineKeyboardButton(text="📱 Открыть веб-приложение",web_app=WebAppInfo(url=f"{WEB_APP_URL}?action=add"))]
    ])
    
    await message.answer(
        "Выберите тип быстрого добавления или используйте веб-приложение:",
        reply_markup=keyboard
    )

# Информация о семье
@dp.message(F.text == "👨‍👩‍👧‍👦 Моя семья")
async def family_info(message: types.Message):
    user_info = db.get_user_family(message.from_user.id)
    
    if not user_info:
        await message.answer("Сначала присоединитесь к семье!")
        return
    
    family_id, family_name, role, avatar_color, theme_color = user_info
    members = db.get_family_members(family_id)
    
    response = f"🏠 <b>Семья: {family_name}</b>\n\n"
    response += f"👥 Участники ({len(members)}):\n"
    
    for member in members:
        role_icon = "👑" if member[2] == 'admin' else "👤"
        response += f"{role_icon} {member[1]}\n"
    
    response += f"\n🔑 Код семьи: <code>{db.get_family_by_code(family_id)}</code>\n"
    response += "📱 Для полного управления используйте веб-приложение!"
    
    await message.answer(response, parse_mode="HTML")

# API для Web App
@dp.message(Command("webapp_data"))
async def cmd_webapp_data(message: types.Message):
    user_info = db.get_user_family(message.from_user.id)
    
    if not user_info:
        return await message.answer(json.dumps({"error": "No family"}))
    
    family_id, family_name, role, avatar_color, theme_color = user_info
    
    # Получаем данные для веб-приложения
    today = datetime.now().strftime('%Y-%m-%d')
    notes_today = db.get_today_notes(family_id)
    members = db.get_family_members(family_id)
    
    # Форматируем заметки
    formatted_notes = []
    for note in notes_today:
        formatted_notes.append({
            'id': note[0],
            'title': note[3],
            'content': note[4],
            'date': note[5],
            'time': note[6],
            'important': bool(note[9]),
            'color': note[10],
            'author': note[11],
            'author_color': note[12]
        })
    
    # Форматируем участников
    formatted_members = []
    for member in members:
        formatted_members.append({
            'id': member[0],
            'name': member[1],
            'role': member[2],
            'color': member[3]
        })
    
    data = {
        'family': {
            'id': family_id,
            'name': family_name,
            'theme_color': theme_color,
            'code': db.get_family_by_code(family_id)[0] if db.get_family_by_code(family_id) else ''
        },
        'user': {
            'id': message.from_user.id,
            'name': message.from_user.full_name,
            'role': role,
            'color': avatar_color
        },
        'today_notes': formatted_notes,
        'members': formatted_members,
        'today': today
    }
    
    await message.answer(json.dumps(data))

# Создание и присоединение к семье (оставляем как есть)
@dp.message(F.text == "👨‍👩‍👧‍👦 Создать семью")
async def create_family_start(message: types.Message, state: FSMContext):
    await state.set_state(CreateFamily.waiting_for_name)
    await message.answer(
        "Введите название вашей семьи:",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(CreateFamily.waiting_for_name)
async def create_family_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено")
        return
    
    import secrets
    family_code = secrets.token_hex(4).upper()
    family_id = db.create_family(family_code, message.text)
    db.add_user(message.from_user.id, message.from_user.username, 
                message.from_user.full_name, family_id, 'admin')
    
    await state.clear()
    await message.answer(
        f"🎉 Семья создана!\n\n"
        f"Название: <b>{message.text}</b>\n"
        f"Код: <code>{family_code}</code>\n\n"
        f"Поделитесь кодом с членами семьи!\n"
        f"Теперь используйте веб-приложение 📱",
        parse_mode="HTML",reply_markup=get_main_keyboard('admin', family_id)
    )

# Система напоминаний
async def send_reminders():
    notes_to_remind = db.get_notes_for_reminder()
    
    for note in notes_to_remind:
        note_id, user_id, family_id, title, content, note_date, note_time, \
        reminder_minutes, is_important, color_tag, created_at, author_id, author_name, family_name = note
        
        family_members = db.get_family_members(family_id)
        
        reminder_text = (
            f"🔔 <b>НАПОМИНАНИЕ для всей семьи</b>\n\n"
            f"📌 {title}\n"
            f"📅 {datetime.strptime(note_date, '%Y-%m-%d').strftime('%d.%m.%Y (%A)')}\n"
            f"⏰ {note_time} (через {reminder_minutes} мин)\n"
            f"👤 {author_name}\n"
        )
        
        if content:
            reminder_text += f"\n📝 {content}"
        
        for member in family_members:
            try:
                await bot.send_message(member[0], reminder_text, parse_mode="HTML")
            except:
                continue

# Запуск бота
async def main():
    scheduler.add_job(send_reminders, 'interval', minutes=1)
    scheduler.start()
    
    print("Бот семейного календаря с Web App запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
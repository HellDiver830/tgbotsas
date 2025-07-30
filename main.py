import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import ChatPermissions
from datetime import datetime
import sqlite3

# Инициализация бота
API_TOKEN = input('введите API токен бота: ')
CHAT_ID = int(input('Укажите ID чата, в котором работает бот: '))
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()

# База данных для хранения информации о заблокированных
conn = sqlite3.connect('banned_users.db')
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS banned_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    full_name TEXT,
    message TEXT,
    ban_date TEXT,
    ban_time TEXT
)''')
conn.commit()

# Загружаем запрещенные слова и админов из txt файлов
def load_ban_words(file_path='ban_words.txt'):
    with open(file_path, 'r', encoding='utf-8') as f:
        return set(line.strip().lower() for line in f if line.strip())

def load_admins(file_path='admins.txt'):
    with open(file_path, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

ban_words = load_ban_words()
admins = load_admins()

# Очередь сообщений
message_queue = asyncio.Queue()



# Проверка на наличие запрещённых слов или других символов
async def check_message_for_ban(message: types.Message):
    if not message.text:
        return False  # Игнорируем сообщения без текста
    #команды админов
    if str(message.from_user.id) in admins:  # Сравниваем как строки
        if message.reply_to_message and message.text.startswith("!бан"):
            await ban_user(message.reply_to_message)
    text = message.text.lower()
#    await message.answer(f"Ваш ID: {message.from_user.id}")
    # Проверка на неразрешённые языки
    if not re.match(r'^[a-zA-Zа-яА-Я0-9\s.,!?]+$', text):
        try:
            await message.delete()
            await message.answer("Допускаются только русские и английские символы.")
        except Exception as e:
            logging.error(f"Ошибка при удалении сообщения: {e}")
        return True

    # Проверка на бан-слова
    if any(ban_word in text for ban_word in ban_words):
        return True
    return False



# Бан пользователя и удаление сообщений
async def ban_user(message: types.Message):
    try:
        user = message.from_user
        await bot.ban_chat_member(message.chat.id, user.id)  # Используем ban_chat_member для бана пользователя

        # Удаляем сообщение, если оно еще существует
        try:
            await message.delete()
        except Exception as e:
            logging.error(f"Ошибка при удалении сообщения: {e}")

        # Логируем бан в базу данных
        ban_date = datetime.now().strftime('%Y-%m-%d')
        ban_time = datetime.now().strftime('%H:%M:%S')
        cursor.execute('''INSERT INTO banned_users (user_id, username, full_name, message, ban_date, ban_time) 
                          VALUES (?, ?, ?, ?, ?, ?)''', 
                          (user.id, user.username, user.full_name, message.text, ban_date, ban_time))
        conn.commit()
    except Exception as e:
        logging.error(f"Ошибка при бане пользователя: {e}")

# Обработка сообщений
@router.message()
async def handle_message(message: types.Message):
    await message_queue.put(message)  # Добавляем сообщение в очередь

# Обработка очереди сообщений
async def process_messages():
    while True:
        message = await message_queue.get()
        if await check_message_for_ban(message):
            await ban_user(message)

# Удаление старых сообщений через 10 секунд после их получения
async def delete_old_messages(message: types.Message):
    await asyncio.sleep(10)  # Ждём 10 секунд
    try:
        await message.delete()
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")





# Основная логика работы бота
async def main():
    dp.include_router(router)  # Подключаем router вместо bot
    loop = asyncio.get_event_loop()
    loop.create_task(process_messages())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

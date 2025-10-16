import telebot
import logging
import os
import json
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file"
]

SHEET_ID = "1TEBRTf_gRi2w-YaOPmouH95tPUR-y5LQIBHKrJ0wjmE"

# Отримуємо credentials з змінної середовища
creds_json = os.environ.get('GOOGLE_CREDENTIALS')
if not creds_json:
    raise Exception("❌ GOOGLE_CREDENTIALS не задано!")

creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).worksheet("Bot Database")



# ---------------------- БОТ ----------------------
import telebot
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise Exception("❌ TOKEN не задано!")

bot = telebot.TeleBot(TOKEN)

# Система балів за тривалість
DURATION_POINTS = {
    "≤ 5 хв.": 1,
    "≤ 15 хв.": 2,
    "≤ 30 хв.": 3,
    "≤ 45 хв.": 4,
    "≥ 1 год.": "review"  # Потребує перевірки
}

# Тимчасове сховище для даних користувачів
user_sessions = {}
admin_review_sessions = {}  # Для оцінки робіт адміном
admin_goal_sessions = {}    # Для зміни мети адміном

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ФУНКЦІЇ ДЛЯ РОБОТИ З GOOGLE SHEETS
def init_user_data(user_id, username, first_name):
    """Ініціалізує дані користувача в таблиці"""
    try:
        # Шукаємо користувача в таблиці
        records = sheet.get_all_records()
        for i, record in enumerate(records, start=2):
            if record.get('user_id') == user_id:
                return record

        # Якщо користувач не знайдений, створюємо новий запис
        new_user_data = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'english': 0,
            'workout': 0,
            'stretching': 0,
            'other': 0,
            'total_points': 0,
            'goal': 100,
            'last_activity': '',
            'gifts_received': 0
        }

        # Додаємо новий рядок
        next_row = len(sheet.get_all_values()) + 1
        sheet.append_row(list(new_user_data.values()))
        logger.info(f"Створено нового користувача: {first_name} (ID: {user_id})")
        return new_user_data

    except Exception as e:
        logger.error(f"Помилка при ініціалізації користувача: {e}")
        return None


def get_user_data(user_id):
    """Отримує дані користувача з таблиці"""
    try:
        records = sheet.get_all_records()
        for record in records:
            if record.get('user_id') == user_id:
                return record
        return None
    except Exception as e:
        logger.error(f"Помилка при отриманні даних користувача: {e}")
        return None


def update_user_data(user_id, updates):
    """Оновлює дані користувача в таблиці"""
    try:
        records = sheet.get_all_records()
        for i, record in enumerate(records, start=2):
            if record.get('user_id') == user_id:
                # Оновлюємо поля
                for key, value in updates.items():
                    if key in record:
                        # Знаходимо колонку для оновлення
                        col_index = list(record.keys()).index(key) + 1
                        sheet.update_cell(i, col_index, value)
                print(f"✅ Дані користувача {user_id} оновлені: {updates}")
                return True
        print(f"❌ Користувач {user_id} не знайдений для оновлення")
        return False
    except Exception as e:
        print(f"❌ Помилка при оновленні даних користувача: {e}")
        return False


def update_activity_log(row_id, updates):
    """Оновлює запис в лозі активностей"""
    try:
        log_sheet = workbook.worksheet("Activity Logs")

        # Оновлюємо потрібні поля
        for col_name, value in updates.items():
            col_index = None
            headers = log_sheet.row_values(1)
            print(f"📋 Заголовки логу: {headers}")

            if col_name == "points_earned" and "Points Earned" in headers:
                col_index = headers.index("Points Earned") + 1
            elif col_name == "admin_reviewed" and "Admin Reviewed" in headers:
                col_index = headers.index("Admin Reviewed") + 1

            if col_index:
                log_sheet.update_cell(row_id, col_index, value)
                print(f"✅ Оновлено комірку [{row_id}, {col_index}] значенням '{value}'")

        print(f"✅ Оновлено лог активності (рядок {row_id}): {updates}")
        return True

    except Exception as e:
        print(f"❌ Помилка при оновленні логу: {e}")
        return False


def get_gift_data():
    """Отримує дані про поточний подарунок"""
    try:
        gift_sheet = workbook.worksheet("Gift Settings")
        records = gift_sheet.get_all_records()
        if records:
            return records[0]  # Перший запис - поточний подарунок
        else:
            # Створюємо дефолтні налаштування
            default_gift = {
                'goal': 100,
                'description': "Гра 'The Witcher 3: Wild Hunt'\nПовна версія з усіма DLC!",
                'photo_file_id': None
            }
            gift_sheet.append_row([default_gift['goal'], default_gift['description'], default_gift['photo_file_id']])
            return default_gift
    except Exception as e:
        logger.error(f"Помилка при отриманні даних подарунка: {e}")
        return {'goal': 100, 'description': "Гра 'The Witcher 3: Wild Hunt'", 'photo_file_id': None}


def update_gift_data(updates):
    """Оновлює дані про подарунок"""
    try:
        gift_sheet = workbook.worksheet("Gift Settings")
        current_data = get_gift_data()

        # Оновлюємо дані
        for key, value in updates.items():
            current_data[key] = value

        # Очищаємо лист і додаємо оновлені дані
        gift_sheet.clear()
        gift_sheet.append_row(['goal', 'description', 'photo_file_id'])  # Заголовки
        gift_sheet.append_row([current_data['goal'], current_data['description'], current_data['photo_file_id']])

        logger.info(f"Оновлено дані подарунка: {updates}")
        return True
    except Exception as e:
        logger.error(f"Помилка при оновленні даних подарунка: {e}")
        return False

def add_activity_log(user_id, activity_type, description, duration, points_earned, has_photo=False, needs_review=False,
                     photo_file_id=None, admin_reviewed=False):
    """Додає запис про активність в лист логів"""
    try:
        log_sheet = workbook.worksheet("Activity Logs")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log_entry = [
            timestamp,
            user_id,
            activity_type,
            description,
            duration,
            "Так" if has_photo else "Ні",
            points_earned,
            "Так" if needs_review else "Ні",
            photo_file_id or "",
            "Так" if admin_reviewed else "Ні"
        ]

        log_sheet.append_row(log_entry)
        logger.info(f"Додано лог активності для користувача {user_id}")

        # Повертаємо ID рядка для подальшого редагування
        return len(log_sheet.get_all_values())

    except Exception as e:
        logger.error(f"Помилка при додаванні логу: {e}")
        return None

def setup_sheets_structure():
    """Створює необхідну структуру таблиць якщо її немає"""
    try:
        try:
            log_sheet = workbook.worksheet("Activity Logs")
        except gspread.exceptions.WorksheetNotFound:
            log_sheet = workbook.add_worksheet(title="Activity Logs", rows=1000, cols=10)
            # Додаємо заголовки
            log_headers = ["Timestamp", "User ID", "Activity Type", "Description", "Duration", "Has Photo",
                           "Points Earned", "Needs Review", "Photo File ID", "Admin Reviewed"]
            log_sheet.append_row(log_headers)
            logger.info("Створено лист 'Activity Logs'")

        try:
            gift_sheet = workbook.worksheet("Gift Settings")
        except gspread.exceptions.WorksheetNotFound:
            gift_sheet = workbook.add_worksheet(title="Gift Settings", rows=10, cols=3)
            # Додаємо заголовки та дефолтні дані
            gift_sheet.append_row(['goal', 'description', 'photo_file_id'])
            gift_sheet.append_row([100, "Гра 'The Witcher 3: Wild Hunt'\nПовна версія з усіма DLC!", ""])
            logger.info("Створено лист 'Gift Settings'")

        # Перевіряємо структуру основного листа
        main_sheet = workbook.worksheet("Bot Database")
        current_headers = main_sheet.row_values(1)

        required_headers = [
            "user_id", "username", "first_name",
            "english", "workout", "stretching", "other",
            "total_points", "goal", "last_activity", "gifts_received"
        ]

        if current_headers != required_headers:
            main_sheet.clear()
            main_sheet.append_row(required_headers)
            logger.info("Оновлено заголовки в 'Bot Database'")

    except Exception as e:
        logger.error(f"Помилка при налаштуванні структури: {e}")


def is_brother(user_id):
    """Перевіряє чи користувач - це брат"""
    return user_id == BROTHER_ID


def is_admin(user_id):
    """Перевіряє чи користувач - це адмін"""
    return user_id == MY_ID


def create_progress_bar(current, goal, bar_length=15):
    """Створює текстову шкалу прогресу"""
    progress = min(current / goal, 1.0)
    filled_length = int(bar_length * progress)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    return f"[{bar}] {current}/{goal} ({progress:.1%})"


# КОМАНДИ БОТА
@bot.message_handler(commands=['start'])
def start_command(message):
    """Команда початку роботи з ботом"""
    user_id = message.from_user.id
    username = message.from_user.username or "Немає username"
    first_name = message.from_user.first_name or "Мандрівник"

    # Перевіряємо хто користувач
    if is_brother(user_id):
        user_data = init_user_data(user_id, username, first_name)

        if user_data:
            gift_data = get_gift_data()
            welcome_text = (
                f"🎮 *Вітаю, {first_name}!* 🎮\n\n"
                f"🛡️ *Ти ввійшов у Систему Покращення Навичок!*\n\n"
                f"📚 *Доступні навички:*\n"
                f"• 🏴‍☠️ Англійська мова\n"
                f"• 💪 Силове тренування\n" 
                f"• 🧘 Гнучкість та розминка\n"
                f"• 🔮 Інші активності\n\n"
                f"⭐ *Система балів:*\n"
                f"За кожну активність ти отримуєш досвід!\n"
                f"Коли накопичиш достатньо - отримаєш *легендарну нагороду!* 🎁\n\n"
                f"🎯 *Поточна ціль:* {gift_data['goal']} XP\n"
                f"💫 *Твій досвід:* {user_data['total_points']} XP\n\n"
                f"*Обери дію, мій друже:*"
            )
        else:
            welcome_text = "⚡ Помилка ініціалізації персонажа! Спробуй ще раз пізніше."

        show_main_menu(message.chat.id, welcome_text)

    elif is_admin(user_id):
        admin_welcome_text = (
            f"👑 *Вітаю, Володарю!* 👑\n\n"
            f"Ти зайшов у *Панель Керування Світом*.\n"
            f"Тут ти можеш керувати системою мотивації свого учня.\n\n"
            f"⚔️ Використовй команду /admin для доступу до всіх можливостей!"
        )
        show_admin_menu(message.chat.id, admin_welcome_text)

    else:
        bot.send_message(
            message.chat.id,
            "🚫 *Доступ заборонено!*\n\nЦей світ призначений лише для обраних героїв.",
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )


def show_main_menu(chat_id, text):
    """Показує головне меню для брата"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('📊 Мій прогрес')
    btn2 = types.KeyboardButton('⚔️ Нова активність')
    btn3 = types.KeyboardButton('🎁 Легендарна нагорода')
    markup.add(btn1, btn2, btn3)
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')


def show_admin_menu(chat_id, text):
    """Показує меню для адміна"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('👑 Панель Володаря')
    markup.add(btn1)
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == '📊 Мій прогрес' and is_brother(message.from_user.id))
def show_stats(message):
    """Показує статистику користувача (тільки для брата)"""
    user_id = message.from_user.id
    user_data = get_user_data(user_id)

    if not user_data:
        bot.send_message(message.chat.id, "🔮 Дані персонажа не знайдені. Почни з /start")
        return

    # Створюємо текст статистики
    stats_text = (
        f"📊 *Статистика Героя:*\n\n"
        f"🏴‍☠️ Англійська мова: *{user_data['english']} разів*\n"
        f"💪 Силове тренування: *{user_data['workout']} разів*\n"
        f"🧘 Гнучкість та розминка: *{user_data['stretching']} разів*\n"
        f"🔮 Інші активності: *{user_data['other']} разів*\n\n"
        f"⭐ *Загальний досвід:* {user_data['total_points']} XP\n"
        f"🎯 *Ціль для нагороди:* {user_data['goal']} XP\n"
        f"🏆 *Отримано нагород:* {user_data['gifts_received']}"
    )

    # Створюємо прогрес-бар
    progress_bar = create_progress_bar(user_data['total_points'], user_data['goal'])

    full_message = f"{stats_text}\n\n*Прогрес:*\n{progress_bar}"

    bot.send_message(message.chat.id, full_message, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == '⚔️ Нова активність' and is_brother(message.from_user.id))
def add_activity_start(message):
    """Починає процес додавання активності (тільки для брата)"""
    user_id = message.from_user.id

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('🏴‍☠️ Англійська')
    btn2 = types.KeyboardButton('💪 Тренування')
    btn3 = types.KeyboardButton('🧘 Розминка')
    btn4 = types.KeyboardButton('🔮 Інше')
    btn5 = types.KeyboardButton('🚪 Назад')
    markup.add(btn1, btn2, btn3, btn4, btn5)

    user_sessions[user_id] = {'state': 'choosing_activity'}

    bot.send_message(
        message.chat.id,
        "🎯 *Обери тип тренування:*\n\n_Яку навичку ти сьогодні прокачав?_",
        reply_markup=markup,
        parse_mode='Markdown'
    )


@bot.message_handler(
    func=lambda message: message.text in ['🏴‍☠️ Англійська', '💪 Тренування', '🧘 Розминка'] and is_brother(
        message.from_user.id))
def main_activity_chosen(message):
    """Обробляє вибір основної активності"""
    user_id = message.from_user.id

    activity_map = {
        '🏴‍☠️ Англійська': 'english',
        '💪 Тренування': 'workout',
        '🧘 Розминка': 'stretching'
    }

    activity_key = activity_map[message.text]
    activity_name = message.text

    if user_id not in user_sessions:
        user_sessions[user_id] = {}

    user_sessions[user_id].update({
        'state': 'choosing_duration',
        'activity_type': activity_key,
        'activity_name': activity_name
    })

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('⚡ 5 хв')
    btn2 = types.KeyboardButton('🚀 15 хв')
    btn3 = types.KeyboardButton('💫 30 хв')
    btn4 = types.KeyboardButton('🔥 45 хв')
    btn5 = types.KeyboardButton('🌟 1+ год')
    btn6 = types.KeyboardButton('🚪 Назад')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)

    bot.send_message(
        message.chat.id,
        f"⏳ *Скільки часу ти присвятив?*\n\n_Обери тривалість твого подвигу:_",
        reply_markup=markup,
        parse_mode='Markdown'
    )


@bot.message_handler(
    func=lambda message: message.text in ['⚡ 5 хв', '🚀 15 хв', '💫 30 хв', '🔥 45 хв', '🌟 1+ год'] and
                         user_sessions.get(message.from_user.id, {}).get('state') == 'choosing_duration' and
                         is_brother(message.from_user.id))
def duration_chosen(message):
    """Обробляє вибір тривалості для основних активностей"""
    user_id = message.from_user.id
    user_session = user_sessions.get(user_id, {})
    activity_type = user_session.get('activity_type')

    # Мапимо нові назви до старих значень
    duration_map = {
        '⚡ 5 хв': '≤ 5 хв.',
        '🚀 15 хв': '≤ 15 хв.',
        '💫 30 хв': '≤ 30 хв.',
        '🔥 45 хв': '≤ 45 хв.',
        '🌟 1+ год': '≥ 1 год.'
    }

    duration = duration_map[message.text]

    if not activity_type:
        bot.send_message(message.chat.id, "⚡ Помилка! Почни спочатку.")
        show_main_menu(message.chat.id, "Обери дію:")
        return

    user_sessions[user_id]['duration'] = duration

    if duration == '≥ 1 год.':
        # Для тривалості ≥ 1 год. - запитуємо опис
        user_sessions[user_id]['state'] = 'waiting_description_long'
        markup = types.ReplyKeyboardRemove()
        bot.send_message(
            message.chat.id,
            "📖 *Опиши свій подвиг!*\n\n_Що саме ти робив? Які вправи, теми чи завдання виконував?_",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    else:
        user_sessions[user_id]['state'] = 'waiting_photo_short'
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('📸 Додати фото')
        btn2 = types.KeyboardButton('🎭 Без фото')
        markup.add(btn1, btn2)

        points = DURATION_POINTS[duration]
        bot.send_message(
            message.chat.id,
            f"📸 *Докази подвигу!*\n\n_Додай фото для підтвердження (+{points} XP)_",
            reply_markup=markup,
            parse_mode='Markdown'
        )


@bot.message_handler(func=lambda message:
user_sessions.get(message.from_user.id, {}).get('state') == 'waiting_description_long' and
is_brother(message.from_user.id))
def description_long_received(message):
    """Обробляє опис для тривалої активності (≥ 1 год.)"""
    user_id = message.from_user.id
    user_sessions[user_id].update({
        'state': 'waiting_photo_long',
        'description': message.text
    })

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('📸 Додати фото')
    btn2 = types.KeyboardButton('🎭 Без фото')
    markup.add(btn1, btn2)

    bot.send_message(
        message.chat.id,
        "📸 *Час для доказів!*\n\n_Тепер додай фото твого подвигу:_",
        reply_markup=markup,
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message: message.text == '🔮 Інше' and is_brother(message.from_user.id))
def other_activity_chosen(message):
    """Обробляє вибір активності 'Інше'"""
    user_id = message.from_user.id

    # Зберігаємо в сесії
    if user_id not in user_sessions:
        user_sessions[user_id] = {}

    user_sessions[user_id].update({
        'state': 'waiting_description_other',
        'activity_type': 'other',
        'activity_name': '🔮 Інша активність'
    })

    markup = types.ReplyKeyboardRemove()
    bot.send_message(
        message.chat.id,
        "🔮 *Опиши свою таємну активність!*\n\n_Що цікавого ти сьогодні робив? Опиши детально:_",
        reply_markup=markup,
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message:
user_sessions.get(message.from_user.id, {}).get('state') == 'waiting_description_other' and
is_brother(message.from_user.id))
def description_other_received(message):
    """Обробляє опис для активності 'Інше'"""
    user_id = message.from_user.id
    user_sessions[user_id].update({
        'state': 'waiting_photo_other',
        'description': message.text
    })

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('📸 Додати фото')
    btn2 = types.KeyboardButton('🎭 Без фото')
    markup.add(btn1, btn2)

    bot.send_message(
        message.chat.id,
        "📸 *Докази таємниці!*\n\n_Додай фото для підтвердження:_",
        reply_markup=markup,
        parse_mode='Markdown'
    )



@bot.message_handler(
    func=lambda message: message.text in ['📸 Додати фото', '🎭 Без фото'] and is_brother(message.from_user.id))
def photo_choice(message):
    """Обробляє вибір щодо фото"""
    user_id = message.from_user.id
    user_session = user_sessions.get(user_id, {})

    if message.text == '🎭 Без фото':
        # Завершуємо без фото
        finish_activity(message, has_photo=False)
    else:
        user_session['state'] = 'waiting_photo_file'
        bot.send_message(
            message.chat.id,
            "🖼️ *Надішли фото твого подвигу!*",
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )


@bot.message_handler(content_types=['photo'],
                     func=lambda message:
                     user_sessions.get(message.from_user.id, {}).get('state') in ['waiting_photo_file',
                                                                                  'waiting_photo_short',
                                                                                  'waiting_photo_long',
                                                                                  'waiting_photo_other'] and
                     is_brother(message.from_user.id))
def photo_received(message):
    """Обробляє отримане фото від брата"""
    user_id = message.from_user.id
    user_sessions[user_id]['photo_file_id'] = message.photo[-1].file_id
    finish_activity(message, has_photo=True)


def finish_activity(message, has_photo=False):
    """Завершує процес додавання активності для брата"""
    user_id = message.from_user.id
    user_session = user_sessions.get(user_id, {})

    activity_type = user_session.get('activity_type')
    activity_name = user_session.get('activity_name', '')
    duration = user_session.get('duration', '')
    description = user_session.get('description', '')
    photo_file_id = user_session.get('photo_file_id')

    if not activity_type:
        bot.send_message(message.chat.id, "⚡ Помилка! Почни спочатку.")
        show_main_menu(message.chat.id, "Обери дію:")
        return

    user_data = get_user_data(user_id)
    if not user_data:
        bot.send_message(message.chat.id, "🔮 Помилка доступу до даних персонажа.")
        return

    needs_review = False
    points_earned = 0

    if activity_type == 'other' or duration == '≥ 1 год.':
        needs_review = True

        if activity_type == 'other':
            duration = "Спеціальна місія"

        log_row_id = add_activity_log(user_id, activity_type, description, duration, 0, has_photo, True, photo_file_id,
                                      False)

        if activity_type == 'other':
            admin_message_text = (
                f"🔔 *ПОТРІБНА ОЦІНКА СПЕЦІАЛЬНОЇ МІСІЇ!*\n\n"
                f"🧙 *Учень:* {user_data['first_name']}\n"
                f"🎯 *Тип:* Спеціальна активність\n"
                f"📖 *Опис:* {description}\n"
                f"📸 *Докази:* {'Так' if has_photo else 'Ні'}\n\n"
                f"_Оціни подвиг учня:_"
            )
        else:
            admin_message_text = (
                f"🔔 *ПОТРІБНА ОЦІНКА ВЕЛИКОГО ПОДВИГУ!*\n\n"
                f"🧙 *Учень:* {user_data['first_name']}\n"
                f"🎯 *Тип:* {activity_name}\n"
                f"⏱️ *Тривалість:* {duration}\n"
                f"📖 *Опис:* {description}\n"
                f"📸 *Докази:* {'Так' if has_photo else 'Ні'}\n\n"
                f"_Оціни подвиг учня:_"
            )

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('⭐ Оцінити подвиг', callback_data=f'review_{log_row_id}'))

        if has_photo and photo_file_id:
            bot.send_photo(MY_ID, photo_file_id, caption=admin_message_text, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.send_message(MY_ID, admin_message_text, reply_markup=markup, parse_mode='Markdown')

    else:
        # Для коротких активностей - автоматичне нарахування
        points_earned = DURATION_POINTS.get(duration, 0)
        new_count = user_data[activity_type] + 1
        new_total = user_data['total_points'] + points_earned

        # Оновлюємо дані
        updates = {
            activity_type: new_count,
            'total_points': new_total,
            'last_activity': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if update_user_data(user_id, updates):
            # Додаємо запис в лог
            log_row_id = add_activity_log(user_id, activity_type, description, duration, points_earned, has_photo,
                                          False, photo_file_id, True)

            gift_data = get_gift_data()

            success_text = (
                f"🎉 *ПОДВИГ ЗАРЕЄСТРОВАНО!* 🎉\n\n"
                f"🏅 *Тип:* {activity_name}\n"
                f"⏱️ *Тривалість:* {duration}\n"
                f"📸 *Докази:* {'Так' if has_photo else 'Ні'}\n"
                f"⭐ *Отримано досвіду:* +{points_earned} XP\n"
                f"💫 *Загальний досвід:* {new_total} XP\n\n"
                f"*Прогрес до легендарної нагороди:*\n"
                f"{create_progress_bar(new_total, gift_data['goal'])}"
            )

            if has_photo and photo_file_id:
                bot.send_photo(
                    message.chat.id,
                    photo_file_id,
                    caption=success_text,
                    parse_mode='Markdown'
                )
            else:
                bot.send_message(message.chat.id, success_text, parse_mode='Markdown')

            check_and_send_gift(message.chat.id, user_id, user_data, new_total)

        else:
            bot.send_message(message.chat.id, "❌ Помилка збереження даних!")

    if needs_review:
        if activity_type == 'other':
            review_text = (
                f"⏳ *СПЕЦІАЛЬНА МІСІЯ ВІДПРАВЛЕНА НА ПЕРЕВІРКУ!*\n\n"
                f"📖 *Опис:* {description}\n"
                f"📸 *Докази:* {'Так' if has_photo else 'Ні'}\n\n"
                f"_Очікуй оцінки від Володаря!_"
            )
        else:
            review_text = (
                f"⏳ *ВЕЛИКИЙ ПОДВИГ ВІДПРАВЛЕНИЙ НА ПЕРЕВІРКУ!*\n\n"
                f"🏅 *Тип:* {activity_name}\n"
                f"⏱️ *Тривалість:* {duration}\n"
                f"📖 *Опис:* {description}\n"
                f"📸 *Докази:* {'Так' if has_photo else 'Ні'}\n\n"
                f"_Очікуй оцінки від Володаря!_"
            )

        if has_photo and photo_file_id:
            bot.send_photo(
                message.chat.id,
                photo_file_id,
                caption=review_text,
                parse_mode='Markdown'
            )
        else:
            bot.send_message(message.chat.id, review_text, parse_mode='Markdown')

    if user_id in user_sessions:
        del user_sessions[user_id]

    show_main_menu(message.chat.id, "🎮 *Чудово! Що далі, мій друже?*")


@bot.message_handler(func=lambda message: message.text == '🎁 Легендарна нагорода' and is_brother(message.from_user.id))
def show_current_gift(message):
    """Показує поточний подарунок і прогрес (тільки для брата)"""
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    gift_data = get_gift_data()

    if not user_data:
        bot.send_message(message.chat.id, "🔮 Дані персонажа не знайдені.")
        return

    gift_description = (
        f"🎁 *ЛЕГЕНДАРНА НАГОРОДА:*\n\n"
        f"{gift_data['description']}\n\n"
        f"⚔️ *Ти отримаєш цю нагороду, коли досягнеш мети!* ⚔️"
    )

    progress_bar = create_progress_bar(user_data['total_points'], gift_data['goal'])

    full_message = f"{gift_description}\n\n*Твій прогрес:*\n{progress_bar}"

    if gift_data.get('photo_file_id'):
        bot.send_photo(message.chat.id, gift_data['photo_file_id'], caption=full_message, parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, full_message, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == '🚪 Назад' and is_brother(message.from_user.id))
def back_to_main(message):
    """Повернення в головне меню (тільки для брата)"""
    user_id = message.from_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]

    show_main_menu(message.chat.id, "🎮 *Повернувся до головного меню!*")


@bot.message_handler(func=lambda message: message.text == '👑 Панель Володаря' and is_admin(message.from_user.id))
def admin_panel(message):
    """Показує адмін панель"""
    admin_command(message)


def check_and_send_gift(chat_id, user_id, user_data, new_total_points):
    """Перевіряє досягнення мети і відправляє подарунок"""
    gift_data = get_gift_data()
    goal = gift_data['goal']

    if new_total_points >= goal:
        gift_message = (
            f"🎉🎉🎉 *ВЕЛИКА ПЕРЕМОГА!* 🎉🎉🎉\n\n"
            f"⚔️ *Ти досяг мети в {goal} XP!*\n"
            f"🏆 *Твоя легендарна нагорода:* {gift_data['description']}\n\n"
            f"🧙 *Володар зв'яжеться з тобою для вручення нагороди!* 🎁"
        )

        updates = {
            'gifts_received': user_data['gifts_received'] + 1,
            'total_points': new_total_points - goal,
            'goal': goal
        }
        update_user_data(user_id, updates)

        if gift_data.get('photo_file_id'):
            bot.send_photo(chat_id, gift_data['photo_file_id'], caption=gift_message, parse_mode='Markdown')
        else:
            bot.send_message(chat_id, gift_message, parse_mode='Markdown')

        admin_message = (
            f"👑 *УЧЕНЬ ДОСЯГ МЕТИ!*\n\n"
            f"🧙 *Учень:* {user_data['first_name']}\n"
            f"🆔 *ID:* {user_id}\n"
            f"⭐ *Досвід:* {new_total_points} XP\n"
            f"🎁 *Не забудь вручити легендарну нагороду!*"
        )
        bot.send_message(MY_ID, admin_message, parse_mode='Markdown')


@bot.message_handler(commands=['admin'])
def admin_command(message):
    """Адмін-команди (тільки для тебе)"""
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 *Ця команда тільки для Володаря!*", parse_mode='Markdown')
        return

    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('📊 Статистика учня', callback_data='admin_stats')
    btn2 = types.InlineKeyboardButton('⚡ Скинути прогрес', callback_data='admin_reset')
    btn3 = types.InlineKeyboardButton('🎯 Змінити ціль', callback_data='admin_goal')
    btn4 = types.InlineKeyboardButton('⭐ Додати досвід', callback_data='custom_points')
    markup.add(btn1, btn2, btn3, btn4)

    bot.send_message(message.chat.id, "👑 *ПАНЕЛЬ ВОЛОДАРЯ:*", reply_markup=markup, parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data.startswith('cancel_review_'))
def handle_cancel_review(call):
    """Обробляє скасування оцінки"""
    print(f"🔄 Отримано натискання кнопки скасування!")
    print(f"📨 Callback data: {call.data}")
    print(f"👤 Користувач: {call.from_user.id} ({call.from_user.first_name})")

    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Немає доступу!")
        return

    try:
        parts = call.data.split('_')
        print(f"🔍 Розбито на частини: {parts}")

        if len(parts) >= 4:
            log_row_id = int(parts[2])
            points = int(parts[3])

            print(f"📊 ID запису: {log_row_id}, Бали для скасування: {points}")

            user_data = get_user_data(BROTHER_ID)
            if not user_data:
                print("❌ Дані брата не знайдені")
                bot.answer_callback_query(call.id, "❌ Дані брата не знайдені")
                return

            print(f"📈 Поточні бали брата: {user_data['total_points']}")

            new_total = user_data['total_points'] - points
            if new_total < 0:
                new_total = 0

            updates = {
                'total_points': new_total,
                'last_activity': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            print(f"🔄 Оновлюємо дані: {updates}")

            if update_user_data(BROTHER_ID, updates):
                print("✅ Дані брата оновлено")
            else:
                print("❌ Помилка оновлення даних брата")

            # Оновлюємо лог
            log_updates = {
                "points_earned": 0,
                "admin_reviewed": "Скасовано"
            }

            if update_activity_log(log_row_id, log_updates):
                print("✅ Лог оновлено")
            else:
                print("❌ Помилка оновлення логу")

            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
                print("✅ Повідомлення адміна видалено")
            except Exception as e:
                print(f"❌ Помилка видалення повідомлення адміна: {e}")

            try:
                brother_message = f"❌ Оцінка скасована адміністратором. Віднімано {points} балів."
                bot.send_message(BROTHER_ID, brother_message)
                print("✅ Повідомлення брату відправлено")
            except Exception as e:
                print(f"❌ Помилка відправки повідомлення брату: {e}")

            try:
                admin_message = f"❌ Оцінка скасована. Віднімано {points} балів."
                bot.send_message(call.message.chat.id, admin_message)
                print("✅ Повідомлення адміну відправлено")
            except Exception as e:
                print(f"❌ Помилка відправки повідомлення адміну: {e}")

            bot.answer_callback_query(call.id, "✅ Оцінка скасована!")
            print("✅ Відповідь callback відправлена")

        else:
            error_msg = "❌ Неправильний формат callback_data"
            print(error_msg)
            bot.answer_callback_query(call.id, error_msg)

    except Exception as e:
        error_msg = f"❌ Помилка при скасуванні оцінки: {e}"
        print(error_msg)
        logger.error(error_msg)
        bot.answer_callback_query(call.id, "❌ Помилка при скасуванні")

@bot.callback_query_handler(func=lambda call: True)
def handle_admin_buttons(call):
    """Обробляє натискання кнопок адмін-панелі"""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Немає доступу!")
        return

    if call.data == 'admin_stats':
        user_data = get_user_data(BROTHER_ID)
        if user_data:
            stats_text = (
                f"<b>📊 Статистика брата:</b>\n\n"
                f"Англійська: {user_data['english']} разів\n"
                f"Тренування: {user_data['workout']} разів\n"
                f"Розминка: {user_data['stretching']} разів\n"
                f"Інше: {user_data['other']} разів\n\n"
                f"Всього балів: {user_data['total_points']}\n"
                f"Мета: {user_data['goal']}\n"
                f"Подарунків отримано: {user_data['gifts_received']}"
            )
            bot.send_message(call.message.chat.id, stats_text, parse_mode='HTML')
        else:
            bot.send_message(call.message.chat.id, "Дані брата не знайдені")

    elif call.data == 'admin_reset':
        user_data = get_user_data(BROTHER_ID)
        if user_data:
            updates = {
                'english': 0,
                'workout': 0,
                'stretching': 0,
                'other': 0,
                'total_points': 0,
                'last_activity': ''
            }
            if update_user_data(BROTHER_ID, updates):
                bot.send_message(call.message.chat.id, "✅ Статистика брата скинута!")
                bot.send_message(BROTHER_ID, "📊 Ваша статистика була скинута адміністратором.")
            else:
                bot.send_message(call.message.chat.id, "❌ Помилка при скиданні статистики")

    elif call.data == 'admin_goal':
        admin_goal_sessions[call.from_user.id] = {'state': 'waiting_goal_description'}
        bot.send_message(call.message.chat.id, "📝 Введи новий опис подарунка:")

    elif call.data == 'custom_points':
        admin_review_sessions[call.from_user.id] = {'state': 'waiting_custom_points'}
        bot.send_message(call.message.chat.id, "💰 Введи кількість балів для нарахування брату:")

    elif call.data.startswith('review_'):
        log_row_id = int(call.data.split('_')[1])
        admin_review_sessions[call.from_user.id] = {
            'state': 'waiting_review_points',
            'log_row_id': log_row_id
        }
        bot.send_message(call.message.chat.id, "⭐ Введи кількість балів для цієї роботи:")

    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda message:
admin_review_sessions.get(message.from_user.id, {}).get('state') == 'waiting_custom_points' and
is_admin(message.from_user.id))
def handle_custom_points(message):
    """Обробляє довільну оцінку від адміна"""
    try:
        points = int(message.text)
        user_data = get_user_data(BROTHER_ID)
        if user_data:
            new_total = user_data['total_points'] + points
            updates = {
                'total_points': new_total,
                'last_activity': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            update_user_data(BROTHER_ID, updates)

            log_row_id = add_activity_log(BROTHER_ID, "custom", f"Довільна оцінка адміна: {points} балів", "", points,
                                          False, False, None, True)

            # Сповіщаємо брата
            success_text = (
                f"🎉 <b>Адміністратор нарахував бали!</b>\n\n"
                f"⭐ Отримано балів: +{points}\n"
                f"💰 Всього балів: {new_total}"
            )

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton('❌ Скасувати оцінку', callback_data=f'cancel_review_{log_row_id}_{points}'))

            brother_message = bot.send_message(BROTHER_ID, success_text, reply_markup=markup, parse_mode='HTML')

            admin_success_text = f"✅ Нараховано {points} балів брату!"
            admin_message = bot.send_message(message.chat.id, admin_success_text, reply_markup=markup)

            admin_review_sessions[message.from_user.id] = {
                'state': 'review_completed',
                'log_row_id': log_row_id,
                'points': points,
                'brother_message_id': brother_message.message_id,
                'admin_message_id': admin_message.message_id,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            check_and_send_gift(BROTHER_ID, BROTHER_ID, user_data, new_total)
        else:
            bot.send_message(message.chat.id, "❌ Помилка: дані брата не знайдені")

    except ValueError:
        bot.send_message(message.chat.id, "❌ Будь ласка, введи коректне число балів")

    # Очищаємо сесію
    if message.from_user.id in admin_review_sessions and admin_review_sessions[message.from_user.id][
        'state'] != 'review_completed':
        del admin_review_sessions[message.from_user.id]


@bot.message_handler(func=lambda message:
admin_review_sessions.get(message.from_user.id, {}).get('state') == 'waiting_review_points' and
is_admin(message.from_user.id))
def handle_review_points(message):
    """Обробляє оцінку роботи від адміна"""
    try:
        points = int(message.text)
        admin_session = admin_review_sessions.get(message.from_user.id, {})
        log_row_id = admin_session.get('log_row_id')

        if not log_row_id:
            bot.send_message(message.chat.id, "❌ Помилка: не знайдено запис для оцінки")
            return

        update_activity_log(log_row_id, {
            "points_earned": points,
            "admin_reviewed": "Так"
        })

        user_data = get_user_data(BROTHER_ID)
        if user_data:
            new_total = user_data['total_points'] + points
            updates = {
                'total_points': new_total,
                'last_activity': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            update_user_data(BROTHER_ID, updates)

            success_text = (
                f"🎉 <b>Твою активність оцінено!</b>\n\n"
                f"⭐ Отримано балів: +{points}\n"
                f"💰 Всього балів: {new_total}"
            )

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('❌ Скасувати оцінку', callback_data=f'cancel_review_{log_row_id}_{points}'))

            brother_message = bot.send_message(BROTHER_ID, success_text, reply_markup=markup, parse_mode='HTML')

            admin_success_text = f"✅ Активність оцінена!\nНараховано: {points} балів"
            admin_message = bot.send_message(message.chat.id, admin_success_text, reply_markup=markup)

            admin_review_sessions[message.from_user.id] = {
                'state': 'review_completed',
                'log_row_id': log_row_id,
                'points': points,
                'brother_message_id': brother_message.message_id,
                'admin_message_id': admin_message.message_id,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            check_and_send_gift(BROTHER_ID, BROTHER_ID, user_data, new_total)
        else:
            bot.send_message(message.chat.id, "❌ Помилка: дані брата не знайдені")

    except ValueError:
        bot.send_message(message.chat.id, "❌ Будь ласка, введи коректне число балів")

    # Очищаємо сесію
    if message.from_user.id in admin_review_sessions and admin_review_sessions[message.from_user.id][
        'state'] != 'review_completed':
        del admin_review_sessions[message.from_user.id]


@bot.callback_query_handler(func=lambda call: call.data.startswith('cancel_review_'))
def handle_cancel_review(call):
    """Обробляє скасування оцінки"""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Немає доступу!")
        return

    try:
        parts = call.data.split('_')
        if len(parts) >= 4:
            log_row_id = int(parts[2])
            points = int(parts[3])

            user_data = get_user_data(BROTHER_ID)
            if user_data:
                new_total = user_data['total_points'] - points
                updates = {
                    'total_points': max(0, new_total),  # Не менше 0
                    'last_activity': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                update_user_data(BROTHER_ID, updates)

                update_activity_log(log_row_id, {
                    "points_earned": 0,
                    "admin_reviewed": "Скасовано"
                })

            brother_message_id = None
            admin_message_id = None

            for user_id, session in admin_review_sessions.items():
                if session.get('log_row_id') == log_row_id:
                    brother_message_id = session.get('brother_message_id')
                    admin_message_id = session.get('admin_message_id')
                    # Видаляємо сесію
                    if user_id in admin_review_sessions:
                        del admin_review_sessions[user_id]
                    break

            if brother_message_id:
                try:
                    bot.delete_message(BROTHER_ID, brother_message_id)
                except Exception as e:
                    logger.error(f"Помилка при видаленні повідомлення брата: {e}")

            if admin_message_id:
                try:
                    bot.delete_message(call.message.chat.id, admin_message_id)
                except Exception as e:
                    logger.error(f"Помилка при видаленні повідомлення адміна: {e}")

            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception as e:
                logger.error(f"Помилка при видаленні поточного повідомлення: {e}")

            # Сповіщаємо брата
            bot.send_message(BROTHER_ID, "❌ Оцінка скасована адміністратором.")

            bot.send_message(call.message.chat.id, f"❌ Оцінка скасована. Віднімано {points} балів.")

            bot.answer_callback_query(call.id, "✅ Оцінка скасована!")
        else:
            bot.answer_callback_query(call.id, "❌ Помилка при скасуванні")

    except Exception as e:
        logger.error(f"Помилка при скасуванні оцінки: {e}")
        bot.answer_callback_query(call.id, "❌ Помилка при скасуванні")


@bot.message_handler(func=lambda message:
admin_goal_sessions.get(message.from_user.id, {}).get('state') == 'waiting_goal_description' and
is_admin(message.from_user.id))
def handle_goal_description(message):
    """Обробляє опис нової мети"""
    admin_goal_sessions[message.from_user.id] = {
        'state': 'waiting_goal_points',
        'description': message.text
    }
    bot.send_message(message.chat.id, "🎯 Тепер введи кількість балів для нової мети:")


@bot.message_handler(func=lambda message:
admin_goal_sessions.get(message.from_user.id, {}).get('state') == 'waiting_goal_points' and
is_admin(message.from_user.id))
def handle_goal_points(message):
    """Обробляє кількість балів для нової мети"""
    try:
        goal_points = int(message.text)
        admin_session = admin_goal_sessions.get(message.from_user.id, {})
        description = admin_session.get('description', '')

        updates = {
            'goal': goal_points,
            'description': description
        }

        bot.send_message(message.chat.id, "📸 Тепер надішли фото для подарунка (або відправ /skip щоб пропустити):")
        admin_goal_sessions[message.from_user.id] = {
            'state': 'waiting_goal_photo',
            'description': description,
            'goal': goal_points
        }

    except ValueError:
        bot.send_message(message.chat.id, "❌ Будь ласка, введи коректне число балів")


@bot.message_handler(content_types=['photo', 'text'],
                     func=lambda message:
                     admin_goal_sessions.get(message.from_user.id, {}).get('state') == 'waiting_goal_photo' and
                     is_admin(message.from_user.id))
def handle_goal_photo_final(message):
    """Обробляє фото або пропуск для нової мети"""
    admin_session = admin_goal_sessions.get(message.from_user.id, {})
    if not admin_session:
        bot.send_message(message.chat.id, "❌ Сесія не знайдена. Почни спочатку.")
        return

    photo_file_id = None
    if message.content_type == 'photo':
        photo_file_id = message.photo[-1].file_id

    updates = {
        'goal': admin_session['goal'],
        'description': admin_session['description'],
        'photo_file_id': photo_file_id
    }

    if update_gift_data(updates):
        records = sheet.get_all_records()
        for i, record in enumerate(records, start=2):
            if record.get('user_id'):
                col_index = list(record.keys()).index('goal') + 1
                sheet.update_cell(i, col_index, admin_session['goal'])

        success_text = (
            f"✅ Мета оновлена!\n\n"
            f"🎯 Нова ціль: {admin_session['goal']} балів\n"
            f"📝 Опис: {admin_session['description']}\n"
            f"📸 Фото: {'Додано' if photo_file_id else 'Відсутнє'}"
        )
        bot.send_message(message.chat.id, success_text)

        bot.send_message(BROTHER_ID, "🎁 Оновлено подарунок! Натисни 'Поточний подарунок' щоб побачити зміни.")
    else:
        bot.send_message(message.chat.id, "❌ Помилка при оновленні мети")

    if message.from_user.id in admin_goal_sessions:
        del admin_goal_sessions[message.from_user.id]


# ЗАПУСК БОТА (версія для Railway)
import flask
import time

app = flask.Flask(__name__)

@app.route(f"/{TOKEN}", methods=['POST'])
def receive_update():
    """Отримання оновлень від Telegram через webhook"""
    try:
        update = telebot.types.Update.de_json(flask.request.stream.read().decode('utf-8'))
        bot.process_new_updates([update])
    except Exception as e:
        logger.error(f"Помилка при обробці webhook: {e}")
    return "OK", 200


@app.route("/", methods=['GET'])
def index():
    """Перевірка, що бот працює"""
    return "Бот запущений 🚀", 200


if __name__ == "__main__":
    logger.info("🚀 Запуск бота у середовищі Railway...")
    try:
        setup_sheets_structure()

        # Отримуємо порт і URL з Railway
        PORT = int(os.environ.get("PORT", 5000))
        RAILWAY_URL = os.environ.get("RAILWAY_STATIC_URL")

        if not RAILWAY_URL:
            logger.error("❌ Змінна середовища RAILWAY_STATIC_URL не задана!")
        else:
            full_webhook_url = f"https://{RAILWAY_URL}/{TOKEN}"
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=full_webhook_url)
            logger.info(f"✅ Webhook встановлено: {full_webhook_url}")

        app.run(host="0.0.0.0", port=PORT)

    except Exception as e:
        logger.error(f"❌ Помилка при запуску бота: {e}")


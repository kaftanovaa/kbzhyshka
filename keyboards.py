from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from datetime import date, timedelta
import calendar


# ===== REPLY KEYBOARDS (внизу экрана) =====

def get_main_keyboard(has_settings: bool = True) -> ReplyKeyboardMarkup:
    """Главное меню — ReplyKeyboard."""
    buttons = [
        [KeyboardButton(text="📅 Сегодня")],
        [KeyboardButton(text="📆 Открыть календарь")],
        [KeyboardButton(text="📊 Статистика за неделю")],
        [KeyboardButton(text="📈 Статистика за месяц")]
    ]
    if has_settings:
        buttons.append([KeyboardButton(text="🔄 Пересчитать норму")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_today_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для страницы 'Сегодня' — ReplyKeyboard."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Добавить"), KeyboardButton(text="➖ Удалить")],
        [KeyboardButton(text="◀ Вчера"), KeyboardButton(text="▶ Завтра")],
        [KeyboardButton(text="📆 К календарю"), KeyboardButton(text="🏠 Главная")]
    ], resize_keyboard=True)


def get_day_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для просмотра дня из календаря — ReplyKeyboard."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Добавить"), KeyboardButton(text="➖ Удалить")],
        [KeyboardButton(text="◀ Пред. день"), KeyboardButton(text="▶ След. день")],
        [KeyboardButton(text="📆 К календарю"), KeyboardButton(text="🏠 Главная")]
    ], resize_keyboard=True)


def get_add_type_keyboard() -> ReplyKeyboardMarkup:
    """Выбор типа добавления."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🍽 На порцию"), KeyboardButton(text="⚖ На 100г")],
        [KeyboardButton(text="❌ Отмена")]
    ], resize_keyboard=True)


def get_remove_type_keyboard() -> ReplyKeyboardMarkup:
    """Выбор типа удаления."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🍽 На порцию"), KeyboardButton(text="⚖ На 100г")],
        [KeyboardButton(text="❌ Отмена")]
    ], resize_keyboard=True)


def get_gender_keyboard() -> ReplyKeyboardMarkup:
    """Выбор пола."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👨 Мужчина"), KeyboardButton(text="👩 Женщина")],
        [KeyboardButton(text="❌ Отмена")]
    ], resize_keyboard=True)


def get_activity_keyboard() -> ReplyKeyboardMarkup:
    """Выбор активности."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🪑 Сидячий (без нагрузок)")],
        [KeyboardButton(text="🚶 Лёгкая (1-3 раза/нед)")],
        [KeyboardButton(text="🏃 Умеренная (3-5 дней/нед)")],
        [KeyboardButton(text="🏋️ Высокая (6-7 дней/нед)")],
        [KeyboardButton(text="⚡ Очень высокая")],
        [KeyboardButton(text="❌ Отмена")]
    ], resize_keyboard=True)


def get_goal_keyboard() -> ReplyKeyboardMarkup:
    """Выбор цели."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔥 Похудение")],
        [KeyboardButton(text="⚖️ Поддержание веса")],
        [KeyboardButton(text="💪 Набор веса")],
        [KeyboardButton(text="❌ Отмена")]
    ], resize_keyboard=True)


def get_deficit_keyboard() -> ReplyKeyboardMarkup:
    """Выбор дефицита."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🟢 Небольшой (-10%)")],
        [KeyboardButton(text="🟡 Средний (-15%)")],
        [KeyboardButton(text="🔴 Большой (-20%)")],
        [KeyboardButton(text="❌ Отмена")]
    ], resize_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Кнопка отмены."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="❌ Отмена")]
    ], resize_keyboard=True)


# ===== INLINE KEYBOARDS (для календаря) =====

def get_calendar_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    """Клавиатура календаря на месяц — inline."""
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    month_days = cal.monthdayscalendar(year, month)
    month_name = calendar.month_name[month]

    buttons = []

    nav_row = [
        InlineKeyboardButton(text="◀", callback_data=f"cal_prev:{year}:{month}"),
        InlineKeyboardButton(text=f"📅 {month_name} {year}", callback_data="cal_title"),
        InlineKeyboardButton(text="▶", callback_data=f"cal_next:{year}:{month}")
    ]
    buttons.append(nav_row)

    days_header = [
        InlineKeyboardButton(text="Пн", callback_data="cal_dn"),
        InlineKeyboardButton(text="Вт", callback_data="cal_dn"),
        InlineKeyboardButton(text="Ср", callback_data="cal_dn"),
        InlineKeyboardButton(text="Чт", callback_data="cal_dn"),
        InlineKeyboardButton(text="Пт", callback_data="cal_dn"),
        InlineKeyboardButton(text="Сб", callback_data="cal_dn"),
        InlineKeyboardButton(text="Вс", callback_data="cal_dn")
    ]
    buttons.append(days_header)

    today = date.today()
    for week in month_days:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text="·", callback_data="cal_empty"))
            else:
                is_today = (day == today.day and month == today.month and year == today.year)
                text = f"[{day}]" if is_today else str(day)
                row.append(InlineKeyboardButton(text=text, callback_data=f"cal_day:{year}:{month}:{day}"))
        buttons.append(row)

    footer_row = [
        InlineKeyboardButton(text="🏠 Главная", callback_data="back_main"),
        InlineKeyboardButton(text="📅 Сегодня", callback_data=f"cal_day:{today.year}:{today.month}:{today.day}")
    ]
    buttons.append(footer_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)

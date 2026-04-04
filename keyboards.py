from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date, timedelta
import calendar


def get_main_keyboard(has_settings: bool = True) -> InlineKeyboardMarkup:
    """Главное меню."""
    rows = [
        [InlineKeyboardButton(text="📅 Сегодня", callback_data="today")],
        [InlineKeyboardButton(text="📆 Открыть календарь", callback_data="calendar_main")],
        [InlineKeyboardButton(text="📊 Статистика за неделю", callback_data="stats_week")],
        [InlineKeyboardButton(text="📈 Статистика за месяц", callback_data="stats_month")]
    ]
    if has_settings:
        rows.append([InlineKeyboardButton(text="🔄 Пересчитать норму", callback_data="recalc_norm")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_gender_keyboard() -> InlineKeyboardMarkup:
    """Выбор пола."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Мужчина", callback_data="gender_male")],
        [InlineKeyboardButton(text="👩 Женщина", callback_data="gender_female")]
    ])


def get_activity_keyboard() -> InlineKeyboardMarkup:
    """Выбор активности."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪑 Сидячий образ жизни", callback_data="activity_1.2")],
        [InlineKeyboardButton(text="🚶 Лёгкая активность (1-3 раза)", callback_data="activity_1.375")],
        [InlineKeyboardButton(text="🏃 Умеренная активность (3-5 дней)", callback_data="activity_1.55")],
        [InlineKeyboardButton(text="🏋️ Высокая активность (6-7 дней)", callback_data="activity_1.725")],
        [InlineKeyboardButton(text="⚡ Очень высокая активность", callback_data="activity_1.9")]
    ])


def get_goal_keyboard() -> InlineKeyboardMarkup:
    """Выбор цели."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Похудение", callback_data="goal_loss")],
        [InlineKeyboardButton(text="⚖️ Поддержание веса", callback_data="goal_maintain")],
        [InlineKeyboardButton(text="💪 Набор веса", callback_data="goal_gain")]
    ])


def get_deficit_keyboard() -> InlineKeyboardMarkup:
    """Выбор дефицита для похудения."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Небольшой (-10%)", callback_data="deficit_small")],
        [InlineKeyboardButton(text="🟡 Средний (-15%)", callback_data="deficit_medium")],
        [InlineKeyboardButton(text="🔴 Большой (-20%)", callback_data="deficit_large")]
    ])


def get_today_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для страницы 'Сегодня' с навигацией."""
    today = date.today()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="add_food")],
        [InlineKeyboardButton(text="➖ Удалить", callback_data="remove_food")],
        [InlineKeyboardButton(text="◀", callback_data=f"day_prev:{today.year}:{today.month}:{today.day}"),
         InlineKeyboardButton(text=" Главная", callback_data="back_main"),
         InlineKeyboardButton(text="▶", callback_data=f"day_next:{today.year}:{today.month}:{today.day}")],
        [InlineKeyboardButton(text="📆 К календарю", callback_data="calendar_main")]
    ])
    return keyboard


def get_add_food_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор типа ввода: на порцию или на 100г."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍽 На порцию", callback_data="add_per_serving")],
        [InlineKeyboardButton(text="⚖ На 100г", callback_data="add_per_100g")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add")]
    ])


def get_calendar_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    """Клавиатура календаря на месяц."""
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


def get_day_view_keyboard(year: int, month: int, day: int) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра конкретного дня с навигацией."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data=f"add_food_day:{year}:{month}:{day}")],
        [InlineKeyboardButton(text="➖ Удалить", callback_data=f"remove_food_day:{year}:{month}:{day}")],
        [InlineKeyboardButton(text="◀", callback_data=f"day_prev:{year}:{month}:{day}"),
         InlineKeyboardButton(text="📆 К календарю", callback_data=f"calendar_month:{year}:{month}"),
         InlineKeyboardButton(text="▶", callback_data=f"day_next:{year}:{month}:{day}")],
        [InlineKeyboardButton(text="🏠 Главная", callback_data="back_main")]
    ])


def get_day_view_keyboard_with_add_type(year: int, month: int, day: int) -> InlineKeyboardMarkup:
    """Клавиатура для дня с выбором типа добавления."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍽 На порцию", callback_data=f"add_serving_day:{year}:{month}:{day}")],
        [InlineKeyboardButton(text="⚖ На 100г", callback_data=f"add_100g_day:{year}:{month}:{day}")],
        [InlineKeyboardButton(text="◀", callback_data=f"day_prev:{year}:{month}:{day}"),
         InlineKeyboardButton(text="📆 К календарю", callback_data=f"calendar_month:{year}:{month}"),
         InlineKeyboardButton(text="▶", callback_data=f"day_next:{year}:{month}:{day}")],
        [InlineKeyboardButton(text="🏠 Главная", callback_data="back_main")]
    ])


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
    ])

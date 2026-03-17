from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date, timedelta
import calendar


def get_main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сегодня", callback_data="today")],
        [InlineKeyboardButton(text="Открыть календарь", callback_data="calendar_main")],
        [InlineKeyboardButton(text="📊 Статистика за неделю", callback_data="stats_week")],
        [InlineKeyboardButton(text="📈 Статистика за месяц", callback_data="stats_month")]
    ])
    return keyboard


def get_today_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для страницы 'Сегодня' с навигацией."""
    today = date.today()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить ням-ням", callback_data="add_food")],
        [InlineKeyboardButton(text="Удалить ням-ням", callback_data="remove_food")],
        [InlineKeyboardButton(text="◀", callback_data=f"day_prev:{today.year}:{today.month}:{today.day}"),
         InlineKeyboardButton(text="🔙 На главную", callback_data="back_main"),
         InlineKeyboardButton(text="▶", callback_data=f"day_next:{today.year}:{today.month}:{today.day}")],
        [InlineKeyboardButton(text="📅 К календарю", callback_data="calendar_main")]
    ])
    return keyboard


def get_add_food_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор типа ввода: на порцию или на 100г."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍽 На порцию", callback_data="add_per_serving")],
        [InlineKeyboardButton(text="⚖ На 100г", callback_data="add_per_100g")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add")]
    ])
    return keyboard


def get_remove_food_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для удаления."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_remove")]
    ])
    return keyboard


def get_calendar_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    """Клавиатура календаря на месяц."""
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    month_days = cal.monthdayscalendar(year, month)
    
    # Название месяца
    month_name = calendar.month_name[month]
    
    buttons = []
    
    # Заголовок с навигацией
    nav_row = [
        InlineKeyboardButton(text="◀", callback_data=f"cal_prev:{year}:{month}"),
        InlineKeyboardButton(text=f"📅 {month_name} {year}", callback_data="cal_title"),
        InlineKeyboardButton(text="▶", callback_data=f"cal_next:{year}:{month}")
    ]
    buttons.append(nav_row)
    
    # Дни недели
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
    
    # Дни месяца
    today = date.today()
    
    for week in month_days:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text="·", callback_data="cal_empty"))
            else:
                day_str = f"{year}-{month:02d}-{day:02d}"
                is_today = (day == today.day and month == today.month and year == today.year)
                
                if is_today:
                    text = f"[{day}]"
                else:
                    text = str(day)
                
                row.append(InlineKeyboardButton(text=text, callback_data=f"cal_day:{year}:{month}:{day}"))
        buttons.append(row)
    
    # Кнопка "Назад" и "К сегодня"
    footer_row = [
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_main"),
        InlineKeyboardButton(text=" Сегодня", callback_data=f"cal_day:{today.year}:{today.month}:{today.day}")
    ]
    buttons.append(footer_row)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_day_view_keyboard(year: int, month: int, day: int) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра конкретного дня с навигацией."""
    current_date = date(year, month, day)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить ням-ням", callback_data=f"add_food_day:{year}:{month}:{day}")],
        [InlineKeyboardButton(text="Удалить ням-ням", callback_data=f"remove_food_day:{year}:{month}:{day}")],
        [InlineKeyboardButton(text="◀", callback_data=f"day_prev:{year}:{month}:{day}"),
         InlineKeyboardButton(text="🔙 К календарю", callback_data=f"calendar_month:{year}:{month}"),
         InlineKeyboardButton(text="▶", callback_data=f"day_next:{year}:{month}:{day}")],
        [InlineKeyboardButton(text="🏠 На главную", callback_data="back_main")]
    ])
    return keyboard


def get_day_view_keyboard_with_add_type(year: int, month: int, day: int, per_100g: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для дня с выбором типа добавления."""
    if per_100g:
        add_callback = f"add_100g_day:{year}:{month}:{day}"
    else:
        add_callback = f"add_serving_day:{year}:{month}:{day}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍽 На порцию", callback_data=f"add_serving_day:{year}:{month}:{day}")],
        [InlineKeyboardButton(text="⚖ На 100г", callback_data=f"add_100g_day:{year}:{month}:{day}")],
        [InlineKeyboardButton(text="◀", callback_data=f"day_prev:{year}:{month}:{day}"),
         InlineKeyboardButton(text="🔙 К календарю", callback_data=f"calendar_month:{year}:{month}"),
         InlineKeyboardButton(text="▶", callback_data=f"day_next:{year}:{month}:{day}")],
        [InlineKeyboardButton(text="🏠 На главную", callback_data="back_main")]
    ])
    return keyboard


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Простая кнопка 'Назад'."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    return keyboard


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
    ])
    return keyboard

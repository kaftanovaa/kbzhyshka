import asyncio
import logging
import re
import calendar
from datetime import date, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import BOT_TOKEN
from database import (
    init_db, add_user, user_exists,
    add_food_entry, remove_food_entry,
    get_daily_totals, get_food_entries_for_date,
    delete_food_entry_by_id, get_dates_with_entries,
    get_week_stats, get_month_stats
)
from keyboards import (
    get_main_keyboard, get_today_keyboard,
    get_calendar_keyboard, get_day_view_keyboard,
    get_add_food_type_keyboard, get_cancel_keyboard,
    get_day_view_keyboard_with_add_type
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# FSM состояния
class FoodInput(StatesGroup):
    waiting_for_serving = State()
    waiting_for_100g = State()
    waiting_for_remove = State()


# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Нормы БЖ
PROTEIN_NORM = 110  # г в день
FAT_NORM = 55  # г в день
WEEKLY_PROTEIN_NORM = 770  # г в неделю (110 * 7)
WEEKLY_FAT_NORM = 385  # г в неделю (55 * 7)


# Форматирование числа
def format_number(num: float) -> str:
    if num == int(num):
        return str(int(num))
    return f"{num:.1f}".rstrip('0').rstrip('.')


# Проверка формата ввода (число/число)
def parse_food_input(text: str) -> tuple:
    """Парсит ввод в формате 'белки/жиры'. Возвращает (protein, fat) или None."""
    text = text.strip()
    pattern = r'^(\d+[.,]?\d*)\s*/\s*(\d+[.,]?\d*)$'
    match = re.match(pattern, text)
    if match:
        try:
            protein = float(match.group(1).replace(',', '.'))
            fat = float(match.group(2).replace(',', '.'))
            return (protein, fat)
        except ValueError:
            return None
    return None


# Проверка формата ввода для 100г (число/число число)
def parse_100g_input(text: str) -> tuple:
    """Парсит ввод в формате 'белки/жиры вес'. Возвращает (protein_per_100, fat_per_100, weight) или None."""
    text = text.strip()
    # Разрешаем запятую или точку как разделитель десятичных
    pattern = r'^(\d+[.,]?\d*)\s*/\s*(\d+[.,]?\d*)\s+(\d+[.,]?\d*)$'
    match = re.match(pattern, text)
    if match:
        try:
            protein_per_100 = float(match.group(1).replace(',', '.'))
            fat_per_100 = float(match.group(2).replace(',', '.'))
            weight = float(match.group(3).replace(',', '.'))
            return (protein_per_100, fat_per_100, weight)
        except ValueError:
            return None
    return None


# Получить название дня недели
def get_day_name(date_str: str) -> str:
    """Вернуть название дня недели для даты."""
    year, month, day = map(int, date_str.split('-'))
    d = date(year, month, day)
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return days[d.weekday()]


# Получить неделю (понедельник-воскресенье) для даты
def get_week_range(target_date: date = None) -> tuple:
    """Вернуть (start_date, end_date) для текущей недели (пн-вс)."""
    if target_date is None:
        target_date = date.today()
    
    # Понедельник этой недели
    monday = target_date - timedelta(days=target_date.weekday())
    # Воскресенье этой недели
    sunday = monday + timedelta(days=6)
    
    return (monday.isoformat(), sunday.isoformat())


# Получить текущий месяц (первый и последний день)
def get_month_range(target_date: date = None) -> tuple:
    """Вернуть (year, month) для текущего месяца."""
    if target_date is None:
        target_date = date.today()
    return (target_date.year, target_date.month)


# ================== КОМАНДЫ ==================

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username

    if not user_exists(user_id):
        add_user(user_id, username)

    await message.answer(
        "🤫 Запиши, сколько белок ты скушал сегодня",
        reply_markup=get_main_keyboard()
    )


# ================== ГЛАВНАЯ ==================

@dp.callback_query(F.data == "today")
async def show_today(callback: CallbackQuery):
    user_id = callback.from_user.id
    today = date.today().isoformat()

    protein, fat = get_daily_totals(user_id, today)

    # Определяем добор/недобор только по белкам
    protein_ok = protein >= PROTEIN_NORM

    if protein_ok:
        protein_percent = int((protein / PROTEIN_NORM) * 100) - 100
        status = f"✅ Добор: +{protein_percent}%"
    else:
        protein_percent = int((protein / PROTEIN_NORM) * 100)
        status = f"😞 Недобор: {protein_percent}%"

    text = (
        f"<b>📊 Данные за сегодня ({date.today().strftime('%d.%m.%Y')})</b>\n\n"
        f"Белки: <b>{format_number(protein)}</b>г\n"
        f"Жиры: <b>{format_number(fat)}</b>г\n\n"
        f"{status}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_today_keyboard(),
        parse_mode="HTML"
    )


# ================== ДОБАВИТЬ НЯМ-НЯМ - ВЫБОР ТИПА ==================

@dp.callback_query(F.data == "add_food")
async def start_add_food_type(callback: CallbackQuery):
    await callback.message.answer(
        "Выберите тип ввода данных:",
        reply_markup=get_add_food_type_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "cancel_add")
async def cancel_add(callback: CallbackQuery):
    await callback.message.edit_text(
        "❌ Отменено",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()


# ================== ДОБАВИТЬ НА ПОРЦИЮ ==================

@dp.callback_query(F.data == "add_per_serving")
async def start_add_serving(callback: CallbackQuery, state: FSMContext):
    await state.update_data(target_date=date.today().isoformat())
    await callback.message.answer(
        "Введите данные в формате <b>Белки/Жиры</b>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(FoodInput.waiting_for_serving)


@dp.message(F.text, FoodInput.waiting_for_serving)
async def process_add_serving(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return
    
    data = await state.get_data()
    target_date = data.get("target_date", date.today().isoformat())
    user_id = message.from_user.id

    result = parse_food_input(message.text)
    if result is None:
        await message.answer(
            "❌ Некорректный ввод, введите в формате <b>Белки/Жиры</b>",
            parse_mode="HTML"
        )
        return

    protein, fat = result
    add_food_entry(user_id, target_date, protein, fat)

    total_protein, total_fat = get_daily_totals(user_id, target_date)

    if target_date == date.today().isoformat():
        text = (
            f"<b>📊 Данные за сегодня ({date.today().strftime('%d.%m.%Y')})</b>\n\n"
            f"Белки: <b>{format_number(total_protein)}</b>г\n"
            f"Жиры: <b>{format_number(total_fat)}</b>г\n\n"
            f"✅ Добавлено: {format_number(protein)}г белка / {format_number(fat)}г жира"
        )
        keyboard = get_today_keyboard()
    else:
        year, month, day = map(int, target_date.split('-'))
        text = (
            f"<b>📊 Данные за {day:02d}.{month:02d}.{year}</b>\n\n"
            f"Белки: <b>{format_number(total_protein)}</b>г\n"
            f"Жиры: <b>{format_number(total_fat)}</b>г\n\n"
            f"✅ Добавлено: {format_number(protein)}г белка / {format_number(fat)}г жира"
        )
        keyboard = get_day_view_keyboard(year, month, day)

    try:
        async for msg in message.bot.get_chat_history(message.chat.id, limit=5):
            if msg.from_user.id == bot.id and msg.reply_markup:
                await msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
                break
    except:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await state.clear()


# ================== ДОБАВИТЬ НА 100Г ==================

@dp.callback_query(F.data == "add_per_100g")
async def start_add_100g(callback: CallbackQuery, state: FSMContext):
    await state.update_data(target_date=date.today().isoformat())
    await callback.message.answer(
        "Введите данные в формате <b>Белки/Жиры Вес</b>\n"
        "(БЖ на 100г и вес порции в граммах)",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(FoodInput.waiting_for_100g)


@dp.message(F.text, FoodInput.waiting_for_100g)
async def process_add_100g(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return
    
    data = await state.get_data()
    target_date = data.get("target_date", date.today().isoformat())
    user_id = message.from_user.id

    result = parse_100g_input(message.text)
    if result is None:
        await message.answer(
            "❌ Некорректный ввод, введите в формате <b>Белки/Жиры Вес</b>\n"
            "Пример: 5/30 150 (5г белка и 30г жира на 100г, вес порции 150г)",
            parse_mode="HTML"
        )
        return

    protein_per_100, fat_per_100, weight = result
    
    # Считаем БЖ для порции
    protein = (protein_per_100 * weight) / 100
    fat = (fat_per_100 * weight) / 100

    add_food_entry(user_id, target_date, protein, fat)

    total_protein, total_fat = get_daily_totals(user_id, target_date)

    if target_date == date.today().isoformat():
        text = (
            f"<b>📊 Данные за сегодня ({date.today().strftime('%d.%m.%Y')})</b>\n\n"
            f"Белки: <b>{format_number(total_protein)}</b>г\n"
            f"Жиры: <b>{format_number(total_fat)}</b>г\n\n"
            f"✅ Добавлено: {format_number(protein)}г белка / {format_number(fat)}г жира\n"
            f"<i>(Рассчитано для {format_number(weight)}г при БЖ {format_number(protein_per_100)}/{format_number(fat_per_100)} на 100г)</i>"
        )
        keyboard = get_today_keyboard()
    else:
        year, month, day = map(int, target_date.split('-'))
        text = (
            f"<b>📊 Данные за {day:02d}.{month:02d}.{year}</b>\n\n"
            f"Белки: <b>{format_number(total_protein)}</b>г\n"
            f"Жиры: <b>{format_number(total_fat)}</b>г\n\n"
            f"✅ Добавлено: {format_number(protein)}г белка / {format_number(fat)}г жира\n"
            f"<i>(Рассчитано для {format_number(weight)}г при БЖ {format_number(protein_per_100)}/{format_number(fat_per_100)} на 100г)</i>"
        )
        keyboard = get_day_view_keyboard(year, month, day)

    try:
        async for msg in message.bot.get_chat_history(message.chat.id, limit=5):
            if msg.from_user.id == bot.id and msg.reply_markup:
                await msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
                break
    except:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await state.clear()


# ================== УДАЛИТЬ НЯМ-НЯМ ==================

@dp.callback_query(F.data == "remove_food")
async def start_remove_food(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    today = date.today().isoformat()

    entries = get_food_entries_for_date(user_id, today)

    if not entries:
        await callback.answer("За сегодня нет записей для удаления", show_alert=True)
        return

    await state.update_data(target_date=today)
    await callback.message.answer(
        "Введите данные для удаления в формате <b>Белки/Жиры</b>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(FoodInput.waiting_for_remove)


@dp.message(F.text, FoodInput.waiting_for_remove)
async def process_remove_food(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return

    data = await state.get_data()
    target_date = data.get("target_date", date.today().isoformat())

    result = parse_food_input(message.text)
    if result is None:
        await message.answer(
            "❌ Некорректный ввод, введите в формате <b>Белки/Жиры</b>",
            parse_mode="HTML"
        )
        return

    protein, fat = result
    user_id = message.from_user.id

    # Получаем список записей для отладки
    entries = get_food_entries_for_date(user_id, target_date)
    
    if not entries:
        await message.answer(
            "❌ За сегодня нет записей для удаления.\n"
            "Сначала добавь что-нибудь.",
            parse_mode="HTML"
        )
        return

    removed = remove_food_entry(user_id, target_date, protein, fat)

    if not removed:
        # Показываем какие записи есть в базе
        entries_text = "\n".join([f"• {e['protein']}г белка / {e['fat']}г жира" for e in entries])
        await message.answer(
            f"❌ Запись с такими значениями не найдена.\n\n"
            f"Ты ввёл: <b>{protein}/{fat}</b>\n\n"
            f"Есть записи:\n{entries_text}",
            parse_mode="HTML"
        )
        return

    total_protein, total_fat = get_daily_totals(user_id, target_date)

    if target_date == date.today().isoformat():
        text = (
            f"<b>📊 Данные за сегодня ({date.today().strftime('%d.%m.%Y')})</b>\n\n"
            f"Белки: <b>{format_number(total_protein)}</b>г\n"
            f"Жиры: <b>{format_number(total_fat)}</b>г\n\n"
            f"✅ Удалено: {format_number(protein)}г белка / {format_number(fat)}г жира"
        )
        keyboard = get_today_keyboard()
    else:
        year, month, day = map(int, target_date.split('-'))
        text = (
            f"<b>📊 Данные за {day:02d}.{month:02d}.{year}</b>\n\n"
            f"Белки: <b>{format_number(total_protein)}</b>г\n"
            f"Жиры: <b>{format_number(total_fat)}</b>г\n\n"
            f"✅ Удалено: {format_number(protein)}г белка / {format_number(fat)}г жира"
        )
        keyboard = get_day_view_keyboard(year, month, day)

    try:
        async for msg in message.bot.get_chat_history(message.chat.id, limit=5):
            if msg.from_user.id == bot.id and msg.reply_markup:
                await msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
                break
    except:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await state.clear()


# ================== КАЛЕНДАРЬ ==================

@dp.callback_query(F.data == "calendar_main")
async def show_calendar_main(callback: CallbackQuery):
    today = date.today()
    keyboard = get_calendar_keyboard(today.year, today.month)

    await callback.message.edit_text(
        "<b>📅 Выберите дату</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("cal_prev:"))
async def calendar_prev_month(callback: CallbackQuery):
    _, year, month = callback.data.split(":")
    year, month = int(year), int(month)

    if month == 1:
        year -= 1
        month = 12
    else:
        month -= 1

    keyboard = get_calendar_keyboard(year, month)
    await callback.message.edit_text(
        "<b>📅 Выберите дату</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("cal_next:"))
async def calendar_next_month(callback: CallbackQuery):
    _, year, month = callback.data.split(":")
    year, month = int(year), int(month)

    if month == 12:
        year += 1
        month = 1
    else:
        month += 1

    keyboard = get_calendar_keyboard(year, month)
    await callback.message.edit_text(
        "<b>📅 Выберите дату</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("cal_day:"))
async def calendar_select_day(callback: CallbackQuery):
    _, year, month, day = callback.data.split(":")
    year, month, day = int(year), int(month), int(day)

    user_id = callback.from_user.id
    target_date = f"{year}-{month:02d}-{day:02d}"

    protein, fat = get_daily_totals(user_id, target_date)
    today = date.today()

    if target_date == today.isoformat():
        date_title = "сегодня"
    else:
        date_title = f"{day:02d}.{month:02d}.{year}"

    # Определяем добор/недобор только по белкам
    protein_ok = protein >= PROTEIN_NORM

    if protein_ok:
        protein_percent = int((protein / PROTEIN_NORM) * 100) - 100
        status = f"✅ Добор: +{protein_percent}%"
    else:
        protein_percent = int((protein / PROTEIN_NORM) * 100)
        status = f"😞 Недобор: {protein_percent}%"

    text = (
        f"<b>📊 Данные за {date_title}</b>\n\n"
        f"Белки: <b>{format_number(protein)}</b>г\n"
        f"Жиры: <b>{format_number(fat)}</b>г\n\n"
        f"{status}"
    )

    keyboard = get_day_view_keyboard(year, month, day)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# ================== НАВИГАЦИЯ ПО ДНЯМ ==================

@dp.callback_query(F.data.startswith("day_prev:"))
async def day_prev(callback: CallbackQuery):
    _, year, month, day = callback.data.split(":")
    year, month, day = int(year), int(month), int(day)

    current_date = date(year, month, day)
    prev_date = current_date - timedelta(days=1)

    user_id = callback.from_user.id
    target_date = prev_date.isoformat()

    protein, fat = get_daily_totals(user_id, target_date)

    # Определяем добор/недобор только по белкам
    protein_ok = protein >= PROTEIN_NORM

    if protein_ok:
        protein_percent = int((protein / PROTEIN_NORM) * 100) - 100
        status = f"✅ Добор: +{protein_percent}%"
    else:
        protein_percent = int((protein / PROTEIN_NORM) * 100)
        status = f"😞 Недобор: {protein_percent}%"

    text = (
        f"<b>📊 Данные за {prev_date.strftime('%d.%m.%Y')}</b>\n\n"
        f"Белки: <b>{format_number(protein)}</b>г\n"
        f"Жиры: <b>{format_number(fat)}</b>г\n\n"
        f"{status}"
    )

    keyboard = get_day_view_keyboard(prev_date.year, prev_date.month, prev_date.day)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query(F.data.startswith("day_next:"))
async def day_next(callback: CallbackQuery):
    _, year, month, day = callback.data.split(":")
    year, month, day = int(year), int(month), int(day)

    current_date = date(year, month, day)
    next_date = current_date + timedelta(days=1)

    user_id = callback.from_user.id
    target_date = next_date.isoformat()

    protein, fat = get_daily_totals(user_id, target_date)

    # Определяем добор/недобор только по белкам
    protein_ok = protein >= PROTEIN_NORM

    if protein_ok:
        protein_percent = int((protein / PROTEIN_NORM) * 100) - 100
        status = f"✅ Добор: +{protein_percent}%"
    else:
        protein_percent = int((protein / PROTEIN_NORM) * 100)
        status = f"😞 Недобор: {protein_percent}%"

    text = (
        f"<b>📊 Данные за {next_date.strftime('%d.%m.%Y')}</b>\n\n"
        f"Белки: <b>{format_number(protein)}</b>г\n"
        f"Жиры: <b>{format_number(fat)}</b>г\n\n"
        f"{status}"
    )

    keyboard = get_day_view_keyboard(next_date.year, next_date.month, next_date.day)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# ================== ДОБАВИТЬ ИЗ ДНЯ ==================

@dp.callback_query(F.data.startswith("add_food_day:"))
async def add_food_from_calendar(callback: CallbackQuery):
    _, year, month, day = callback.data.split(":")
    year, month, day = int(year), int(month), int(day)
    
    keyboard = get_day_view_keyboard_with_add_type(year, month, day)
    await callback.message.edit_text(
        f"<b>📊 Данные за {day:02d}.{month:02d}.{year}</b>\n\n"
        f"Выберите тип добавления:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("add_serving_day:"))
async def add_serving_from_day(callback: CallbackQuery, state: FSMContext):
    _, year, month, day = callback.data.split(":")
    year, month, day = int(year), int(month), int(day)
    target_date = f"{year}-{month:02d}-{day:02d}"
    
    await state.update_data(target_date=target_date)
    await callback.message.answer(
        f"Введите данные для {day:02d}.{month:02d}.{year} в формате <b>Белки/Жиры</b>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(FoodInput.waiting_for_serving)


@dp.callback_query(F.data.startswith("add_100g_day:"))
async def add_100g_from_day(callback: CallbackQuery, state: FSMContext):
    _, year, month, day = callback.data.split(":")
    year, month, day = int(year), int(month), int(day)
    target_date = f"{year}-{month:02d}-{day:02d}"
    
    await state.update_data(target_date=target_date)
    await callback.message.answer(
        f"Введите данные для {day:02d}.{month:02d}.{year} в формате <b>Белки/Жиры Вес</b>\n"
        "(БЖ на 100г и вес порции в граммах)",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(FoodInput.waiting_for_100g)


# ================== УДАЛИТЬ ИЗ ДНЯ ==================

@dp.callback_query(F.data.startswith("remove_food_day:"))
async def remove_food_from_calendar(callback: CallbackQuery, state: FSMContext):
    _, year, month, day = callback.data.split(":")
    year, month, day = int(year), int(month), int(day)
    target_date = f"{year}-{month:02d}-{day:02d}"

    user_id = callback.from_user.id
    entries = get_food_entries_for_date(user_id, target_date)

    if not entries:
        await callback.answer(f"За {day:02d}.{month:02d}.{year} нет записей для удаления", show_alert=True)
        return

    await state.update_data(target_date=target_date)
    await callback.message.answer(
        f"Введите данные для удаления за {day:02d}.{month:02d}.{year} в формате <b>Белки/Жиры</b>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(FoodInput.waiting_for_remove)


# ================== СТАТИСТИКА ЗА НЕДЕЛЮ ==================

@dp.callback_query(F.data == "stats_week")
async def show_week_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    start_date, end_date = get_week_range()
    
    stats = get_week_stats(user_id, start_date, end_date)
    
    # Создаём словарь всех дней недели
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    
    all_days = {}
    current = start
    while current <= end:
        all_days[current.isoformat()] = {"protein": 0, "fat": 0}
        current += timedelta(days=1)
    
    # Заполняем данными
    for row in stats:
        all_days[row["entry_date"]] = {
            "protein": float(row["total_protein"]),
            "fat": float(row["total_fat"])
        }
    
    # Формируем сообщение
    lines = []
    total_protein = 0
    total_fat = 0
    
    for date_str in sorted(all_days.keys()):
        data = all_days[date_str]
        day_name = get_day_name(date_str)
        d = date.fromisoformat(date_str)
        date_formatted = d.strftime("%d.%m.%Y")
        
        protein = data["protein"]
        fat = data["fat"]
        total_protein += protein
        total_fat += fat

        # Определяем добор/недобор за день только по белкам
        protein_ok = protein >= PROTEIN_NORM

        if protein_ok:
            protein_percent = int((protein / PROTEIN_NORM) * 100) - 100
            lines.append(f"<b>{date_formatted} ({day_name})</b>")
            lines.append(f"  Белки: {format_number(protein)}г | Жиры: {format_number(fat)}г")
            lines.append(f"  ✅ Добор: +{protein_percent}% ✅")
        else:
            protein_percent = int((protein / PROTEIN_NORM) * 100)
            lines.append(f"<b>{date_formatted} ({day_name})</b>")
            lines.append(f"  Белки: {format_number(protein)}г | Жиры: {format_number(fat)}г")
            lines.append(f"  😞 Недобор: {protein_percent}% 😞")

        lines.append("")  # Пустая строка между днями

    # Итог
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"<b>📊 ИТОГО ЗА НЕДЕЛЮ</b>")
    lines.append(f"  Белки: {format_number(total_protein)}г / Жиры: {format_number(total_fat)}г")
    lines.append("")

    # Определяем добор/недобор за неделю только по белкам
    week_protein_ok = total_protein >= WEEKLY_PROTEIN_NORM

    if week_protein_ok:
        protein_percent = int((total_protein / WEEKLY_PROTEIN_NORM) * 100) - 100
        lines.append(f"✅ <b>Добор: +{protein_percent}%</b> ✅")
    else:
        protein_percent = int((total_protein / WEEKLY_PROTEIN_NORM) * 100)
        lines.append(f"😞 <b>Недобор: {protein_percent}%</b> 😞")

    text = "\n".join(lines)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 На главную", callback_data="back_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# ================== СТАТИСТИКА ЗА МЕСЯЦ ==================

@dp.callback_query(F.data == "stats_month")
async def show_month_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    year, month = get_month_range()

    stats = get_month_stats(user_id, year, month)

    if not stats:
        text = f"За {calendar.month_name[month]} {year} ещё нет записей"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 На главную", callback_data="back_main")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        return

    # Формируем сообщение
    total_protein = 0
    total_fat = 0

    for row in stats:
        protein = float(row["total_protein"])
        fat = float(row["total_fat"])
        total_protein += protein
        total_fat += fat

    # Итог как в статистике за неделю
    lines = []
    lines.append(f"<b>📊 ИТОГО ЗА {calendar.month_name[month].upper()} {year}</b>")
    lines.append(f"  Белки: {format_number(total_protein)}г | Жиры: {format_number(total_fat)}г")
    lines.append("")

    # Определяем добор/недобор за месяц только по белкам
    month_protein_ok = total_protein >= WEEKLY_PROTEIN_NORM

    if month_protein_ok:
        protein_percent = int((total_protein / WEEKLY_PROTEIN_NORM) * 100) - 100
        lines.append(f"✅ <b>Добор: +{protein_percent}%</b> ✅")
    else:
        protein_percent = int((total_protein / WEEKLY_PROTEIN_NORM) * 100)
        lines.append(f"😞 <b>Недобор: {protein_percent}%</b> 😞")

    text = "\n".join(lines)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 На главную", callback_data="back_main")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# ================== ОТМЕНА ==================

@dp.callback_query(F.data == "cancel_action")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer("Отменено")


# ================== НАЗАД ==================

@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "🤫 Запиши, сколько белок ты скушал сегодня",
        reply_markup=get_main_keyboard()
    )


@dp.callback_query(F.data.startswith("calendar_month:"))
async def back_to_calendar_month(callback: CallbackQuery):
    _, year, month = callback.data.split(":")
    year, month = int(year), int(month)

    keyboard = get_calendar_keyboard(year, month)
    await callback.message.edit_text(
        "<b>📅 Выберите дату</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# ================== ЗАПУСК ==================

async def main():
    init_db()
    logging.info("База данных инициализирована")

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот запущен...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

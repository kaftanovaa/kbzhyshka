import asyncio
import logging
import re
from datetime import date
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import BOT_TOKEN
from database import (
    init_db, add_user, user_exists, 
    add_food_entry, remove_food_entry, 
    get_daily_totals, get_food_entries_for_date,
    delete_food_entry_by_id, get_dates_with_entries
)
from keyboards import (
    get_main_keyboard, get_today_keyboard, 
    get_calendar_keyboard, get_day_view_keyboard
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# FSM состояния
class FoodInput(StatesGroup):
    waiting_for_food = State()
    waiting_for_remove = State()


# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# Форматирование числа (округление до 1 знака, если есть дробная часть)
def format_number(num: float) -> str:
    if num == int(num):
        return str(int(num))
    return f"{num:.1f}".rstrip('0').rstrip('.')


# Проверка формата ввода (число/число)
def parse_food_input(text: str) -> tuple:
    """Парсит ввод в формате 'белки/жиры'. Возвращает (protein, fat) или None."""
    # Разрешаем запятую или точку как разделитель десятичных
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


# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if not user_exists(user_id):
        add_user(user_id, username)
    
    await message.answer(
        "Привет! Я бот для подсчета чистого БЖ, без лишних данных о калориях и углеводах>3\n\n"
        "Выбери действие:",
        reply_markup=get_main_keyboard()
    )


# Главная - кнопка "Сегодня"
@dp.callback_query(F.data == "today")
async def show_today(callback: CallbackQuery):
    user_id = callback.from_user.id
    today = date.today().isoformat()
    
    protein, fat = get_daily_totals(user_id, today)
    
    text = (
        f"<b>📊 Данные за сегодня ({date.today().strftime('%d.%m.%Y')})</b>\n\n"
        f"Белки: <b>{format_number(protein)}</b>г\n"
        f"Жиры: <b>{format_number(fat)}</b>г"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_today_keyboard(),
        parse_mode="HTML"
    )


# Добавить ням-ням (сегодня)
@dp.callback_query(F.data == "add_food")
async def start_add_food(callback: CallbackQuery, state: FSMContext):
    await state.update_data(target_date=date.today().isoformat())
    await callback.message.answer(
        "Введите данные в формате <b>Белки/Жиры</b>\n"
        "Пример: 50/60 или 23,5/22,2",
        parse_mode="HTML"
    )
    await state.set_state(FoodInput.waiting_for_food)


# Обработка ввода для добавления
@dp.message(FoodInput.waiting_for_food)
async def process_add_food(message: Message, state: FSMContext):
    data = await state.get_data()
    target_date = data.get("target_date", date.today().isoformat())
    user_id = message.from_user.id

    result = parse_food_input(message.text)
    if result is None:
        await message.answer(
            "❌ Некорректный ввод, введите в формате <b>Белки/Жиры</b>\n"
            "Пример: 50/60 или 23,5/22,2",
            parse_mode="HTML"
        )
        return

    protein, fat = result

    add_food_entry(user_id, target_date, protein, fat)

    # Обновляем данные
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

    # Редактируем последнее сообщение с данными (если есть)
    try:
        # Ищем последнее сообщение бота с данными
        async for msg in message.bot.get_chat_history(message.chat.id, limit=5):
            if msg.from_user.id == bot.id and msg.reply_markup:
                await msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
                break
    except:
        # Если не получилось отредактировать — отправляем новое
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await state.clear()


# Удалить ням-ням (сегодня)
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
        "Введите данные для удаления в формате <b>Белки/Жиры</b>\n"
        "Пример: 50/60 или 23,5/22,2\n\n"
        "<i>Будет удалена одна запись с такими значениями</i>",
        parse_mode="HTML"
    )
    await state.set_state(FoodInput.waiting_for_remove)


# Обработка ввода для удаления
@dp.message(FoodInput.waiting_for_remove)
async def process_remove_food(message: Message, state: FSMContext):
    data = await state.get_data()
    target_date = data.get("target_date", date.today().isoformat())

    result = parse_food_input(message.text)
    if result is None:
        await message.answer(
            "❌ Некорректный ввод, введите в формате <b>Белки/Жиры</b>\n"
            "Пример: 50/60 или 23,5/22,2",
            parse_mode="HTML"
        )
        return

    protein, fat = result
    user_id = message.from_user.id

    removed = remove_food_entry(user_id, target_date, protein, fat)

    if not removed:
        await message.answer(
            "❌ Запись с такими значениями не найдена.\n"
            "Проверьте введённые данные.",
            parse_mode="HTML"
        )
        return

    # Обновляем данные
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

    # Редактируем последнее сообщение с данными (если есть)
    try:
        async for msg in message.bot.get_chat_history(message.chat.id, limit=5):
            if msg.from_user.id == bot.id and msg.reply_markup:
                await msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
                break
    except:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await state.clear()


# Календарь - главный экран
@dp.callback_query(F.data == "calendar_main")
async def show_calendar_main(callback: CallbackQuery):
    today = date.today()
    keyboard = get_calendar_keyboard(today.year, today.month)
    
    await callback.message.edit_text(
        "<b>📅 Выберите дату</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# Календарь - переключение месяца
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
        "<b> Выберите дату</b>",
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
        "<b> Выберите дату</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# Календарь - выбор дня
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
    
    text = (
        f"<b> Данные за {date_title}</b>\n\n"
        f"Белки: <b>{format_number(protein)}</b>г\n"
        f"Жиры: <b>{format_number(fat)}</b>г"
    )
    
    keyboard = get_day_view_keyboard(year, month, day)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# Из календаря - добавить ням-ням
@dp.callback_query(F.data.startswith("add_food_day:"))
async def add_food_from_calendar(callback: CallbackQuery, state: FSMContext):
    _, year, month, day = callback.data.split(":")
    year, month, day = int(year), int(month), int(day)
    target_date = f"{year}-{month:02d}-{day:02d}"

    await state.update_data(target_date=target_date)
    await callback.message.answer(
        f"Введите данные для <b>{day:02d}.{month:02d}.{year}</b> в формате <b>Белки/Жиры</b>\n"
        "Пример: 50/60 или 23,5/22,2",
        parse_mode="HTML"
    )
    await state.set_state(FoodInput.waiting_for_food)


# Из календаря - удалить ням-ням
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
        f"Введите данные для удаления за <b>{day:02d}.{month:02d}.{year}</b>\n"
        "Формат: <b>Белки/Жиры</b> (пример: 50/60)",
        parse_mode="HTML"
    )
    await state.set_state(FoodInput.waiting_for_remove)


# Назад в главное меню
@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "Привет! Я бот для подсчета чистого БЖ, без лишних данных о калориях и углеводах>3\n\n"
        "Выбери действие:",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


# Календарь - месяц из кнопки (для возврата)
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


# Запуск бота
async def main():
    # Инициализация БД
    init_db()
    logging.info("База данных инициализирована")
    
    # Удаление вебхуков (для локального запуска)
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот запущен...")
    
    # Запуск polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

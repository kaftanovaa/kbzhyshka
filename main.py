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
    init_db, add_user, user_exists, user_has_settings, save_user_settings, get_user_settings,
    add_food_entry, remove_food_entry,
    get_daily_totals, get_food_entries_for_date,
    delete_food_entry_by_id, get_dates_with_entries,
    get_week_stats, get_month_stats
)
from keyboards import (
    get_main_keyboard, get_today_keyboard,
    get_calendar_keyboard, get_day_view_keyboard,
    get_add_food_type_keyboard, get_cancel_keyboard,
    get_day_view_keyboard_with_add_type,
    get_gender_keyboard, get_activity_keyboard,
    get_goal_keyboard, get_deficit_keyboard
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# FSM состояния
class Onboarding(StatesGroup):
    waiting_gender = State()
    waiting_weight = State()
    waiting_height = State()
    waiting_age = State()
    waiting_activity = State()
    waiting_goal = State()
    waiting_deficit = State()


class FoodInput(StatesGroup):
    waiting_for_serving = State()
    waiting_for_100g = State()
    waiting_for_remove = State()


# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ================== УТИЛИТЫ ==================

def format_number(num: float) -> str:
    """Форматирование числа."""
    if num == int(num):
        return str(int(num))
    return f"{num:.1f}".rstrip('0').rstrip('.')


def parse_number(text: str) -> float:
    """Парсит число из строки (целое или дробное)."""
    text = text.strip().replace(',', '.')
    try:
        return float(text)
    except ValueError:
        return None


def parse_serving_input(text: str) -> tuple:
    """Парсит ввод: калории/белки/жиры/углеводы. Возвращает (cal, prot, fat, carb) или None."""
    text = text.strip()
    pattern = r'^(\d+[.,]?\d*)\s*/\s*(\d+[.,]?\d*)\s*/\s*(\d+[.,]?\d*)\s*/\s*(\d+[.,]?\d*)$'
    match = re.match(pattern, text)
    if match:
        try:
            cal = float(match.group(1).replace(',', '.'))
            prot = float(match.group(2).replace(',', '.'))
            fat = float(match.group(3).replace(',', '.'))
            carb = float(match.group(4).replace(',', '.'))
            return (cal, prot, fat, carb)
        except ValueError:
            return None
    return None


def parse_100g_input(text: str) -> tuple:
    """Парсит ввод: калории/белки/жиры/углеводы вес. Возвращает (cal_per_100, prot_per_100, fat_per_100, carb_per_100, weight) или None."""
    text = text.strip()
    pattern = r'^(\d+[.,]?\d*)\s*/\s*(\d+[.,]?\d*)\s*/\s*(\d+[.,]?\d*)\s*/\s*(\d+[.,]?\d*)\s+(\d+[.,]?\d*)$'
    match = re.match(pattern, text)
    if match:
        try:
            cal_per_100 = float(match.group(1).replace(',', '.'))
            prot_per_100 = float(match.group(2).replace(',', '.'))
            fat_per_100 = float(match.group(3).replace(',', '.'))
            carb_per_100 = float(match.group(4).replace(',', '.'))
            weight = float(match.group(5).replace(',', '.'))
            return (cal_per_100, prot_per_100, fat_per_100, carb_per_100, weight)
        except ValueError:
            return None
    return None


def get_day_name(date_str: str) -> str:
    """Название дня недели."""
    year, month, day = map(int, date_str.split('-'))
    d = date(year, month, day)
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return days[d.weekday()]


def get_week_range(target_date: date = None) -> tuple:
    """(start_date, end_date) для текущей недели (пн-вс)."""
    if target_date is None:
        target_date = date.today()
    monday = target_date - timedelta(days=target_date.weekday())
    sunday = monday + timedelta(days=6)
    return (monday.isoformat(), sunday.isoformat())


def get_month_range(target_date: date = None) -> tuple:
    """(year, month) для текущего месяца."""
    if target_date is None:
        target_date = date.today()
    return (target_date.year, target_date.month)


def calculate_norms(gender: str, weight: float, height: float, age: int,
                    activity_coeff: float, activity_label: str,
                    goal: str, deficit_label: str = None) -> dict:
    """Рассчитать персонализированные нормы КБЖУ."""
    # Формула Миффлина-Сан Жеора
    if gender == "female":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5

    # Умножаем на коэффициент активности
    daily_calories = bmr * activity_coeff

    # Корректировка по цели
    if goal == "loss":
        if deficit_label == "small":
            daily_calories *= 0.90
        elif deficit_label == "medium":
            daily_calories *= 0.85
        else:  # large
            daily_calories *= 0.80
    elif goal == "gain":
        daily_calories *= 1.20
    # maintain — ничего не меняем

    daily_calories = round(daily_calories, 1)

    # Белки: 2г на кг веса
    protein_norm = round(2 * weight, 1)
    # Жиры: 1г на кг веса
    fat_norm = round(1 * weight, 1)
    # Углеводы: остаток калорий
    # 1г белка = 4 ккал, 1г жира = 9 ккал, 1г углеводов = 4 ккал
    calories_from_protein = protein_norm * 4
    calories_from_fat = fat_norm * 9
    remaining_calories = daily_calories - calories_from_protein - calories_from_fat
    carbs_norm = round(remaining_calories / 4, 1) if remaining_calories > 0 else 0

    return {
        "daily_calories": daily_calories,
        "protein_norm": protein_norm,
        "fat_norm": fat_norm,
        "carbs_norm": carbs_norm
    }


def get_status_text(current: float, norm: float, label: str) -> str:
    """Текст статуса для одного нутриента."""
    if norm == 0:
        return ""
    percent = int((current / norm) * 100)
    if current >= norm:
        over = percent - 100
        return f"{label}: {format_number(current)}г/{format_number(norm)}г ✅ Добор: +{over}%"
    else:
        return f"{label}: {format_number(current)}г/{format_number(norm)}г 😞 Недобор: {percent}%"


def get_day_status(current: float, norm: float) -> str:
    """Статус для одного нутриента (короткий)."""
    if norm == 0:
        return ""
    percent = int((current / norm) * 100)
    if current >= norm:
        over = percent - 100
        return f"✅ Добор: +{over}%"
    else:
        return f"😞 Недобор: {percent}%"


# ================== КОМАНДА /START ==================

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username

    if not user_exists(user_id):
        add_user(user_id, username)

    settings = get_user_settings(user_id)
    if settings:
        await state.clear()
        await message.answer(
            "🤫 Запиши, сколько КБЖУ ты скушал сегодня",
            reply_markup=get_main_keyboard(has_settings=True)
        )
    else:
        await state.set_state(Onboarding.waiting_gender)
        await message.answer(
            "Привет! Я бот для подсчёта КБЖУ (калории, белки, жиры, углеводы).\n\n"
            "Давай рассчитаю твою персональную норму! 🎯\n\n"
            "Укажи свой пол:"
        )
        await message.answer(
            "Выбери пол:",
            reply_markup=get_gender_keyboard()
        )


# ================== ОНБОРДИНГ ==================

@dp.callback_query(F.data.startswith("gender_"), Onboarding.waiting_gender)
async def onboarding_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split("_")[1]  # male или female
    await state.update_data(gender=gender)
    await callback.message.answer(
        "Теперь укажи свой вес (кг):"
    )
    await state.set_state(Onboarding.waiting_weight)


@dp.message(Onboarding.waiting_weight)
async def onboarding_weight(message: Message, state: FSMContext):
    weight = parse_number(message.text)
    if weight is None or weight <= 0:
        await message.answer("❌ Введи корректный вес (число, кг):")
        return

    await state.update_data(weight=weight)
    await message.answer("Теперь укажи свой рост (см):")
    await state.set_state(Onboarding.waiting_height)


@dp.message(Onboarding.waiting_height)
async def onboarding_height(message: Message, state: FSMContext):
    height = parse_number(message.text)
    if height is None or height <= 0:
        await message.answer("❌ Введи корректный рост (число, см):")
        return

    await state.update_data(height=height)
    await message.answer("Теперь укажи свой возраст (полных лет):")
    await state.set_state(Onboarding.waiting_age)


@dp.message(Onboarding.waiting_age)
async def onboarding_age(message: Message, state: FSMContext):
    age_val = parse_number(message.text)
    if age_val is None or age_val <= 0 or age_val != int(age_val):
        await message.answer("❌ Введи корректный возраст (целое число):")
        return

    await state.update_data(age=int(age_val))
    await message.answer(
        "Какой у тебя уровень активности?",
        reply_markup=get_activity_keyboard()
    )
    await state.set_state(Onboarding.waiting_activity)


@dp.callback_query(F.data.startswith("activity_"), Onboarding.waiting_activity)
async def onboarding_activity(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    coeff = float(parts[1])

    labels = {
        "1.2": "Сидячий образ жизни",
        "1.375": "Лёгкая активность",
        "1.55": "Умеренная активность",
        "1.725": "Высокая активность",
        "1.9": "Очень высокая активность"
    }

    await state.update_data(activity_coefficient=coeff, activity_label=labels.get(parts[1], ""))
    await callback.message.answer(
        "Какая у тебя цель?",
        reply_markup=get_goal_keyboard()
    )
    await state.set_state(Onboarding.waiting_goal)


@dp.callback_query(F.data.startswith("goal_"), Onboarding.waiting_goal)
async def onboarding_goal(callback: CallbackQuery, state: FSMContext):
    goal = callback.data.split("_")[1]

    if goal == "loss":
        await state.update_data(goal=goal)
        await callback.message.answer(
            "Какой дефицит калорий хочешь?",
            reply_markup=get_deficit_keyboard()
        )
        await state.set_state(Onboarding.waiting_deficit)
    else:
        await state.update_data(goal=goal, deficit_label=None)
        # Рассчитываем нормы сразу
        await finish_onboarding(callback, state)


@dp.callback_query(F.data.startswith("deficit_"), Onboarding.waiting_deficit)
async def onboarding_deficit(callback: CallbackQuery, state: FSMContext):
    deficit = callback.data.split("_")[1]

    labels = {
        "small": "Небольшой",
        "medium": "Средний",
        "large": "Большой"
    }

    await state.update_data(deficit_label=labels.get(deficit, ""))
    await finish_onboarding(callback, state)


async def finish_onboarding(callback: CallbackQuery, state: FSMContext):
    """Завершение онбординга: расчёт и сохранение норм."""
    data = await state.get_data()
    user_id = callback.from_user.id

    gender = data["gender"]
    weight = data["weight"]
    height = data["height"]
    age = data["age"]
    activity_coeff = data["activity_coefficient"]
    activity_label = data["activity_label"]
    goal = data["goal"]
    deficit_label = data.get("deficit_label")

    norms = calculate_norms(gender, weight, height, age, activity_coeff, activity_label, goal, deficit_label)

    # Сохраняем в БД
    save_user_settings(
        user_id=user_id,
        gender=gender,
        weight=weight,
        height=height,
        age=age,
        activity_coefficient=activity_coeff,
        activity_label=activity_label,
        goal=goal,
        deficit_label=deficit_label,
        daily_calories=norms["daily_calories"],
        protein_norm=norms["protein_norm"],
        fat_norm=norms["fat_norm"],
        carbs_norm=norms["carbs_norm"]
    )

    goal_labels = {"loss": "Похудение", "maintain": "Поддержание", "gain": "Набор веса"}

    result_text = (
        f"🎉 Готово! Твоя персональная норма:\n\n"
        f"🔥 Калории: <b>{format_number(norms['daily_calories'])}</b> ккал\n"
        f"🥩 Белки: <b>{format_number(norms['protein_norm'])}</b>г\n"
        f"🥑 Жиры: <b>{format_number(norms['fat_norm'])}</b>г\n"
        f"🍞 Углеводы: <b>{format_number(norms['carbs_norm'])}</b>г\n\n"
        f"Цель: {goal_labels.get(goal, goal)}"
    )

    await callback.message.answer(result_text, parse_mode="HTML")
    await state.clear()

    # Показываем главное меню
    await callback.message.answer(
        "🤫 Запиши, сколько КБЖУ ты скушал сегодня",
        reply_markup=get_main_keyboard(has_settings=True)
    )


# ================== ПЕРЕСЧЁТ НОРМЫ ==================

@dp.callback_query(F.data == "recalc_norm")
async def recalc_norm(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Давай пересчитаем норму! Укажи свой пол:",
        reply_markup=get_gender_keyboard()
    )
    await state.set_state(Onboarding.waiting_gender)


# ================== ГЛАВНАЯ — СЕГОДНЯ ==================

@dp.callback_query(F.data == "today")
async def show_today(callback: CallbackQuery):
    user_id = callback.from_user.id
    today = date.today().isoformat()

    cal, prot, fat, carb = get_daily_totals(user_id, today)
    settings = get_user_settings(user_id)

    if not settings:
        text = (
            f"<b>📊 Данные за сегодня ({date.today().strftime('%d.%m.%Y')})</b>\n\n"
            f"Калории: <b>{format_number(cal)}</b> ккал\n"
            f"Белки: <b>{format_number(prot)}</b>г\n"
            f"Жиры: <b>{format_number(fat)}</b>г\n"
            f"Углеводы: <b>{format_number(carb)}</b>г"
        )
    else:
        cal_norm = settings["daily_calories"]
        prot_norm = settings["protein_norm"]
        fat_norm = settings["fat_norm"]
        carb_norm = settings["carbs_norm"]

        lines = [
            f"<b>📊 Данные за сегодня ({date.today().strftime('%d.%m.%Y')})</b>",
            "",
            f"🔥 Калории: {format_number(cal)}/{format_number(cal_norm)} ккал — {get_day_status(cal, cal_norm)}",
            f"🥩 Белки: {format_number(prot)}/{format_number(prot_norm)}г — {get_day_status(prot, prot_norm)}",
            f"🥑 Жиры: {format_number(fat)}/{format_number(fat_norm)}г — {get_day_status(fat, fat_norm)}",
            f"🍞 Углеводы: {format_number(carb)}/{format_number(carb_norm)}г — {get_day_status(carb, carb_norm)}"
        ]
        text = "\n".join(lines)

    await callback.message.edit_text(text, reply_markup=get_today_keyboard(), parse_mode="HTML")


# ================== ДОБАВИТЬ ЕДУ — ВЫБОР ТИПА ==================

@dp.callback_query(F.data == "add_food")
async def start_add_food_type(callback: CallbackQuery):
    await callback.message.answer(
        "Выбери тип ввода:",
        reply_markup=get_add_food_type_keyboard()
    )


@dp.callback_query(F.data == "cancel_add")
async def cancel_add(callback: CallbackQuery):
    await callback.message.edit_text(
        "❌ Отменено",
        reply_markup=get_main_keyboard(has_settings=True)
    )


# ================== ДОБАВИТЬ НА ПОРЦИЮ ==================

@dp.callback_query(F.data == "add_per_serving")
async def start_add_serving(callback: CallbackQuery, state: FSMContext):
    await state.update_data(target_date=date.today().isoformat())
    await callback.message.answer(
        "Введи в формате: <b>Калории/Белки/Жиры/Углеводы</b>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(FoodInput.waiting_for_serving)


@dp.message(FoodInput.waiting_for_serving)
async def process_add_serving(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return

    data = await state.get_data()
    target_date = data.get("target_date", date.today().isoformat())
    user_id = message.from_user.id

    result = parse_serving_input(message.text)
    if result is None:
        await message.answer(
            "❌ Некорректный ввод. Формат: <b>Калории/Белки/Жиры/Углеводы</b>\n"
            "Пример: 100/20/30/40",
            parse_mode="HTML"
        )
        return

    cal, prot, fat, carb = result
    add_food_entry(user_id, target_date, cal, prot, fat, carb)

    total_cal, total_prot, total_fat, total_carb = get_daily_totals(user_id, target_date)

    if target_date == date.today().isoformat():
        text = (
            f"<b>📊 Данные за сегодня ({date.today().strftime('%d.%m.%Y')})</b>\n\n"
            f"🔥 Калории: <b>{format_number(total_cal)}</b> ккал\n"
            f"🥩 Белки: <b>{format_number(total_prot)}</b>г\n"
            f"🥑 Жиры: <b>{format_number(total_fat)}</b>г\n"
            f"🍞 Углеводы: <b>{format_number(total_carb)}</b>г\n\n"
            f"✅ Добавлено: {format_number(cal)} ккал / {format_number(prot)}г / {format_number(fat)}г / {format_number(carb)}г"
        )
        keyboard = get_today_keyboard()
    else:
        year, month, day = map(int, target_date.split('-'))
        text = (
            f"<b>📊 Данные за {day:02d}.{month:02d}.{year}</b>\n\n"
            f"🔥 Калории: <b>{format_number(total_cal)}</b> ккал\n"
            f"🥩 Белки: <b>{format_number(total_prot)}</b>г\n"
            f"🥑 Жиры: <b>{format_number(total_fat)}</b>г\n"
            f"🍞 Углеводы: <b>{format_number(total_carb)}</b>г\n\n"
            f"✅ Добавлено: {format_number(cal)} ккал / {format_number(prot)}г / {format_number(fat)}г / {format_number(carb)}г"
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
        "Введи в формате: <b>Калории/Белки/Жиры/Углеводы Вес</b>\n"
        "(КБЖУ на 100г + вес порции)",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(FoodInput.waiting_for_100g)


@dp.message(FoodInput.waiting_for_100g)
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
            "❌ Некорректный ввод. Формат: <b>Калории/Белки/Жиры/Углеводы Вес</b>\n"
            "Пример: 100/20/30/40 150",
            parse_mode="HTML"
        )
        return

    cal_per_100, prot_per_100, fat_per_100, carb_per_100, weight = result

    cal = (cal_per_100 * weight) / 100
    prot = (prot_per_100 * weight) / 100
    fat = (fat_per_100 * weight) / 100
    carb = (carb_per_100 * weight) / 100

    add_food_entry(user_id, target_date, cal, prot, fat, carb)

    total_cal, total_prot, total_fat, total_carb = get_daily_totals(user_id, target_date)

    if target_date == date.today().isoformat():
        text = (
            f"<b>📊 Данные за сегодня ({date.today().strftime('%d.%m.%Y')})</b>\n\n"
            f"🔥 Калории: <b>{format_number(total_cal)}</b> ккал\n"
            f"🥩 Белки: <b>{format_number(total_prot)}</b>г\n"
            f"🥑 Жиры: <b>{format_number(total_fat)}</b>г\n"
            f"🍞 Углеводы: <b>{format_number(total_carb)}</b>г\n\n"
            f"✅ Добавлено: {format_number(cal)} ккал / {format_number(prot)}г / {format_number(fat)}г / {format_number(carb)}г\n"
            f"<i>(Для {format_number(weight)}г)</i>"
        )
        keyboard = get_today_keyboard()
    else:
        year, month, day = map(int, target_date.split('-'))
        text = (
            f"<b>📊 Данные за {day:02d}.{month:02d}.{year}</b>\n\n"
            f"🔥 Калории: <b>{format_number(total_cal)}</b> ккал\n"
            f"🥩 Белки: <b>{format_number(total_prot)}</b>г\n"
            f"🥑 Жиры: <b>{format_number(total_fat)}</b>г\n"
            f"🍞 Углеводы: <b>{format_number(total_carb)}</b>г\n\n"
            f"✅ Добавлено: {format_number(cal)} ккал / {format_number(prot)}г / {format_number(fat)}г / {format_number(carb)}г\n"
            f"<i>(Для {format_number(weight)}г)</i>"
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


# ================== УДАЛИТЬ ЕДУ ==================

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
        "Введи данные для удаления: <b>Калории/Белки/Жиры/Углеводы</b>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(FoodInput.waiting_for_remove)


@dp.message(FoodInput.waiting_for_remove)
async def process_remove_food(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return

    data = await state.get_data()
    target_date = data.get("target_date", date.today().isoformat())

    result = parse_serving_input(message.text)
    if result is None:
        await message.answer(
            "❌ Некорректный ввод. Формат: <b>Калории/Белки/Жиры/Углеводы</b>",
            parse_mode="HTML"
        )
        return

    cal, prot, fat, carb = result
    user_id = message.from_user.id

    remove_food_entry(user_id, target_date, cal, prot, fat, carb)

    total_cal, total_prot, total_fat, total_carb = get_daily_totals(user_id, target_date)

    if target_date == date.today().isoformat():
        text = (
            f"<b>📊 Данные за сегодня ({date.today().strftime('%d.%m.%Y')})</b>\n\n"
            f"🔥 Калории: <b>{format_number(total_cal)}</b> ккал\n"
            f"🥩 Белки: <b>{format_number(total_prot)}</b>г\n"
            f"🥑 Жиры: <b>{format_number(total_fat)}</b>г\n"
            f"🍞 Углеводы: <b>{format_number(total_carb)}</b>г\n\n"
            f"✅ Удалено: {format_number(cal)} ккал / {format_number(prot)}г / {format_number(fat)}г / {format_number(carb)}г"
        )
        keyboard = get_today_keyboard()
    else:
        year, month, day = map(int, target_date.split('-'))
        text = (
            f"<b>📊 Данные за {day:02d}.{month:02d}.{year}</b>\n\n"
            f"🔥 Калории: <b>{format_number(total_cal)}</b> ккал\n"
            f"🥩 Белки: <b>{format_number(total_prot)}</b>г\n"
            f"🥑 Жиры: <b>{format_number(total_fat)}</b>г\n"
            f"🍞 Углеводы: <b>{format_number(total_carb)}</b>г\n\n"
            f"✅ Удалено: {format_number(cal)} ккал / {format_number(prot)}г / {format_number(fat)}г / {format_number(carb)}г"
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
    await callback.message.edit_text("<b>📆 Выбери дату</b>", reply_markup=keyboard, parse_mode="HTML")


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
    await callback.message.edit_text("<b>📆 Выбери дату</b>", reply_markup=keyboard, parse_mode="HTML")


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
    await callback.message.edit_text("<b>📆 Выбери дату</b>", reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query(F.data.startswith("cal_day:"))
async def calendar_select_day(callback: CallbackQuery):
    _, year, month, day = callback.data.split(":")
    year, month, day = int(year), int(month), int(day)

    user_id = callback.from_user.id
    target_date = f"{year}-{month:02d}-{day:02d}"
    cal, prot, fat, carb = get_daily_totals(user_id, target_date)
    settings = get_user_settings(user_id)

    today = date.today()
    if target_date == today.isoformat():
        date_title = "сегодня"
    else:
        date_title = f"{day:02d}.{month:02d}.{year}"

    if not settings:
        lines = [
            f"<b>📊 Данные за {date_title}</b>",
            "",
            f"🔥 Калории: <b>{format_number(cal)}</b> ккал",
            f"🥩 Белки: <b>{format_number(prot)}</b>г",
            f"🥑 Жиры: <b>{format_number(fat)}</b>г",
            f"🍞 Углеводы: <b>{format_number(carb)}</b>г"
        ]
    else:
        cal_norm = settings["daily_calories"]
        prot_norm = settings["protein_norm"]
        fat_norm = settings["fat_norm"]
        carb_norm = settings["carbs_norm"]

        lines = [
            f"<b>📊 Данные за {date_title}</b>",
            "",
            f"🔥 Калории: {format_number(cal)}/{format_number(cal_norm)} ккал — {get_day_status(cal, cal_norm)}",
            f"🥩 Белки: {format_number(prot)}/{format_number(prot_norm)}г — {get_day_status(prot, prot_norm)}",
            f"🥑 Жиры: {format_number(fat)}/{format_number(fat_norm)}г — {get_day_status(fat, fat_norm)}",
            f"🍞 Углеводы: {format_number(carb)}/{format_number(carb_norm)}г — {get_day_status(carb, carb_norm)}"
        ]

    text = "\n".join(lines)
    keyboard = get_day_view_keyboard(year, month, day)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# ================== НАВИГАЦИЯ ПО ДНЯМ ==================

@dp.callback_query(F.data.startswith("day_prev:"))
async def day_prev(callback: CallbackQuery):
    _, year, month, day = callback.data.split(":")
    year, month, day = int(year), int(month), int(day)

    prev_date = date(year, month, day) - timedelta(days=1)
    user_id = callback.from_user.id
    cal, prot, fat, carb = get_daily_totals(user_id, prev_date.isoformat())
    settings = get_user_settings(user_id)

    if not settings:
        lines = [
            f"<b>📊 Данные за {prev_date.strftime('%d.%m.%Y')}</b>",
            "",
            f"🔥 Калории: <b>{format_number(cal)}</b> ккал",
            f"🥩 Белки: <b>{format_number(prot)}</b>г",
            f"🥑 Жиры: <b>{format_number(fat)}</b>г",
            f"🍞 Углеводы: <b>{format_number(carb)}</b>г"
        ]
    else:
        lines = [
            f"<b>📊 Данные за {prev_date.strftime('%d.%m.%Y')}</b>",
            "",
            f"🔥 Калории: {format_number(cal)}/{format_number(settings['daily_calories'])} ккал — {get_day_status(cal, settings['daily_calories'])}",
            f"🥩 Белки: {format_number(prot)}/{format_number(settings['protein_norm'])}г — {get_day_status(prot, settings['protein_norm'])}",
            f"🥑 Жиры: {format_number(fat)}/{format_number(settings['fat_norm'])}г — {get_day_status(fat, settings['fat_norm'])}",
            f"🍞 Углеводы: {format_number(carb)}/{format_number(settings['carbs_norm'])}г — {get_day_status(carb, settings['carbs_norm'])}"
        ]

    text = "\n".join(lines)
    keyboard = get_day_view_keyboard(prev_date.year, prev_date.month, prev_date.day)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query(F.data.startswith("day_next:"))
async def day_next(callback: CallbackQuery):
    _, year, month, day = callback.data.split(":")
    year, month, day = int(year), int(month), int(day)

    next_date = date(year, month, day) + timedelta(days=1)
    user_id = callback.from_user.id
    cal, prot, fat, carb = get_daily_totals(user_id, next_date.isoformat())
    settings = get_user_settings(user_id)

    if not settings:
        lines = [
            f"<b>📊 Данные за {next_date.strftime('%d.%m.%Y')}</b>",
            "",
            f"🔥 Калории: <b>{format_number(cal)}</b> ккал",
            f"🥩 Белки: <b>{format_number(prot)}</b>г",
            f"🥑 Жиры: <b>{format_number(fat)}</b>г",
            f"🍞 Углеводы: <b>{format_number(carb)}</b>г"
        ]
    else:
        lines = [
            f"<b>📊 Данные за {next_date.strftime('%d.%m.%Y')}</b>",
            "",
            f"🔥 Калории: {format_number(cal)}/{format_number(settings['daily_calories'])} ккал — {get_day_status(cal, settings['daily_calories'])}",
            f"🥩 Белки: {format_number(prot)}/{format_number(settings['protein_norm'])}г — {get_day_status(prot, settings['protein_norm'])}",
            f"🥑 Жиры: {format_number(fat)}/{format_number(settings['fat_norm'])}г — {get_day_status(fat, settings['fat_norm'])}",
            f"🍞 Углеводы: {format_number(carb)}/{format_number(settings['carbs_norm'])}г — {get_day_status(carb, settings['carbs_norm'])}"
        ]

    text = "\n".join(lines)
    keyboard = get_day_view_keyboard(next_date.year, next_date.month, next_date.day)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# ================== ДОБАВИТЬ ИЗ ДНЯ ==================

@dp.callback_query(F.data.startswith("add_food_day:"))
async def add_food_from_calendar(callback: CallbackQuery):
    _, year, month, day = callback.data.split(":")
    year, month, day = int(year), int(month), int(day)

    cal, prot, fat, carb = get_daily_totals(callback.from_user.id, f"{year}-{month:02d}-{day:02d}")
    settings = get_user_settings(callback.from_user.id)

    if not settings:
        text = (
            f"<b>📊 Данные за {day:02d}.{month:02d}.{year}</b>\n\n"
            f"🔥 Калории: <b>{format_number(cal)}</b> ккал\n"
            f"🥩 Белки: <b>{format_number(prot)}</b>г\n"
            f"🥑 Жиры: <b>{format_number(fat)}</b>г\n"
            f"🍞 Углеводы: <b>{format_number(carb)}</b>г\n\n"
            "Выбери тип добавления:"
        )
    else:
        lines = [
            f"<b>📊 Данные за {day:02d}.{month:02d}.{year}</b>",
            "",
            f"🔥 Калории: {format_number(cal)}/{format_number(settings['daily_calories'])} ккал — {get_day_status(cal, settings['daily_calories'])}",
            f"🥩 Белки: {format_number(prot)}/{format_number(settings['protein_norm'])}г — {get_day_status(prot, settings['protein_norm'])}",
            f"🥑 Жиры: {format_number(fat)}/{format_number(settings['fat_norm'])}г — {get_day_status(fat, settings['fat_norm'])}",
            f"🍞 Углеводы: {format_number(carb)}/{format_number(settings['carbs_norm'])}г — {get_day_status(carb, settings['carbs_norm'])}",
            "",
            "Выбери тип добавления:"
        ]
        text = "\n".join(lines)

    keyboard = get_day_view_keyboard_with_add_type(year, month, day)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query(F.data.startswith("add_serving_day:"))
async def add_serving_from_day(callback: CallbackQuery, state: FSMContext):
    _, year, month, day = callback.data.split(":")
    year, month, day = int(year), int(month), int(day)
    target_date = f"{year}-{month:02d}-{day:02d}"

    await state.update_data(target_date=target_date)
    await callback.message.answer(
        f"Введи данные для {day:02d}.{month:02d}.{year}: <b>Калории/Белки/Жиры/Углеводы</b>",
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
        f"Введи данные для {day:02d}.{month:02d}.{year}: <b>Калории/Белки/Жиры/Углеводы Вес</b>",
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
        await callback.answer(f"За {day:02d}.{month:02d}.{year} нет записей", show_alert=True)
        return

    await state.update_data(target_date=target_date)
    await callback.message.answer(
        f"Введи данные для удаления за {day:02d}.{month:02d}.{year}: <b>Калории/Белки/Жиры/Углеводы</b>",
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
    settings = get_user_settings(user_id)

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    all_days = {}
    current = start
    while current <= end:
        all_days[current.isoformat()] = {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}
        current += timedelta(days=1)

    for row in stats:
        all_days[row["entry_date"]] = {
            "calories": float(row["total_calories"]),
            "protein": float(row["total_protein"]),
            "fat": float(row["total_fat"]),
            "carbs": float(row["total_carbs"])
        }

    lines = []
    total_cal = 0
    total_prot = 0
    total_fat = 0
    total_carb = 0

    for date_str in sorted(all_days.keys()):
        data = all_days[date_str]
        day_name = get_day_name(date_str)
        d = date.fromisoformat(date_str)
        date_formatted = d.strftime("%d.%m.%Y")

        cal = data["calories"]
        prot = data["protein"]
        fat = data["fat"]
        carb = data["carbs"]
        total_cal += cal
        total_prot += prot
        total_fat += fat
        total_carb += carb

        lines.append(f"<b>{date_formatted} ({day_name})</b>")
        lines.append(f"  🔥 {format_number(cal)} ккал | 🥩 {format_number(prot)}г | 🥑 {format_number(fat)}г | 🍞 {format_number(carb)}г")

        if settings:
            statuses = []
            if cal >= settings["daily_calories"]:
                p = int((cal / settings["daily_calories"]) * 100) - 100
                statuses.append(f"ккал ✅+{p}%")
            else:
                p = int((cal / settings["daily_calories"]) * 100)
                statuses.append(f"ккал 😞{p}%")
            if prot >= settings["protein_norm"]:
                p = int((prot / settings["protein_norm"]) * 100) - 100
                statuses.append(f"бел ✅+{p}%")
            else:
                p = int((prot / settings["protein_norm"]) * 100)
                statuses.append(f"бел 😞{p}%")
            lines.append(f"  {' | '.join(statuses)}")

        lines.append("")

    # Итог
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"<b>📊 ИТОГО ЗА НЕДЕЛЮ</b>")

    if settings:
        lines.append(f"  🔥 {format_number(total_cal)}/{format_number(settings['daily_calories'])} ккал")
        lines.append(f"  🥩 {format_number(total_prot)}/{format_number(settings['protein_norm'])}г")
        lines.append(f"  🥑 {format_number(total_fat)}/{format_number(settings['fat_norm'])}г")
        lines.append(f"  🍞 {format_number(total_carb)}/{format_number(settings['carbs_norm'])}г")
        lines.append("")

        # Общий статус по калориям
        cal_ok = total_cal >= settings["daily_calories"]
        prot_ok = total_prot >= settings["protein_norm"]
        if cal_ok and prot_ok:
            p = int((total_cal / settings["daily_calories"]) * 100) - 100
            lines.append(f"✅ <b>Добор: +{p}%</b> ✅")
        else:
            p = int((total_cal / settings["daily_calories"]) * 100)
            lines.append(f"😞 <b>Недобор: {p}%</b> 😞")
    else:
        lines.append(f"  🔥 {format_number(total_cal)} ккал")
        lines.append(f"  🥩 {format_number(total_prot)}г | 🥑 {format_number(total_fat)}г | 🍞 {format_number(total_carb)}г")

    text = "\n".join(lines)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главная", callback_data="back_main")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# ================== СТАТИСТИКА ЗА МЕСЯЦ ==================

@dp.callback_query(F.data == "stats_month")
async def show_month_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    year, month = get_month_range()
    stats = get_month_stats(user_id, year, month)
    settings = get_user_settings(user_id)

    if not stats:
        text = f"За {calendar.month_name[month]} {year} ещё нет записей"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главная", callback_data="back_main")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        return

    total_cal = 0
    total_prot = 0
    total_fat = 0
    total_carb = 0

    for row in stats:
        total_cal += float(row["total_calories"])
        total_prot += float(row["total_protein"])
        total_fat += float(row["total_fat"])
        total_carb += float(row["total_carbs"])

    lines = []
    lines.append(f"<b>📊 ИТОГО ЗА {calendar.month_name[month].upper()} {year}</b>")
    lines.append("")

    if settings:
        lines.append(f"  🔥 {format_number(total_cal)}/{format_number(settings['daily_calories'])} ккал")
        lines.append(f"  🥩 {format_number(total_prot)}/{format_number(settings['protein_norm'])}г")
        lines.append(f"  🥑 {format_number(total_fat)}/{format_number(settings['fat_norm'])}г")
        lines.append(f"  🍞 {format_number(total_carb)}/{format_number(settings['carbs_norm'])}г")
        lines.append("")

        cal_ok = total_cal >= settings["daily_calories"]
        prot_ok = total_prot >= settings["protein_norm"]
        if cal_ok and prot_ok:
            p = int((total_cal / settings["daily_calories"]) * 100) - 100
            lines.append(f"✅ <b>Добор: +{p}%</b> ✅")
        else:
            p = int((total_cal / settings["daily_calories"]) * 100)
            lines.append(f"😞 <b>Недобор: {p}%</b> 😞")
    else:
        lines.append(f"  🔥 {format_number(total_cal)} ккал")
        lines.append(f"  🥩 {format_number(total_prot)}г | 🥑 {format_number(total_fat)}г | 🍞 {format_number(total_carb)}г")

    text = "\n".join(lines)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главная", callback_data="back_main")]
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
    user_id = callback.from_user.id
    settings = get_user_settings(user_id)
    await callback.message.edit_text(
        "🤫 Запиши, сколько КБЖУ ты скушал сегодня",
        reply_markup=get_main_keyboard(has_settings=settings is not None)
    )


@dp.callback_query(F.data.startswith("calendar_month:"))
async def back_to_calendar_month(callback: CallbackQuery):
    _, year, month = callback.data.split(":")
    year, month = int(year), int(month)
    keyboard = get_calendar_keyboard(year, month)
    await callback.message.edit_text("<b>📆 Выбери дату</b>", reply_markup=keyboard, parse_mode="HTML")


# ================== ЗАПУСК ==================

async def main():
    init_db()
    logging.info("База данных инициализирована")

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот запущен...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

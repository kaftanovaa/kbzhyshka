import asyncio
import logging
import re
import calendar
from datetime import date, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import BOT_TOKEN
from database import (
    init_db, add_user, user_exists, user_has_settings, save_user_settings, get_user_settings,
    add_food_entry, remove_food_entry,
    get_daily_totals, get_food_entries_for_date,
    get_week_stats, get_month_stats
)
from keyboards import (
    get_main_keyboard, get_today_keyboard, get_day_keyboard,
    get_calendar_keyboard,
    get_add_type_keyboard, get_remove_type_keyboard,
    get_gender_keyboard, get_activity_keyboard,
    get_goal_keyboard, get_deficit_keyboard,
    get_cancel_keyboard
)

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


class FoodAdd(StatesGroup):
    waiting_serving = State()
    waiting_100g = State()


class FoodRemove(StatesGroup):
    waiting_serving = State()
    waiting_100g = State()


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ================== УТИЛИТЫ ==================

def format_number(num: float) -> str:
    if num == int(num):
        return str(int(num))
    return f"{num:.1f}".rstrip('0').rstrip('.')


def parse_number(text: str) -> float:
    text = text.strip().replace(',', '.')
    try:
        return float(text)
    except ValueError:
        return None


def parse_serving_input(text: str) -> tuple:
    """Калории/Белки/Жиры/Углеводы"""
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
    """Калории/Белки/Жиры/Углеводы Вес"""
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
    year, month, day = map(int, date_str.split('-'))
    d = date(year, month, day)
    return ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][d.weekday()]


def get_week_range(target_date: date = None) -> tuple:
    if target_date is None:
        target_date = date.today()
    monday = target_date - timedelta(days=target_date.weekday())
    sunday = monday + timedelta(days=6)
    return (monday.isoformat(), sunday.isoformat())


def get_month_range(target_date: date = None) -> tuple:
    if target_date is None:
        target_date = date.today()
    return (target_date.year, target_date.month)


def calculate_norms(gender, weight, height, age, activity_coeff, activity_label, goal, deficit_label=None):
    if gender == "female":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5

    daily_calories = bmr * activity_coeff

    if goal == "loss":
        if deficit_label == "small":
            daily_calories *= 0.90
        elif deficit_label == "medium":
            daily_calories *= 0.85
        else:
            daily_calories *= 0.80
    elif goal == "gain":
        daily_calories *= 1.20

    daily_calories = round(daily_calories, 1)
    protein_norm = round(2 * weight, 1)
    fat_norm = round(1 * weight, 1)
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


def get_day_status(current: float, norm: float) -> str:
    if norm == 0:
        return ""
    return str(int((current / norm) * 100))


# ================== ТЕКСТОВЫЕ ОБРАБОТЧИКИ (ReplyKeyboard) ==================

MAIN_BUTTONS = {"📅 Сегодня", "📆 Открыть календарь", "📊 Статистика за неделю",
                "📈 Статистика за месяц", "🔄 Пересчитать норму"}
TODAY_BUTTONS = {"➕ Добавить", "➖ Удалить", "◀ Вчера", "▶ Завтра", "📆 К календарю", "🏠 Главная"}
DAY_BUTTONS = {"➕ Добавить", "➖ Удалить", "◀ Пред. день", "▶ След. день", "📆 К календарю", "🏠 Главная"}
CANCEL_BTN = "❌ Отмена"


async def show_day_view(message: Message, target_date: date, state: FSMContext, is_today_view: bool = False):
    """Показать данные за день с ReplyKeyboard."""
    user_id = message.from_user.id
    cal, prot, fat, carb = get_daily_totals(user_id, target_date.isoformat())
    settings = get_user_settings(user_id)

    if target_date == date.today():
        date_title = "сегодня"
    else:
        date_title = target_date.strftime("%d.%m.%Y")

    if not settings:
        lines = [
            f"<b>📊 Данные за {date_title}</b>", "",
            f"🔥 Калории: <b>{format_number(cal)}</b> ккал",
            f"🥩 Белки: <b>{format_number(prot)}</b>г",
            f"🥑 Жиры: <b>{format_number(fat)}</b>г",
            f"🍞 Углеводы: <b>{format_number(carb)}</b>г"
        ]
    else:
        lines = [
            f"<b>📊 Данные за {date_title}</b>", "",
            f"🔥 Калории: {format_number(cal)}/{format_number(settings['daily_calories'])} ккал",
            f"🥩 Белки: {format_number(prot)}/{format_number(settings['protein_norm'])}г",
            f"🥑 Жиры: {format_number(fat)}/{format_number(settings['fat_norm'])}г",
            f"🍞 Углеводы: {format_number(carb)}/{format_number(settings['carbs_norm'])}г"
        ]

    text = "\n".join(lines)
    kb = get_today_keyboard() if is_today_view else get_day_keyboard()

    # Сохраняем текущую дату в state для навигации
    await state.update_data(view_date=target_date.isoformat(), is_today_view=is_today_view)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


async def handle_main_button(message: Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text

    if text == "📅 Сегодня":
        await show_day_view(message, date.today(), state, is_today_view=True)

    elif text == "🏠 Главная":
        await state.clear()
        settings = get_user_settings(user_id)
        await message.answer("🤫 Запиши, сколько КБЖУ ты скушал сегодня",
                             reply_markup=get_main_keyboard(has_settings=settings is not None))

    elif text == "📆 К календарю":
        await state.clear()
        today = date.today()
        kb = get_calendar_keyboard(today.year, today.month)
        await message.answer("<b>📆 Выбери дату</b>", reply_markup=kb, parse_mode="HTML")

    elif text == "➕ Добавить":
        await message.answer("Выбери тип ввода:", reply_markup=get_add_type_keyboard())
        await FoodAdd.waiting_serving.set()  # временное состояние, переключится при выборе

    elif text == "➖ Удалить":
        await message.answer("Выбери тип удаления:", reply_markup=get_remove_type_keyboard())
        await FoodRemove.waiting_serving.set()

    elif text == "◀ Вчера" or text == "◀ Пред. день":
        data = await state.get_data()
        current = date.fromisoformat(data.get("view_date", date.today().isoformat()))
        prev = current - timedelta(days=1)
        is_today = (prev == date.today())
        await show_day_view(message, prev, state, is_today_view=is_today)

    elif text == "▶ Завтра" or text == "▶ След. день":
        data = await state.get_data()
        current = date.fromisoformat(data.get("view_date", date.today().isoformat()))
        nxt = current + timedelta(days=1)
        is_today = (nxt == date.today())
        await show_day_view(message, nxt, state, is_today_view=is_today)

    elif text == "📊 Статистика за неделю":
        await show_week_stats_text(message, user_id)

    elif text == "📈 Статистика за месяц":
        await show_month_stats_text(message, user_id)

    elif text == "🔄 Пересчитать норму":
        await state.set_state(Onboarding.waiting_gender)
        await message.answer("Давай пересчитаем норму! Укажи свой пол:",
                             reply_markup=get_gender_keyboard())


async def show_week_stats_text(message: Message, user_id: int):
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
    total_cal = total_prot = total_fat = total_carb = 0.0

    for date_str in sorted(all_days.keys()):
        data = all_days[date_str]
        day_name = get_day_name(date_str)
        d = date.fromisoformat(date_str)
        cal = data["calories"]
        prot = data["protein"]
        fat = data["fat"]
        carb = data["carbs"]
        total_cal += cal
        total_prot += prot
        total_fat += fat
        total_carb += carb

        lines.append(f"<b>{d.strftime('%d.%m.%Y')} ({day_name})</b>")
        lines.append(f"  🔥 {format_number(cal)} ккал | 🥩 {format_number(prot)}г | 🥑 {format_number(fat)}г | 🍞 {format_number(carb)}г")

        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"<b>📊 ИТОГО ЗА НЕДЕЛЮ</b>")

    if settings:
        week_days = (end - start).days + 1
        norm_cal = settings["daily_calories"] * week_days
        norm_prot = settings["protein_norm"] * week_days
        norm_fat = settings["fat_norm"] * week_days
        norm_carb = settings["carbs_norm"] * week_days

        lines.append(f"  🔥 Набрано {format_number(total_cal)} из {format_number(norm_cal)} ккал")
        lines.append(f"  🥩 Набрано {format_number(total_prot)} из {format_number(norm_prot)}г белка")
        lines.append(f"  🥑 Набрано {format_number(total_fat)} из {format_number(norm_fat)}г жира")
        lines.append(f"  🍞 Набрано {format_number(total_carb)} из {format_number(norm_carb)}г углеводов")
    else:
        lines.append(f"  🔥 {format_number(total_cal)} ккал")
        lines.append(f"  🥩 {format_number(total_prot)}г | 🥑 {format_number(total_fat)}г | 🍞 {format_number(total_carb)}г")

    await message.answer("\n".join(lines), reply_markup=get_main_keyboard(has_settings=settings is not None), parse_mode="HTML")


async def show_month_stats_text(message: Message, user_id: int):
    year, month = get_month_range()
    stats = get_month_stats(user_id, year, month)
    settings = get_user_settings(user_id)

    if not stats:
        await message.answer(f"За {calendar.month_name[month]} {year} ещё нет записей",
                             reply_markup=get_main_keyboard(has_settings=settings is not None))
        return

    total_cal = total_prot = total_fat = total_carb = 0.0
    for row in stats:
        total_cal += float(row["total_calories"])
        total_prot += float(row["total_protein"])
        total_fat += float(row["total_fat"])
        total_carb += float(row["total_carbs"])

    lines = [f"<b>📊 ИТОГО ЗА {calendar.month_name[month].upper()} {year}</b>", ""]

    if settings:
        days_in_month = calendar.monthrange(year, month)[1]
        norm_cal = settings["daily_calories"] * days_in_month
        norm_prot = settings["protein_norm"] * days_in_month
        norm_fat = settings["fat_norm"] * days_in_month
        norm_carb = settings["carbs_norm"] * days_in_month

        lines.append(f"  🔥 Набрано {format_number(total_cal)} из {format_number(norm_cal)} ккал")
        lines.append(f"  🥩 Набрано {format_number(total_prot)} из {format_number(norm_prot)}г белка")
        lines.append(f"  🥑 Набрано {format_number(total_fat)} из {format_number(norm_fat)}г жира")
        lines.append(f"  🍞 Набрано {format_number(total_carb)} из {format_number(norm_carb)}г углеводов")
    else:
        lines.append(f"  🔥 {format_number(total_cal)} ккал")
        lines.append(f"  🥩 {format_number(total_prot)}г | 🥑 {format_number(total_fat)}г | 🍞 {format_number(total_carb)}г")

    await message.answer("\n".join(lines), reply_markup=get_main_keyboard(has_settings=settings is not None), parse_mode="HTML")


# ================== /START ==================

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    if not user_exists(user_id):
        add_user(user_id, username)

    settings = get_user_settings(user_id)
    if settings:
        await state.clear()
        await message.answer("🤫 Запиши, сколько КБЖУ ты скушал сегодня",
                             reply_markup=get_main_keyboard(has_settings=True))
    else:
        await state.set_state(Onboarding.waiting_gender)
        await message.answer(
            "Привет! Я бот для подсчёта КБЖУ (калории, белки, жиры, углеводы).\n\n"
            "Давай рассчитаю твою персональную норму! 🎯\n\n"
            "Укажи свой пол:",
            reply_markup=get_gender_keyboard()
        )


# ================== ТЕКСТОВЫЕ СООБЩЕНИЯ — МАРШРУТИЗАЦИЯ ==================

@dp.message(F.text)
async def handle_text_message(message: Message, state: FSMContext):
    """Обрабатываем все текстовые сообщения: кнопки и ввод данных."""
    text = message.text.strip()

    # Отмена
    if text == CANCEL_BTN:
        await state.clear()
        user_id = message.from_user.id
        settings = get_user_settings(user_id)
        await message.answer("Отменено.", reply_markup=get_main_keyboard(has_settings=settings is not None))
        return

    # Текущее состояние FSM
    current_state = await state.get_state()

    # --- Онбординг ---
    if current_state == Onboarding.waiting_gender.state:
        if text == "👨 Мужчина":
            await state.update_data(gender="male")
            await message.answer("Теперь укажи свой вес (кг):", reply_markup=get_cancel_keyboard())
            await state.set_state(Onboarding.waiting_weight)
        elif text == "👩 Женщина":
            await state.update_data(gender="female")
            await message.answer("Теперь укажи свой вес (кг):", reply_markup=get_cancel_keyboard())
            await state.set_state(Onboarding.waiting_weight)
        return

    if current_state == Onboarding.waiting_weight.state:
        weight = parse_number(text)
        if weight is None or weight <= 0:
            await message.answer("❌ Введи корректный вес (число, кг):")
            return
        await state.update_data(weight=weight)
        await message.answer("Теперь укажи свой рост (см):")
        await state.set_state(Onboarding.waiting_height)
        return

    if current_state == Onboarding.waiting_height.state:
        height = parse_number(text)
        if height is None or height <= 0:
            await message.answer("❌ Введи корректный рост (число, см):")
            return
        await state.update_data(height=height)
        await message.answer("Теперь укажи свой возраст (полных лет):")
        await state.set_state(Onboarding.waiting_age)
        return

    if current_state == Onboarding.waiting_age.state:
        age_val = parse_number(text)
        if age_val is None or age_val <= 0 or age_val != int(age_val):
            await message.answer("❌ Введи корректный возраст (целое число):")
            return
        await state.update_data(age=int(age_val))
        await message.answer("Какой у тебя уровень активности?", reply_markup=get_activity_keyboard())
        await state.set_state(Onboarding.waiting_activity)
        return

    if current_state == Onboarding.waiting_activity.state:
        activity_map = {
            "🪑 Сидячий (без нагрузок)": (1.2, "Сидячий образ жизни"),
            "🚶 Лёгкая (1-3 раза/нед)": (1.375, "Лёгкая активность"),
            "🏃 Умеренная (3-5 дней/нед)": (1.55, "Умеренная активность"),
            "🏋️ Высокая (6-7 дней/нед)": (1.725, "Высокая активность"),
            "⚡ Очень высокая": (1.9, "Очень высокая активность"),
        }
        if text in activity_map:
            coeff, label = activity_map[text]
            await state.update_data(activity_coefficient=coeff, activity_label=label)
            await message.answer("Какая у тебя цель?", reply_markup=get_goal_keyboard())
            await state.set_state(Onboarding.waiting_goal)
        else:
            await message.answer("Выбери активность из списка:", reply_markup=get_activity_keyboard())
        return

    if current_state == Onboarding.waiting_goal.state:
        goal_map = {
            "🔥 Похудение": "loss",
            "⚖️ Поддержание веса": "maintain",
            "💪 Набор веса": "gain",
        }
        if text in goal_map:
            goal = goal_map[text]
            if goal == "loss":
                await state.update_data(goal=goal)
                await message.answer("Какой дефицит калорий хочешь?", reply_markup=get_deficit_keyboard())
                await state.set_state(Onboarding.waiting_deficit)
            else:
                await state.update_data(goal=goal, deficit_label=None)
                await finish_onboarding(message, state)
        else:
            await message.answer("Выбери цель из списка:", reply_markup=get_goal_keyboard())
        return

    if current_state == Onboarding.waiting_deficit.state:
        deficit_map = {
            "🟢 Небольшой (-10%)": "small",
            "🟡 Средний (-15%)": "medium",
            "🔴 Большой (-20%)": "large",
        }
        if text in deficit_map:
            await state.update_data(deficit_label=deficit_map[text])
            await finish_onboarding(message, state)
        else:
            await message.answer("Выбери дефицит из списка:", reply_markup=get_deficit_keyboard())
        return

    # --- Добавление еды ---
    if current_state == FoodAdd.waiting_serving.state:
        # Это был выбор "на порцию" через текст, но теперь мы обрабатываем ввод данных
        result = parse_serving_input(text)
        if result is None:
            await message.answer("❌ Некорректный ввод. Формат: <b>Калории/Белки/Жиры/Углеводы</b>\nПример: 200/30/15/45",
                                 parse_mode="HTML")
            return
        await process_add_serving(message, state, result)
        return

    if current_state == FoodAdd.waiting_100g.state:
        result = parse_100g_input(text)
        if result is None:
            await message.answer("❌ Некорректный ввод. Формат: <b>Калории/Белки/Жиры/Углеводы Вес</b>\nПример: 100/20/30/40 150",
                                 parse_mode="HTML")
            return
        await process_add_100g(message, state, result)
        return

    # --- Удаление еды ---
    if current_state == FoodRemove.waiting_serving.state:
        result = parse_serving_input(text)
        if result is None:
            await message.answer("❌ Некорректный ввод. Формат: <b>Калории/Белки/Жиры/Углеводы</b>\nПример: 200/30/15/45",
                                 parse_mode="HTML")
            return
        await process_remove_serving(message, state, result)
        return

    if current_state == FoodRemove.waiting_100g.state:
        result = parse_100g_input(text)
        if result is None:
            await message.answer("❌ Некорректный ввод. Формат: <b>Калории/Белки/Жиры/Углеводы Вес</b>\nПример: 100/20/30/40 150",
                                 parse_mode="HTML")
            return
        await process_remove_100g(message, state, result)
        return

    # --- Кнопки главного меню ---
    if text in MAIN_BUTTONS | TODAY_BUTTONS | DAY_BUTTONS:
        await handle_main_button(message, state)
        return

    # Не распознано
    await message.answer("Не распознано. Используй кнопки меню.")


async def finish_onboarding(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    norms = calculate_norms(
        data["gender"], data["weight"], data["height"], data["age"],
        data["activity_coefficient"], data["activity_label"],
        data["goal"], data.get("deficit_label")
    )
    save_user_settings(
        user_id=user_id, gender=data["gender"], weight=data["weight"],
        height=data["height"], age=data["age"],
        activity_coefficient=data["activity_coefficient"],
        activity_label=data["activity_label"], goal=data["goal"],
        deficit_label=data.get("deficit_label"),
        daily_calories=norms["daily_calories"],
        protein_norm=norms["protein_norm"], fat_norm=norms["fat_norm"],
        carbs_norm=norms["carbs_norm"]
    )
    goal_labels = {"loss": "Похудение", "maintain": "Поддержание", "gain": "Набор веса"}
    await message.answer(
        f"🎉 Готово! Твоя персональная норма:\n\n"
        f"🔥 Калории: <b>{format_number(norms['daily_calories'])}</b> ккал\n"
        f"🥩 Белки: <b>{format_number(norms['protein_norm'])}</b>г\n"
        f"🥑 Жиры: <b>{format_number(norms['fat_norm'])}</b>г\n"
        f"🍞 Углеводы: <b>{format_number(norms['carbs_norm'])}</b>г\n\n"
        f"Цель: {goal_labels.get(data['goal'], data['goal'])}",
        parse_mode="HTML"
    )
    await state.clear()
    await message.answer("🤫 Запиши, сколько КБЖУ ты скушал сегодня",
                         reply_markup=get_main_keyboard(has_settings=True))


# ================== ДОБАВЛЕНИЕ ЕДЫ ==================

async def process_add_serving(message: Message, state: FSMContext, result: tuple):
    cal, prot, fat, carb = result
    # Проверка на отрицательные значения
    if cal < 0 or prot < 0 or fat < 0 or carb < 0:
        await message.answer("❌ Значения не могут быть отрицательными!", parse_mode="HTML")
        return

    data = await state.get_data()
    target_date = data.get("target_date", date.today().isoformat())
    user_id = message.from_user.id

    add_food_entry(user_id, target_date, cal, prot, fat, carb)
    total_cal, total_prot, total_fat, total_carb = get_daily_totals(user_id, target_date)

    # Проверка: не ушли ли в минус
    if total_cal < 0 or total_prot < 0 or total_fat < 0 or total_carb < 0:
        # Откатываем: добавляем отрицательную запись
        add_food_entry(user_id, target_date, -cal, -prot, -fat, -carb)
        await message.answer("❌ Ошибка: значения не могут уйти в минус!")
        await state.clear()
        return

    d = date.fromisoformat(target_date)
    text = (
        f"<b>📊 Данные за {d.strftime('%d.%m.%Y')}</b>\n\n"
        f"🔥 Калории: <b>{format_number(total_cal)}</b> ккал\n"
        f"🥩 Белки: <b>{format_number(total_prot)}</b>г\n"
        f"🥑 Жиры: <b>{format_number(total_fat)}</b>г\n"
        f"🍞 Углеводы: <b>{format_number(total_carb)}</b>г\n\n"
        f"Добавлено: {format_number(cal)} ккал / {format_number(prot)}г / {format_number(fat)}г / {format_number(carb)}г"
    )
    is_today = (target_date == date.today().isoformat())
    kb = get_today_keyboard() if is_today else get_day_keyboard()
    await state.update_data(view_date=target_date, is_today_view=is_today)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.clear()


async def process_add_100g(message: Message, state: FSMContext, result: tuple):
    cal_per_100, prot_per_100, fat_per_100, carb_per_100, weight = result
    if cal_per_100 < 0 or prot_per_100 < 0 or fat_per_100 < 0 or carb_per_100 < 0 or weight <= 0:
        await message.answer("❌ Значения не могут быть отрицательными!", parse_mode="HTML")
        return

    cal = (cal_per_100 * weight) / 100
    prot = (prot_per_100 * weight) / 100
    fat = (fat_per_100 * weight) / 100
    carb = (carb_per_100 * weight) / 100

    data = await state.get_data()
    target_date = data.get("target_date", date.today().isoformat())
    user_id = message.from_user.id

    add_food_entry(user_id, target_date, cal, prot, fat, carb)
    total_cal, total_prot, total_fat, total_carb = get_daily_totals(user_id, target_date)

    if total_cal < 0 or total_prot < 0 or total_fat < 0 or total_carb < 0:
        add_food_entry(user_id, target_date, -cal, -prot, -fat, -carb)
        await message.answer("❌ Ошибка: значения не могут уйти в минус!")
        await state.clear()
        return

    d = date.fromisoformat(target_date)
    text = (
        f"<b>📊 Данные за {d.strftime('%d.%m.%Y')}</b>\n\n"
        f"🔥 Калории: <b>{format_number(total_cal)}</b> ккал\n"
        f"🥩 Белки: <b>{format_number(total_prot)}</b>г\n"
        f"🥑 Жиры: <b>{format_number(total_fat)}</b>г\n"
        f"🍞 Углеводы: <b>{format_number(total_carb)}</b>г\n\n"
        f"Добавлено: {format_number(cal)} ккал / {format_number(prot)}г / {format_number(fat)}г / {format_number(carb)}г\n"
        f"<i>(Для {format_number(weight)}г)</i>"
    )
    is_today = (target_date == date.today().isoformat())
    kb = get_today_keyboard() if is_today else get_day_keyboard()
    await state.update_data(view_date=target_date, is_today_view=is_today)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.clear()


# ================== УДАЛЕНИЕ ЕДЫ ==================

async def process_remove_serving(message: Message, state: FSMContext, result: tuple):
    cal, prot, fat, carb = result
    if cal < 0 or prot < 0 or fat < 0 or carb < 0:
        await message.answer("❌ Значения не могут быть отрицательными!", parse_mode="HTML")
        return

    data = await state.get_data()
    target_date = data.get("target_date", date.today().isoformat())
    user_id = message.from_user.id

    # Проверяем текущие итоги
    cur_cal, cur_prot, cur_fat, cur_carb = get_daily_totals(user_id, target_date)

    # Проверяем, не уйдут ли в минус
    if cur_cal - cal < 0 or cur_prot - prot < 0 or cur_fat - fat < 0 or cur_carb - carb < 0:
        await message.answer("❌ Ошибка: значения не могут уйти в минус! Проверь введённые данные.")
        await state.clear()
        return

    remove_food_entry(user_id, target_date, cal, prot, fat, carb)
    total_cal, total_prot, total_fat, total_carb = get_daily_totals(user_id, target_date)

    d = date.fromisoformat(target_date)
    text = (
        f"<b>📊 Данные за {d.strftime('%d.%m.%Y')}</b>\n\n"
        f"🔥 Калории: <b>{format_number(total_cal)}</b> ккал\n"
        f"🥩 Белки: <b>{format_number(total_prot)}</b>г\n"
        f"🥑 Жиры: <b>{format_number(total_fat)}</b>г\n"
        f"🍞 Углеводы: <b>{format_number(total_carb)}</b>г\n\n"
        f"Удалено: {format_number(cal)} ккал / {format_number(prot)}г / {format_number(fat)}г / {format_number(carb)}г"
    )
    is_today = (target_date == date.today().isoformat())
    kb = get_today_keyboard() if is_today else get_day_keyboard()
    await state.update_data(view_date=target_date, is_today_view=is_today)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.clear()


async def process_remove_100g(message: Message, state: FSMContext, result: tuple):
    cal_per_100, prot_per_100, fat_per_100, carb_per_100, weight = result
    if cal_per_100 < 0 or prot_per_100 < 0 or fat_per_100 < 0 or carb_per_100 < 0 or weight <= 0:
        await message.answer("❌ Значения не могут быть отрицательными!", parse_mode="HTML")
        return

    cal = (cal_per_100 * weight) / 100
    prot = (prot_per_100 * weight) / 100
    fat = (fat_per_100 * weight) / 100
    carb = (carb_per_100 * weight) / 100

    data = await state.get_data()
    target_date = data.get("target_date", date.today().isoformat())
    user_id = message.from_user.id

    cur_cal, cur_prot, cur_fat, cur_carb = get_daily_totals(user_id, target_date)
    if cur_cal - cal < 0 or cur_prot - prot < 0 or cur_fat - fat < 0 or cur_carb - carb < 0:
        await message.answer("❌ Ошибка: значения не могут уйти в минус!")
        await state.clear()
        return

    remove_food_entry(user_id, target_date, cal, prot, fat, carb)
    total_cal, total_prot, total_fat, total_carb = get_daily_totals(user_id, target_date)

    d = date.fromisoformat(target_date)
    text = (
        f"<b>📊 Данные за {d.strftime('%d.%m.%Y')}</b>\n\n"
        f"🔥 Калории: <b>{format_number(total_cal)}</b> ккал\n"
        f"🥩 Белки: <b>{format_number(total_prot)}</b>г\n"
        f"🥑 Жиры: <b>{format_number(total_fat)}</b>г\n"
        f"🍞 Углеводы: <b>{format_number(total_carb)}</b>г\n\n"
        f"Удалено: {format_number(cal)} ккал / {format_number(prot)}г / {format_number(fat)}г / {format_number(carb)}г\n"
        f"<i>(Для {format_number(weight)}г)</i>"
    )
    is_today = (target_date == date.today().isoformat())
    kb = get_today_keyboard() if is_today else get_day_keyboard()
    await state.update_data(view_date=target_date, is_today_view=is_today)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.clear()


# ================== КАЛЕНДАРЬ (Inline) ==================

@dp.callback_query(F.data == "calendar_main")
async def show_calendar_main(callback: CallbackQuery):
    today = date.today()
    await callback.message.edit_text("<b>📆 Выбери дату</b>",
                                      reply_markup=get_calendar_keyboard(today.year, today.month),
                                      parse_mode="HTML")


@dp.callback_query(F.data.startswith("cal_prev:"))
async def calendar_prev_month(callback: CallbackQuery):
    _, year, month = callback.data.split(":")
    year, month = int(year), int(month)
    if month == 1:
        year -= 1
        month = 12
    else:
        month -= 1
    await callback.message.edit_text("<b>📆 Выбери дату</b>",
                                      reply_markup=get_calendar_keyboard(year, month),
                                      parse_mode="HTML")


@dp.callback_query(F.data.startswith("cal_next:"))
async def calendar_next_month(callback: CallbackQuery):
    _, year, month = callback.data.split(":")
    year, month = int(year), int(month)
    if month == 12:
        year += 1
        month = 1
    else:
        month += 1
    await callback.message.edit_text("<b>📆 Выбери дату</b>",
                                      reply_markup=get_calendar_keyboard(year, month),
                                      parse_mode="HTML")


@dp.callback_query(F.data.startswith("cal_day:"))
async def calendar_select_day(callback: CallbackQuery):
    _, year, month, day = callback.data.split(":")
    year, month, day = int(year), int(month), int(day)
    target_date = date(year, month, day)

    user_id = callback.from_user.id
    cal, prot, fat, carb = get_daily_totals(user_id, target_date.isoformat())
    settings = get_user_settings(user_id)

    date_title = "сегодня" if target_date == date.today() else target_date.strftime("%d.%m.%Y")

    if not settings:
        lines = [f"<b>📊 Данные за {date_title}</b>", "",
                 f"🔥 Калории: <b>{format_number(cal)}</b> ккал",
                 f"🥩 Белки: <b>{format_number(prot)}</b>г",
                 f"🥑 Жиры: <b>{format_number(fat)}</b>г",
                 f"🍞 Углеводы: <b>{format_number(carb)}</b>г"]
    else:
        lines = [f"<b>📊 Данные за {date_title}</b>", "",
                 f"🔥 Калории: {format_number(cal)}/{format_number(settings['daily_calories'])} ккал",
                 f"🥩 Белки: {format_number(prot)}/{format_number(settings['protein_norm'])}г",
                 f"🥑 Жиры: {format_number(fat)}/{format_number(settings['fat_norm'])}г",
                 f"🍞 Углеводы: {format_number(carb)}/{format_number(settings['carbs_norm'])}г"]

    await callback.message.answer("\n".join(lines), reply_markup=get_day_keyboard(), parse_mode="HTML")


# ================== ЗАПУСК ==================

async def main():
    init_db()
    logging.info("База данных инициализирована")
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

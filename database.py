import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date
from typing import Optional

# Подключение к PostgreSQL (Railway предоставляет DATABASE_URL)
DATABASE_URL = os.environ.get("DATABASE_URL")

# Проверка наличия DATABASE_URL
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не найден! Добавь переменную окружения на Railway")


def get_connection():
    """Получить соединение с базой данных."""
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_db():
    """Инициализировать базу данных."""
    conn = get_connection()
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица настроек пользователя (персонализированные нормы)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            gender TEXT,
            weight REAL,
            height REAL,
            age INTEGER,
            activity_coefficient REAL,
            activity_label TEXT,
            goal TEXT,
            deficit_label TEXT,
            daily_calories REAL,
            protein_norm REAL,
            fat_norm REAL,
            carbs_norm REAL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Таблица отдельных записей еды (КБЖУ)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS food_entries (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            entry_date DATE,
            calories REAL,
            protein REAL,
            fat REAL,
            carbs REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def add_user(user_id: int, username: Optional[str] = None):
    """Добавить пользователя в базу."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (user_id, username) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING",
        (user_id, username)
    )
    conn.commit()
    conn.close()


def user_exists(user_id: int) -> bool:
    """Проверить, существует ли пользователь."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def user_has_settings(user_id: int) -> bool:
    """Проверить, есть ли у пользователя настройки."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM user_settings WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def save_user_settings(user_id: int, gender: str, weight: float, height: float, age: int,
                       activity_coefficient: float, activity_label: str, goal: str,
                       deficit_label: Optional[str], daily_calories: float,
                       protein_norm: float, fat_norm: float, carbs_norm: float):
    """Сохранить персонализированные нормы пользователя."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_settings (user_id, gender, weight, height, age, activity_coefficient,
                                   activity_label, goal, deficit_label, daily_calories,
                                   protein_norm, fat_norm, carbs_norm)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            gender = %s, weight = %s, height = %s, age = %s,
            activity_coefficient = %s, activity_label = %s, goal = %s,
            deficit_label = %s, daily_calories = %s,
            protein_norm = %s, fat_norm = %s, carbs_norm = %s
    """, (
        user_id, gender, weight, height, age, activity_coefficient,
        activity_label, goal, deficit_label, daily_calories,
        protein_norm, fat_norm, carbs_norm,
        # Для ON CONFLICT DO UPDATE
        gender, weight, height, age,
        activity_coefficient, activity_label, goal,
        deficit_label, daily_calories,
        protein_norm, fat_norm, carbs_norm
    ))
    conn.commit()
    conn.close()


def get_user_settings(user_id: int) -> Optional[dict]:
    """Получить настройки пользователя."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM user_settings WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return dict(result)
    return None


def add_food_entry(user_id: int, entry_date: str, calories: float, protein: float, fat: float, carbs: float):
    """Добавить запись о еде."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO food_entries (user_id, entry_date, calories, protein, fat, carbs) VALUES (%s, %s, %s, %s, %s, %s)",
        (user_id, entry_date, calories, protein, fat, carbs)
    )
    conn.commit()
    conn.close()


def remove_food_entry(user_id: int, entry_date: str, calories: float, protein: float, fat: float, carbs: float):
    """Вычесть значения из суммы за день (добавить отрицательную запись)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO food_entries (user_id, entry_date, calories, protein, fat, carbs)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (user_id, entry_date, -calories, -protein, -fat, -carbs)
    )
    conn.commit()
    conn.close()
    return True


def get_daily_totals(user_id: int, record_date: str) -> tuple:
    """Получить суммарные КБЖУ за день."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """SELECT COALESCE(SUM(calories), 0) as total_calories,
                  COALESCE(SUM(protein), 0) as total_protein,
                  COALESCE(SUM(fat), 0) as total_fat,
                  COALESCE(SUM(carbs), 0) as total_carbs
           FROM food_entries
           WHERE user_id = %s AND entry_date = %s""",
        (user_id, record_date)
    )
    result = cursor.fetchone()
    conn.close()
    return (
        float(result["total_calories"]),
        float(result["total_protein"]),
        float(result["total_fat"]),
        float(result["total_carbs"])
    )


def get_food_entries_for_date(user_id: int, record_date: str) -> list:
    """Получить все записи о еде за дату."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """SELECT id, calories, protein, fat, carbs, created_at
           FROM food_entries
           WHERE user_id = %s AND entry_date = %s
           ORDER BY created_at DESC""",
        (user_id, record_date)
    )
    results = cursor.fetchall()
    conn.close()
    return [dict(row) for row in results]


def delete_food_entry_by_id(user_id: int, entry_id: int) -> bool:
    """Удалить запись по ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM food_entries WHERE id = %s AND user_id = %s",
        (entry_id, user_id)
    )
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def get_dates_with_entries(user_id: int, year: int, month: int) -> list:
    """Получить список дат в месяце, где есть записи."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1

    cursor.execute(
        """SELECT DISTINCT entry_date
           FROM food_entries
           WHERE user_id = %s
           AND entry_date >= %s
           AND entry_date < %s
           ORDER BY entry_date""",
        (user_id, f"{year}-{month:02d}-01", f"{next_year}-{next_month:02d}-01")
    )
    results = cursor.fetchall()
    conn.close()
    return [row["entry_date"] for row in results]


def get_week_stats(user_id: int, start_date: str, end_date: str) -> list:
    """Получить статистику за период (неделю)."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """SELECT entry_date,
                  COALESCE(SUM(calories), 0) as total_calories,
                  COALESCE(SUM(protein), 0) as total_protein,
                  COALESCE(SUM(fat), 0) as total_fat,
                  COALESCE(SUM(carbs), 0) as total_carbs
           FROM food_entries
           WHERE user_id = %s AND entry_date >= %s AND entry_date <= %s
           GROUP BY entry_date
           ORDER BY entry_date""",
        (user_id, start_date, end_date)
    )
    results = cursor.fetchall()
    conn.close()
    return [dict(row) for row in results]


def get_month_stats(user_id: int, year: int, month: int) -> list:
    """Получить статистику за месяц."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1

    cursor.execute(
        """SELECT entry_date,
                  COALESCE(SUM(calories), 0) as total_calories,
                  COALESCE(SUM(protein), 0) as total_protein,
                  COALESCE(SUM(fat), 0) as total_fat,
                  COALESCE(SUM(carbs), 0) as total_carbs
           FROM food_entries
           WHERE user_id = %s AND entry_date >= %s AND entry_date < %s
           GROUP BY entry_date
           ORDER BY entry_date""",
        (user_id, f"{year}-{month:02d}-01", f"{next_year}-{next_month:02d}-01")
    )
    results = cursor.fetchall()
    conn.close()
    return [dict(row) for row in results]

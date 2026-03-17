import sqlite3
from datetime import date
from typing import Optional

DATABASE = "bj.db"


def get_connection():
    """Получить соединение с базой данных."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


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
    
    # Таблица записей БЖ за каждый день
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            record_date DATE,
            protein REAL DEFAULT 0,
            fat REAL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            UNIQUE(user_id, record_date)
        )
    """)
    
    # Таблица отдельных записей "ням-ням" (для удаления/редактирования)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS food_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            entry_date DATE,
            protein REAL,
            fat REAL,
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
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username)
    )
    conn.commit()
    conn.close()


def user_exists(user_id: int) -> bool:
    """Проверить, существует ли пользователь."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def add_food_entry(user_id: int, entry_date: str, protein: float, fat: float):
    """Добавить запись о еде."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO food_entries (user_id, entry_date, protein, fat) VALUES (?, ?, ?, ?)",
        (user_id, entry_date, protein, fat)
    )
    conn.commit()
    conn.close()


def remove_food_entry(user_id: int, entry_date: str, protein: float, fat: float):
    """Удалить запись о еде (одну конкретную запись с такими значениями)."""
    conn = get_connection()
    cursor = conn.cursor()
    # Удаляем одну запись с такими параметрами
    cursor.execute(
        """DELETE FROM food_entries 
           WHERE user_id = ? AND entry_date = ? AND protein = ? AND fat = ?
           LIMIT 1""",
        (user_id, entry_date, protein, fat)
    )
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def get_daily_totals(user_id: int, record_date: str) -> tuple:
    """Получить суммарные БЖ за день."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT COALESCE(SUM(protein), 0) as total_protein, 
                  COALESCE(SUM(fat), 0) as total_fat 
           FROM food_entries 
           WHERE user_id = ? AND entry_date = ?""",
        (user_id, record_date)
    )
    result = cursor.fetchone()
    conn.close()
    return (float(result["total_protein"]), float(result["total_fat"]))


def get_food_entries_for_date(user_id: int, record_date: str) -> list:
    """Получить все записи о еде за дату."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT id, protein, fat, created_at 
           FROM food_entries 
           WHERE user_id = ? AND entry_date = ?
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
        "DELETE FROM food_entries WHERE id = ? AND user_id = ?",
        (entry_id, user_id)
    )
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def get_dates_with_entries(user_id: int, year: int, month: int) -> list:
    """Получить список дат в месяце, где есть записи."""
    conn = get_connection()
    cursor = conn.cursor()

    # Первый и последний день месяца
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1

    cursor.execute(
        """SELECT DISTINCT entry_date
           FROM food_entries
           WHERE user_id = ?
           AND entry_date >= ?
           AND entry_date < ?
           ORDER BY entry_date""",
        (user_id, f"{year}-{month:02d}-01", f"{next_year}-{next_month:02d}-01")
    )
    results = cursor.fetchall()
    conn.close()
    return [row["entry_date"] for row in results]


def get_week_stats(user_id: int, start_date: str, end_date: str) -> list:
    """Получить статистику за период (неделю)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT entry_date, 
                  COALESCE(SUM(protein), 0) as total_protein,
                  COALESCE(SUM(fat), 0) as total_fat
           FROM food_entries
           WHERE user_id = ? AND entry_date >= ? AND entry_date <= ?
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
    cursor = conn.cursor()
    
    # Первый и последний день месяца
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1
    
    cursor.execute(
        """SELECT entry_date,
                  COALESCE(SUM(protein), 0) as total_protein,
                  COALESCE(SUM(fat), 0) as total_fat
           FROM food_entries
           WHERE user_id = ? AND entry_date >= ? AND entry_date < ?
           GROUP BY entry_date
           ORDER BY entry_date""",
        (user_id, f"{year}-{month:02d}-01", f"{next_year}-{next_month:02d}-01")
    )
    results = cursor.fetchall()
    conn.close()
    return [dict(row) for row in results]

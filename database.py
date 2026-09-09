import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional

DB_NAME = "baby_bot.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            child_birthday TEXT,
            morning_brief_time TEXT,
            timezone TEXT
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_type TEXT,
            timestamp INTEGER,
            note TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            age_min INTEGER,
            age_max INTEGER,
            category TEXT,
            text TEXT
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keywords TEXT,
            answer TEXT
        )
    ''')
    
    # Заполняем тестовыми данными, если таблицы пустые
    cur.execute("SELECT COUNT(*) FROM ideas")
    if cur.fetchone()[0] == 0:
        sample_ideas = [
            (0, 90, "моторика", "Игра с погремушкой: водите ей перед глазами."),
            (0, 90, "сенсорика", "Поглаживание разными тканями."),
            (90, 180, "моторика", "Игрушки на резинке над кроваткой."),
            (90, 180, "речь", "Пойте песенки с паузами."),
            (180, 365, "моторика", "Игры с крупными кубиками."),
            (180, 365, "речь", "Читайте книжки с картинками."),
        ]
        cur.executemany("INSERT INTO ideas (age_min, age_max, category, text) VALUES (?,?,?,?)", sample_ideas)
    
    cur.execute("SELECT COUNT(*) FROM knowledge")
    if cur.fetchone()[0] == 0:
        sample_knowledge = [
            ("прикорм,яблоко", "Яблоко можно вводить с 6 месяцев, начиная с 1/2 чайной ложки."),
            ("прикорм,кабачок", "Кабачок подходит для первого прикорма с 5-6 месяцев."),
            ("сон,норма", "В 6 месяцев ребёнок спит в среднем 14-15 часов в сутки."),
        ]
        cur.executemany("INSERT INTO knowledge (keywords, answer) VALUES (?,?)", sample_knowledge)
    
    conn.commit()
    conn.close()

def get_user(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {"user_id": row[0], "child_birthday": row[1], "morning_brief_time": row[2], "timezone": row[3]}
    return None

def create_user(user_id: int, child_birthday: str, morning_brief_time: str = "08:00", timezone: str = "Europe/Moscow"):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO users (user_id, child_birthday, morning_brief_time, timezone) VALUES (?,?,?,?)",
                (user_id, child_birthday, morning_brief_time, timezone))
    conn.commit()
    conn.close()

def update_user_brief_time(user_id: int, brief_time: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET morning_brief_time = ? WHERE user_id = ?", (brief_time, user_id))
    conn.commit()
    conn.close()

def add_event(user_id: int, event_type: str, timestamp: int, note: str = ""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO events (user_id, event_type, timestamp, note) VALUES (?,?,?,?)",
                (user_id, event_type, timestamp, note))
    conn.commit()
    conn.close()

def get_last_event(user_id: int, event_type: str = None):
    conn = get_connection()
    cur = conn.cursor()
    if event_type:
        cur.execute("SELECT * FROM events WHERE user_id = ? AND event_type = ? ORDER BY timestamp DESC LIMIT 1",
                    (user_id, event_type))
    else:
        cur.execute("SELECT * FROM events WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "user_id": row[1], "event_type": row[2], "timestamp": row[3], "note": row[4]}
    return None

def get_events_since(user_id: int, since_timestamp: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE user_id = ? AND timestamp >= ? ORDER BY timestamp ASC",
                (user_id, since_timestamp))
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "user_id": r[1], "event_type": r[2], "timestamp": r[3], "note": r[4]} for r in rows]

def get_events_between(user_id: int, start_ts: int, end_ts: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE user_id = ? AND timestamp BETWEEN ? AND ? ORDER BY timestamp ASC",
                (user_id, start_ts, end_ts))
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "user_id": r[1], "event_type": r[2], "timestamp": r[3], "note": r[4]} for r in rows]

def get_day_events(user_id: int, date_obj: date):
    start = int(datetime.combine(date_obj, datetime.min.time()).timestamp())
    end = int(datetime.combine(date_obj, datetime.max.time()).timestamp())
    return get_events_between(user_id, start, end)

def get_idea_by_age(age_days: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT text FROM ideas WHERE age_min <= ? AND age_max >= ? ORDER BY RANDOM() LIMIT 1",
                (age_days, age_days))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "Проведите время с ребёнком на свежем воздухе."

def get_idea_by_age(age_days: int):
    """Возвращает одну случайную идею (оставлено для совместимости)"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT text FROM ideas WHERE age_min <= ? AND age_max >= ? ORDER BY RANDOM() LIMIT 1",
                (age_days, age_days))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "Проведите время с ребёнком на свежем воздухе."

def get_ideas_by_age(age_days: int, limit: int = 5):
    """Возвращает список из limit случайных идей для данного возраста"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT text FROM ideas WHERE age_min <= ? AND age_max >= ? ORDER BY RANDOM() LIMIT ?",
                (age_days, age_days, limit))
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]

def answer_question(question: str):
    conn = get_connection()
    cur = conn.cursor()
    words = question.lower().split()
    best_match = None
    cur.execute("SELECT keywords, answer FROM knowledge")
    for kw, ans in cur.fetchall():
        kw_list = kw.split(',')
        if any(w in ' '.join(words) for w in kw_list):
            best_match = ans
            break
    conn.close()
    return best_match or "Не нашёл ответа на ваш вопрос. Попробуйте переформулировать."
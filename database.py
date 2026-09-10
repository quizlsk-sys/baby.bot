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
    
    # === Заполняем идеями (безопасно: добавляет только те, которых ещё нет) ===
    cur.execute("SELECT text FROM ideas")
    existing = set(row[0] for row in cur.fetchall())
    all_ideas = [
        # === 0–3 месяца (0–90 дней) ===
        (0, 90, "моторика", "Выкладывайте малыша на животик на 1–2 минуты несколько раз в день — это укрепляет шею и спинку."),
        (0, 90, "моторика", "Игра с погремушкой: медленно водите ей перед глазами, чтобы малыш следил взглядом."),
        (0, 90, "сенсорика", "Поглаживайте малыша разными тканями: шёлк, хлопок, махровое полотенце, мех."),
        (0, 90, "сенсорика", "Включите спокойную музыку и покачайте ребёнка на руках в такт."),
        (0, 90, "речь", "Разговаривайте с малышом, комментируйте всё, что делаете: «Сейчас мы пойдём купаться»."),
        (0, 90, "речь", "Пойте колыбельные и простые песенки, делая паузы, чтобы малыш мог «ответить» гулением."),
        (0, 90, "познание", "Показывайте чёрно-белые картинки с узорами — они лучше всего видны новорождённому."),
        (0, 90, "социальное", "Держите малыша на руках лицом к себе и улыбайтесь — он учится распознавать эмоции."),
        (0, 90, "моторика", "Массаж пальчиков: нежно разминайте каждый пальчик, приговаривая потешки."),
        (0, 90, "сенсорика", "Подуйте на ручки и ножки малыша — лёгкий ветерок развивает чувствительность."),

        # === 3–6 месяцев (90–180 дней) ===
        (90, 180, "моторика", "Подвесьте игрушки на резинке над кроваткой — пусть малыш пытается их схватить."),
        (90, 180, "моторика", "Давайте в ручки разные по форме и текстуре предметы: мячик, кубик, мягкую игрушку."),
        (90, 180, "моторика", "Упражнение «велосипед»: аккуратно двигайте ножками малыша, как будто он крутит педали."),
        (90, 180, "сенсорика", "Покажите, как звенят разные предметы: бубен, погремушка, ложка о чашку."),
        (90, 180, "сенсорика", "Позвольте малышу потрогать воду во время купания, поймать струйку."),
        (90, 180, "речь", "Пойте песенки с паузами — малыш будет гулить в ответ, поддерживайте «диалог»."),
        (90, 180, "речь", "Читайте короткие стишки (Барто, Маршак) с выразительной интонацией."),
        (90, 180, "познание", "Игра «ку-ку» с платком: закрывайте лицо и открывайте — малыш учится, что вы не исчезаете."),
        (90, 180, "познание", "Показывайте себя в зеркале и называйте: «Это мама! А это — малыш!»"),
        (90, 180, "социальное", "Хлопайте в ладоши и радуйтесь — малыш копирует эмоции."),

        # === 6–9 месяцев (180–270 дней) ===
        (180, 270, "моторика", "Игры с крупными кубиками — стройте башню и позволяйте малышу её рушить."),
        (180, 270, "моторика", "Дайте малышу безопасную ложку и миску — пусть учится перекладывать предметы."),
        (180, 270, "моторика", "Спрячьте игрушку под платок — пусть ищет, это развивает координацию."),
        (180, 270, "моторика", "Ползание за мячиком: катите мяч, а малыш пусть догоняет."),
        (180, 270, "сенсорика", "Сенсорная коробка: контейнер с крупой, фасолью или макаронами (под присмотром!)."),
        (180, 270, "сенсорика", "Игры с водой: переливайте воду из стакана в стакан во время купания."),
        (180, 270, "речь", "Читайте книжки с яркими картинками, называйте предметы и показывайте на них пальцем."),
        (180, 270, "речь", "Учите простые слова: «дай», «на», «мама», «папа» — повторяйте в игре."),
        (180, 270, "познание", "Игра «сортер»: покажите, как вставлять фигурки в отверстия."),
        (180, 270, "познание", "Спрячьте игрушку за спину и спросите «Где мишка?» — малыш будет искать."),
        (180, 270, "социальное", "Играйте в «ладушки» и «сороку-ворону» — это весело и развивает речь."),

        # === 9–12 месяцев (270–365 дней) ===
        (270, 365, "моторика", "Учите ставить кубик на кубик — начните с двух, потом больше."),
        (270, 365, "моторика", "Катайте мяч друг другу, сидя на полу."),
        (270, 365, "моторика", "Дайте карандаш и бумагу — пусть малыш черкает (под присмотром)."),
        (270, 365, "моторика", "Игры с вкладышами: пирамидка, стаканчики один в другой."),
        (270, 365, "сенсорика", "Игра с крупами: пересыпайте ложкой из одной чашки в другую."),
        (270, 365, "сенсорика", "Тесто для лепки (съедобное): мука + вода, можно мять руками."),
        (270, 365, "речь", "Называйте части тела: «Где носик? Вот носик!» — и трогайте их."),
        (270, 365, "речь", "Пойте песенки с движениями: «Мишка косолапый», «Зайка серенький»."),
        (270, 365, "познание", "Игра «что пропало»: уберите одну игрушку из трёх, малыш показывает, какая исчезла."),
        (270, 365, "познание", "Показывайте животных на картинках и озвучивайте: «Мяу», «Гав-гав»."),
        (270, 365, "социальное", "Играйте в «дочки-матери» с мягкими игрушками: покормите мишку, уложите спать."),
        (270, 365, "социальное", "Учите махать «пока-пока» и «привет»."),

        # === Универсальные (0–365 дней) ===
        (0, 365, "сенсорика", "Прогулка на свежем воздухе: показывайте листья, цветы, облака, слушайте птиц."),
        (0, 365, "социальное", "Обнимашки и поцелуи: тактильный контакт — основа эмоционального развития."),
        (0, 365, "речь", "Пойте песенку «Каравай» и водите хоровод вокруг малыша."),
    ]
    new_ideas = [idea for idea in all_ideas if idea[3] not in existing]
    if new_ideas:
        cur.executemany("INSERT INTO ideas (age_min, age_max, category, text) VALUES (?,?,?,?)", new_ideas)
        print(f"Добавлено {len(new_ideas)} новых идей в базу.")
    
    # === База знаний ===
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

# --- Пользователи ---
def get_user(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {"user_id": row[0], "child_birthday": row[1], "morning_brief_time": row[2], "timezone": row[3]}
    return None

def create_user(user_id: int, child_birthday: str, morning_brief_time: str = "08:00", timezone: str = "Asia/Krasnoyarsk"):
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

# --- События ---
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

# --- Идеи ---
def get_idea_by_age(age_days: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT text FROM ideas WHERE age_min <= ? AND age_max >= ? ORDER BY RANDOM() LIMIT 1",
                (age_days, age_days))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "Проведите время с ребёнком на свежем воздухе."

def get_ideas_by_age(age_days: int, limit: int = 5):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT text FROM ideas WHERE age_min <= ? AND age_max >= ? ORDER BY RANDOM() LIMIT ?",
                (age_days, age_days, limit))
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]

# --- База знаний ---
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
import sqlite3
import os
import json
from slugify import slugify

DB_PATH = os.path.join(os.path.dirname(__file__), 'weather.db')

# remove database first
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS cities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        timezone TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL
    )''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS styles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        position INTEGER NOT NULL
    )''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS weather_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        city_id INTEGER NOT NULL,
        style_id INTEGER NOT NULL,
        time_period TEXT NOT NULL,
        date TEXT NOT NULL,
        weather_json TEXT NOT NULL,
        report_text TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(city_id) REFERENCES cities(id),
        FOREIGN KEY(style_id) REFERENCES styles(id),
        UNIQUE(city_id, style_id, time_period, date)
    )''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

def populate_from_config():
    with open("config.json", encoding="utf-8") as f:
        config = json.load(f)
    cities = config["CITIES"]
    styles = config["STYLES"]
    conn = get_db()
    c = conn.cursor()
    for city in cities:
        slug = slugify(city['name'])
        c.execute('INSERT OR IGNORE INTO cities (name, slug, timezone, lat, lon) VALUES (?, ?, ?, ?, ?)', (city['name'], slug, city['timezone'], city['lat'], city['lon']))
    for i, style in enumerate(styles):
        c.execute('INSERT OR IGNORE INTO styles (name, position) VALUES (?, ?)', (style, i))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    populate_from_config()
    print("Database initialized and populated from config.json.")

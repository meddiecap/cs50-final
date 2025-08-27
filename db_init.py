import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), 'weather.db')

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
        lat REAL NOT NULL,
        lon REAL NOT NULL
    )''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS styles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS weather_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_id INTEGER NOT NULL,
        style_id INTEGER NOT NULL,
        time_period TEXT NOT NULL,
        date TEXT NOT NULL,
        weather_json TEXT NOT NULL,
        report_text TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(city_id) REFERENCES cities(id),
        FOREIGN KEY(style_id) REFERENCES styles(id),
        UNIQUE(city_id, style_id, time_period, date)
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
        c.execute('INSERT OR IGNORE INTO cities (name, lat, lon) VALUES (?, ?, ?)', (city['name'], city['lat'], city['lon']))
    for style in styles:
        c.execute('INSERT OR IGNORE INTO styles (name) VALUES (?)', (style,))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    populate_from_config()
    print("Database initialized and populated from config.json.")

from flask import request
from datetime import datetime
import requests
import sqlite3
import os
from google import genai
import json
from urllib.parse import quote
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
import zoneinfo

DB_PATH = os.path.join(os.path.dirname(__file__), 'weather.db')
def get_db():
	conn = sqlite3.connect(DB_PATH)
	conn.row_factory = sqlite3.Row
	return conn

def get_user_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if (ip == '127.0.0.1'):
        ip = "75.157.111.33"
    return ip

def get_user_location(ip):
    if ip:
        # Fetch location data from ip-api.com
        try:
            resp = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)
            if resp.status_code == 200:
                return resp.json()
            
            if resp.status_code == 429:
                return {"error": "Rate limit exceeded"}
            elif resp.status_code == 403:
                return {"error": "Access denied"}
            elif resp.status_code == 404:
                return {"error": "Location not found"}
        except requests.RequestException:
            pass

    return {"error": "Could not determine location"}

def get_time_period():
    hour = datetime.now().hour
    if 0 <= hour < 11:
        return "morning"
    elif 11 <= hour < 18:
        return "midday"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "night"
    
def get_time_period_from_json(weather_json):
    current_time = datetime.fromisoformat(weather_json["current"]["time"])
    hour = current_time.hour
    if 0 <= hour < 11:
        return "morning"
    elif 11 <= hour < 18:
        return "midday"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "night"

def get_weather(city, timezone_str="America/Los_Angeles"):
    tz_param = quote(timezone_str)
    url = (
        f"http://api.open-meteo.com/v1/forecast?latitude={city['lat']}&longitude={city['lon']}"
        f"&current=temperature_2m,wind_direction_10m,wind_speed_10m,pressure_msl,relative_humidity_2m,weather_code"
        f"&hourly=wind_speed_10m,wind_direction_10m,temperature_2m,weather_code,is_day"
        f"&timezone={tz_param}&forecast_days=2"
    )
    resp = requests.get(url)
    if resp.status_code == 200:

        # add url to output
        resp_json = resp.json()
        resp_json["url"] = url
        return resp_json
    return {}

def get_current_weather(city, timezone_str="America/Los_Angeles"):
    """
    Fetches the current weather for a specific city.
    """
    # if cities is a list, comma-separate lat and lon
    if isinstance(city, list):
        lat = ",".join(str(c['lat']) for c in city)
        lon = ",".join(str(c['lon']) for c in city)
    else:
        lat = city['lat']
        lon = city['lon']

    tz_param = quote(timezone_str)
    url = (
        f"http://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,wind_direction_10m,wind_speed_10m,pressure_msl,relative_humidity_2m,weather_code,is_day"
        f"&timezone={tz_param}"
    )
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()
        
        # attach city information when it's a list or dict
        if isinstance(city, dict):
            data['city'] = city
            data['location_name'] = city['name']
        elif isinstance(city, list):
            for i, c in enumerate(city):
                data[i]['city'] = c
                data[i]['location_name'] = c['name']

        return data

    return {}
    
STYLE_INSTRUCTIONS = {
    "Normal Weather Report Style": """
    Use a friendly, engaging, newsletter/blog tone (not dry newsroom).
    Short paragraphs (use p-tags), clear headers or emojis for flow (e.g. 🌤️ Morning, ☀️ Afternoon).
    Easy to read on the web: conversational, light, a touch of personality.
    """,
    "Fashion Advice Style": """
    Goal: outfit guidance. Weather summary: max 2 concise sentences.
    ≥70% of the text = concrete clothing advice (tops, bottoms/dress, footwear, outer layer, accessories).
    Map advice to data: heat → breathable fabrics/short sleeves; cool morning → layers; wind > 15 km/h → windbreaking layer; strong sun/heat → hat/sunscreen/sunglasses; cool evening → light sweater.
    Include fabric suggestions (cotton/linen/tech-breathables), and one “elevate the look” tip.
    Write in an upbeat fashion-mag/newsletter voice (no jargon dump).
    """,
    "Shakespearean": "Fully commit to Shakespearean style without mixing in newsletter/blog tone.",
    "Noir": "Fully commit to Noir style without mixing in newsletter/blog tone.",
    "Sci-Fi": "Fully commit to Sci-Fi style without mixing in newsletter/blog tone.",
    "Children's Storybook": "Fully commit to Children's Storybook style without mixing in newsletter/blog tone. Reading level: 5th grade.",
    "Pirate": "Fully commit to Pirate style without mixing in newsletter/blog tone.",
}

def call_llm_api(city, weather, style):
    """
    Calls Google Gemini API (using google-genai client) to generate a weather report in the selected style.
    """

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        return "[Error: GEMINI_API_KEY not set in environment.]"
	
    GEMINI_API_MODEL = os.environ.get("GEMINI_API_MODEL", "gemini-2.5-flash-lite")

    from datetime import datetime, timedelta
    import zoneinfo

    weather_json = json.dumps(weather, indent=2)

    # always use the locations local time, not the user's local time.
    tz = zoneinfo.ZoneInfo(weather["timezone"])
    now = datetime.now(tz)
    local_date = now.strftime("%Y-%m-%d, %A")
    tomorrow_date = (now + timedelta(days=1)).strftime("%Y-%m-%d, %A")

    # only include relevant style instructions
    prompt_style_instructions = STYLE_INSTRUCTIONS.get(style, "")

    prompt = f"""
    ROLE: You are a creative weather editor for a website.
    Write a weather report for {city} in {style}. Use at least 200 words. 250 words max.

    Context:
    - timezone: {tz}
    - local_date: {local_date}
    - tomorrow_date: {tomorrow_date}
    - current_time_of_day: {get_time_period_from_json(weather)}

    Hard rules (must follow):
    - If current_time_of_day in ["evening","night"]: 
    1) Start with tomorrow_date. 
    2) Cover tomorrow 06:00–22:00 (temp ranges, wind, any rain if present).
    3) Tonight: ≤1 sentence.
    - If current_time_of_day == "morning": focus on the rest of today 08:00–22:00.
    - If current_time_of_day == "midday": ≤1 sentence about the morning, then the rest of today until 22:00.
    - Do not open with current conditions unless it's morning.
    - Do not invent data not present in JSON.

    Weather JSON:
    {weather_json}

    STYLE:
    - Always write in the requested style: {style}.
    {prompt_style_instructions}

    FORMATTING:
    - Always start with an <h1> headline for the city and date.
    - If the time period is "morning":
        - Add a TLDR summary as an unordered <ul> list with three <li> items: morning, afternoon, evening (each with a short summary).
    - If the time period is not "morning":
        - Add a <h2>Summary</h2> section with a <p> summarizing the day up to now.
    - For each relevant period (morning, afternoon, evening):
        - Use a <h2> header for the period name (e.g., <h2>Afternoon</h2>).
        - Follow with a <p> paragraph describing the weather for that period.
    - Only use the following HTML tags: <h1>, <h2>, <ul>, <ol>, <li>, <p>, <strong>, <em>, <br>, <span>.
    - Do NOT use <script>, <style>, <iframe>, <link>, <img>, <video>, <audio>, or any other HTML/JS/CSS.
    - Keep the HTML minimal, clean, and semantic.
    - If uncertain, prefer plain text over unsupported HTML.

    OUTPUT:
    - Always follow this structure:
        1. <h1> headline
        2. TLDR <ul> (if morning) OR <h2>Summary</h2> + <p> (if not morning)
        3. For each period (morning, afternoon, evening): <h2> + <p>
    - Do not include any content outside this structure.
    - Ensure the output is lively, readable, and consistent every time.
    """

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_API_MODEL,
            contents=prompt
        )
        # The response object may have .text or .candidates[0].content.parts[0].text
        if hasattr(response, 'text'):
            return response.text
        # Fallback for other response structures
        if hasattr(response, 'candidates') and response.candidates:
            parts = response.candidates[0].content.parts
            if parts and hasattr(parts[0], 'text'):
                return parts[0].text
        return str(response)
    except Exception as e:
        return f"[Gemini API exception]: {e}"


def beaufort_scale(windspeed):
    """
    Convert wind speed in km/h to Beaufort scale.
    """
    if windspeed < 1:
        return 0  # Calm
    elif windspeed < 6:
        return 1  # Light air
    elif windspeed < 12:
        return 2  # Light breeze
    elif windspeed < 20:
        return 3  # Gentle breeze
    elif windspeed < 29:
        return 4  # Moderate breeze
    elif windspeed < 39:
        return 5  # Fresh breeze
    elif windspeed < 50:
        return 6  # Strong breeze
    elif windspeed < 62:
        return 7  # High wind
    elif windspeed < 75:
        return 8  # Gale
    elif windspeed < 89:
        return 9  # Strong gale
    elif windspeed < 103:
        return 10  # Storm
    elif windspeed < 118:
        return 11  # Violent storm
    else:
        return 12  # Hurricane
    
def wind_direction_cardinal(degree):
    """
    Convert wind direction in degrees to the closest cardinal direction (e.g. N, NNE, NE, etc.).
    0°/360° is North, 90° is East, 180° is South, 270° is West.
    """
    directions = [
        'N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
        'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'
    ]
    idx = int((degree % 360) / 22.5 + 0.5) % 16
    return directions[idx]
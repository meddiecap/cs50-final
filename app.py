from datetime import datetime
# In-memory cache: {(city, style, time_period): report}
ai_report_cache = {}

# Helper to determine time of day
def get_time_period():
	hour = datetime.now().hour
	if 5 <= hour < 11:
		return "morning"
	elif 11 <= hour < 16:
		return "midday"
	elif 16 <= hour < 21:
		return "evening"
	else:
		return "night"
	
from flask import Flask, render_template, request, jsonify
import requests
from google import genai

from dotenv import load_dotenv
load_dotenv()


import json
import os

app = Flask(__name__)

# Load CITIES and STYLES from config.json
with open("config.json", encoding="utf-8") as f:
	config = json.load(f)

CITIES = config["CITIES"]
STYLES = config["STYLES"]

def get_weather(city):
	url = (
		f"https://api.open-meteo.com/v1/forecast?latitude={city['lat']}&longitude={city['lon']}"
		"&current_weather=true&hourly=temperature_2m,wind_speed_10m,relative_humidity_2m,pressure_msl,cloud_cover&timezone=America%2FLos_Angeles&past_days=1&forecast_days=2"
	)
	resp = requests.get(url)
	if resp.status_code == 200:
		return resp.json()
	return {}

@app.route("/")
def index():
	city_names = [city["name"] for city in CITIES]
	return render_template("index.html", cities=city_names, styles=STYLES)


def call_llm_api(city, weather, style):
	"""
	Calls Google Gemini API (using google-genai client) to generate a weather report in the selected style.
	"""
	GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
	if not GEMINI_API_KEY:
		return "[Error: GEMINI_API_KEY not set in environment.]"
	
	GEMINI_API_MODEL = os.environ.get("GEMINI_API_MODEL", "gemini-2.5-flash")
	
	from datetime import datetime, timedelta
	import zoneinfo

	tz = zoneinfo.ZoneInfo("America/Los_Angeles")  # of je gewenste tz
	now = datetime.now(tz)
	local_date = now.strftime("%Y-%m-%d")
	tomorrow_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
	
	weather_json = json.dumps(weather, indent=2)

	prompt = f"""
	ROLE: You are a creative weather editor for a website.
	Write a weather report for {city} in {style}. Use at least 200 words. 250 words max.

	Context:
	- timezone: {tz}
	- local_date: {local_date}
	- tomorrow_date: {tomorrow_date}
	- current_time_of_day: {get_time_period()}

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
	- If style == "Normal Weather Report Style":
	• Use a friendly, engaging, newsletter/blog tone (not dry newsroom).
	• Short paragraphs, clear headers or emojis for flow (e.g. 🌤️ Morning, ☀️ Afternoon).
	• Easy to read on the web: conversational, light, a touch of personality.
	- For other styles (Shakespearean, Noir, Sci-Fi, Children’s Storybook, Pirate):
	• Fully commit to that style without mixing in newsletter/blog tone.

	OUTPUT:
	- Deliver a lively weather piece, formatted with line breaks for readability.
	- Keep the focus day clear (“Tomorrow …” if evening/night).
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

@app.route("/generate_report", methods=["POST"])
def generate_report():
	data = request.json
	city_name = data.get("city")
	style = data.get("style")

	# Find city info
	city = next((c for c in CITIES if c["name"] == city_name), None)
	if not city:
		return jsonify({"error": "City not found"}), 400
	time_period = get_time_period()
	cache_key = (city_name, style, time_period)

	# Check cache
	if cache_key in ai_report_cache:
		weather = get_weather(city)  # Always get fresh weather
		return jsonify({"report": ai_report_cache[cache_key], "weather": weather, "cached": True})
	
	# Not cached, call AI
	weather = get_weather(city)
	report = call_llm_api(city_name, weather, style)
	ai_report_cache[cache_key] = report
	
	return jsonify({"report": report, "weather": weather, "cached": False})

if __name__ == "__main__":
	app.run(debug=True)

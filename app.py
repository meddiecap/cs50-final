from flask import Flask, render_template_string, request, jsonify
import requests
from google import genai

from dotenv import load_dotenv
load_dotenv()

import json
import os

app = Flask(__name__)

# List of 10 major cities with their coordinates
CITIES = [
	{"name": "Vancouver", "lat": 49.2827, "lon": -123.1207},
	{"name": "New York", "lat": 40.7128, "lon": -74.0060},
	{"name": "London", "lat": 51.5074, "lon": -0.1278},
	{"name": "Tokyo", "lat": 35.6895, "lon": 139.6917},
	{"name": "Sydney", "lat": -33.8688, "lon": 151.2093},
	{"name": "Paris", "lat": 48.8566, "lon": 2.3522},
	{"name": "Cairo", "lat": 30.0444, "lon": 31.2357},
	{"name": "Rio de Janeiro", "lat": -22.9068, "lon": -43.1729},
	{"name": "Moscow", "lat": 55.7558, "lon": 37.6173},
	{"name": "Mumbai", "lat": 19.0760, "lon": 72.8777},
]

STYLES = [
	"Shakespearean Style",
	"Noir Detective Style",
	"Sci-Fi Futuristic Style",
	"Children’s Storybook Style",
	"Pirate Style",
	"Normal Weather Report Style"
]

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
	# Only send city names, not weather data
	city_names = [city["name"] for city in CITIES]
	return render_template_string(TEMPLATE, cities=city_names, styles=STYLES)

# Dummy LLM API call (replace with your actual LLM API integration)


def call_llm_api(city, weather, style):
	"""
	Calls Google Gemini API (using google-genai client) to generate a weather report in the selected style.
	"""
	api_key = os.environ.get("GEMINI_API_KEY")
	if not api_key:
		return "[Error: GEMINI_API_KEY not set in environment.]"
	
	from datetime import datetime, timedelta
	import zoneinfo

	tz = zoneinfo.ZoneInfo("America/Los_Angeles")  # of je gewenste tz
	now = datetime.now(tz)
	local_date = now.strftime("%Y-%m-%d")
	tomorrow_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")

	current_time_of_day = (
		"morning" if 5 <= now.hour < 12 else
		"midday" if 12 <= now.hour < 17 else
		"evening" if 17 <= now.hour < 24 else
		"night"
	)
	
	weather_json = json.dumps(weather, indent=2)

	prompt = f"""
	ROLE: You are a creative weather editor for a website.
	Write a weather report for {city} in {style}. Use 200-250 words max.

	Context:
	- timezone: {tz}
	- local_date: {local_date}
	- tomorrow_date: {tomorrow_date}
	- current_time_of_day: {current_time_of_day}

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
		client = genai.Client(api_key=api_key)
		response = client.models.generate_content(
			model="gemini-2.5-flash",
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
	weather = get_weather(city)
	report = call_llm_api(city_name, weather, style)
	return jsonify({"report": report, "weather": weather})

# Simple HTML template with inline JS
TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<title>World Weather - CS50 Final</title>
	<style>
		body { font-family: Arial, sans-serif; background: #f0f4f8; margin: 0; padding: 0; }
		.container { max-width: 900px; margin: 40px auto; background: #fff; border-radius: 10px; box-shadow: 0 2px 8px #0001; padding: 30px; }
		h1 { text-align: center; }
		select, button { padding: 6px 12px; border-radius: 5px; border: 1px solid #bbb; }
		.report-box { margin-top: 30px; background: #f9fafb; border-radius: 8px; padding: 20px; min-height: 80px; }
		.weather-table { margin-top: 20px; width: 100%; border-collapse: collapse; }
		.weather-table th, .weather-table td { padding: 10px; text-align: center; border-bottom: 1px solid #eee; }
		.weather-table th { background: #e0e7ef; }
	</style>
</head>
<body>
	<div class="container">
		<h1>Weather for 10 Major Cities</h1>
		<form id="reportForm" onsubmit="return false;">
			<label for="city">City:</label>
			<select id="city">
				{% for c in cities %}
				<option value="{{c}}">{{c}}</option>
				{% endfor %}
			</select>
			<label for="style">Style:</label>
			<select id="style">
				{% for s in styles %}
				<option value="{{s}}">{{s}}</option>
				{% endfor %}
			</select>
			<button onclick="generateReport()">Generate Weather Report</button>
		</form>
		<div class="report-box" id="reportBox">Select a city and style, then click Generate Weather Report.</div>
		<table class="weather-table" id="weatherTable" style="display:none;">
			<tr>
				<th>Temperature (°C)</th>
				<th>Windspeed (km/h)</th>
				<th>Weather Code</th>
			</tr>
			<tr>
				<td id="tempCell"></td>
				<td id="windCell"></td>
				<td id="codeCell"></td>
			</tr>
		</table>
	</div>
	<script>
		function generateReport() {
			const cityName = document.getElementById('city').value;
			const style = document.getElementById('style').value;
			fetch('/generate_report', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ city: cityName, style: style })
			})
			.then(res => res.json())
			.then(data => {
				document.getElementById('reportBox').innerText = data.report;
				// Show weather table
				if (data.weather) {
					document.getElementById('weatherTable').style.display = '';
					document.getElementById('tempCell').innerText = data.weather.temperature ?? 'N/A';
					document.getElementById('windCell').innerText = data.weather.windspeed ?? 'N/A';
					document.getElementById('codeCell').innerText = data.weather.weathercode ?? 'N/A';
				}
			});
		}
	</script>
</body>
</html>
'''

if __name__ == "__main__":
	app.run(debug=True)

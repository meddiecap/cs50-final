from flask import abort

from datetime import datetime
from flask import Flask, render_template, request, jsonify
import json

# Import get_time_period from helpers.py
from helpers import get_time_period, get_weather, call_llm_api

# In-memory cache: {(city, style, time_period): report}
ai_report_cache = {}

app = Flask(__name__)

# Load CITIES and STYLES from config.json
with open("config.json", encoding="utf-8") as f:
	config = json.load(f)

CITIES = config["CITIES"]
STYLES = config["STYLES"]

@app.route("/")
def index():
	city_names = [city["name"] for city in CITIES]
	return render_template("index.html", cities=city_names, styles=STYLES)

# Endpoint to get weather for arbitrary lat/lon (for user's location)
@app.route("/weather_at_location")
def weather_at_location():
	try:
		lat = float(request.args.get("lat"))
		lon = float(request.args.get("lon"))
	except (TypeError, ValueError):
		return jsonify({"error": "Invalid or missing lat/lon"}), 400
	# Use a dummy city dict for get_weather
	city = {"name": "Your Location", "lat": lat, "lon": lon}
	weather = get_weather(city)
	return jsonify({"weather": weather})


# Route for /<city> to show today's forecast for that city
@app.route("/<city_name>")
def city_forecast(city_name):
	# Find city by name (case-insensitive match)
	city = next((c for c in CITIES if c["name"].lower() == city_name.lower()), None)
	if not city:
		return abort(404, description="City not found")
	weather = get_weather(city)
	return render_template("city.html", city=city, weather=weather)

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

from flask import abort, Flask, render_template, request, jsonify
from datetime import datetime
import json

# Import get_time_period from helpers.py
from helpers import get_time_period, get_weather, call_llm_api, get_user_ip, get_user_location, get_db

# In-memory caches
ip_location_cache = {}  # {ip: {location and weather data}}

app = Flask(__name__)

@app.route("/")
def index():
	# Load cities and styles from the database
	conn = get_db()
	c = conn.cursor()
	c.execute('SELECT name FROM cities ORDER BY name')
	city_names = [row[0] for row in c.fetchall()]
	c.execute('SELECT name FROM styles ORDER BY name')
	styles = [row[0] for row in c.fetchall()]
	conn.close()

	# Get user IP
	ip = get_user_ip()
	if ip and "," in ip:
		ip = ip.split(",")[0].strip()
		
	user_location = ip_location_cache.get(ip)

	if not user_location:
		loc_data = get_user_location(ip)

		if loc_data.get("status") == "success":
			user_location = loc_data
			# Get weather for this location
			city = {"name": loc_data.get("city", "Your Location"), "lat": loc_data["lat"], "lon": loc_data["lon"]}
			user_weather = get_weather(city)
			user_location["weather"] = user_weather
			ip_location_cache[ip] = user_location

	return render_template("index.html", cities=city_names, styles=styles, user_location=user_location)

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
	# Find city by name (case-insensitive match) in DB
	conn = get_db()
	c = conn.cursor()
	c.execute('SELECT name, lat, lon FROM cities WHERE lower(name) = ?', (city_name.lower(),))
	row = c.fetchone()
	conn.close()
	if not row:
		return abort(404, description="City not found")
	city = {"name": row[0], "lat": row[1], "lon": row[2]}
	weather = get_weather(city)
	return render_template("city.html", city=city, weather=weather)

@app.route("/generate_report", methods=["POST"])
def generate_report():
	data = request.json
	city_name = data.get("city")
	style = data.get("style")

	time_period = get_time_period()
	today = datetime.now().strftime("%Y-%m-%d")

	# Get city_id, lat, lon and style_id from DB
	conn = get_db()
	c = conn.cursor()
	c.execute('SELECT id, lat, lon FROM cities WHERE name = ?', (city_name,))
	city_row = c.fetchone()
	c.execute('SELECT id FROM styles WHERE name = ?', (style,))
	style_row = c.fetchone()
	if not city_row or not style_row:
		conn.close()
		return jsonify({"error": "City or style not found in DB"}), 400
	city_id, lat, lon = city_row[0], city_row[1], city_row[2]
	style_id = style_row[0]

	# Check for cached report in DB
	c.execute('''SELECT weather_json, report_text FROM weather_reports
				WHERE city_id = ? AND style_id = ? AND time_period = ? AND date = ?''',
			  (city_id, style_id, time_period, today))
	row = c.fetchone()
	if row:
		# Cached report found
		weather = json.loads(row[0])
		report = row[1]
		conn.close()
		return jsonify({"report": report, "weather": weather, "cached": True})

	# Not cached, call API and store
	city = {"name": city_name, "lat": lat, "lon": lon}
	weather = get_weather(city)
	report = call_llm_api(city_name, weather, style)
	c.execute('''INSERT INTO weather_reports (city_id, style_id, time_period, date, weather_json, report_text)
				VALUES (?, ?, ?, ?, ?, ?)''',
			  (city_id, style_id, time_period, today, json.dumps(weather), report))
	conn.commit()
	conn.close()

	return jsonify({"report": report, "weather": weather, "cached": False})

if __name__ == "__main__":
	app.run(debug=True)

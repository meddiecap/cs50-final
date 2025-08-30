from flask import abort, Flask, render_template, request, redirect, url_for, session, flash
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import json
import dateutil.parser
import zoneinfo

app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Import get_time_period from helpers.py
from helpers import *

from weather_helper import WEATHER_ICON_MAP, get_weather_icon, get_weather_simplified, hourly_dicts_from_openmeteo, filtered_hourly_dicts_from_openmeteo

# In-memory caches
ip_location_cache = {}  # {ip: {location and weather data}}

@app.route("/")
def index():
	# Load cities and styles from the database
	conn = get_db()
	c = conn.cursor()
	c.execute('SELECT name, slug, timezone, lat, lon FROM cities ORDER BY name')
	city_names = [{"name": row[0], "slug": row[1], "timezone": row[2], "lat": row[3], "lon": row[4]} for row in c.fetchall()]
	c.execute('SELECT name FROM styles ORDER BY name')
	styles = [row[0] for row in c.fetchall()]
	conn.close()
	
	# add current weather icon
	cities_current_weather = get_current_weather(city_names)
	for city in cities_current_weather:
		city["current"]["icon"] = get_weather_icon(city["current"]["weather_code"], city["current"]["is_day"])
		city['current']['description'] = get_weather_simplified(city["current"]["weather_code"], city["current"]["is_day"])
		# Set hour:minute to city timezone from city_names
		city['current']['time'] = datetime.now(zoneinfo.ZoneInfo(city['city']['timezone'])).strftime("%H:%M")

	# Get user IP
	ip = get_user_ip()

	# No caching temporary
	user_location = None # ip_location_cache.get(ip)

	if not user_location:
		loc_data = get_user_location(ip)

		if loc_data.get("status") == "success":
			user_location = loc_data
			# Get weather for this location, using user's timezone if available
			city = {"name": loc_data.get("city", "Your Location"), "lat": loc_data["lat"], "lon": loc_data["lon"]}
			timezone_str = loc_data.get("timezone", "America/Los_Angeles")
			user_location["weather"] = get_weather(city, timezone_str)
			user_location["weather"]['current']['cardinal'] = wind_direction_cardinal(user_location["weather"]['current']['wind_direction_10m'])
			ip_location_cache[ip] = user_location

	# Prepare 24-hour hourly forecast for user's location (if available)
	user_hourly_forecast = None
	if user_location and user_location.get("weather") and user_location["weather"].get("hourly"):
		hourly = user_location["weather"]["hourly"]

		# open-meteo returns arrays: time, temperature_2m, wind_speed_10m, etc.
		times = hourly.get("time", [])
		temps = hourly.get("temperature_2m", [])
		winds = hourly.get("wind_speed_10m", [])
		wind_directions = hourly.get("wind_direction_10m", [])
		weather_codes = hourly.get("weather_code", [])
		is_day_flags = hourly.get("is_day", [])  # 1 for day, 0 for night

		# Use user's timezone for current time		
		timezone_str = user_location.get("timezone", "America/Los_Angeles")
		try:
			tz = zoneinfo.ZoneInfo(timezone_str)
		except Exception:
			tz = zoneinfo.ZoneInfo("America/Los_Angeles")
		now = datetime.now(tz)
		start_idx = 0
		for i, t in enumerate(times):
			tdt = dateutil.parser.isoparse(t)
			if tdt.tzinfo is None:
				tdt = tdt.replace(tzinfo=tz)
			# Find the first hour that is >= current hour (rounded down)
			if tdt.hour == now.hour and tdt.date() == now.date():
				start_idx = i
				break
			elif tdt > now:
				start_idx = i
				break

		# Always get 24 hours from start_idx
		end_idx = min(start_idx + 24, len(times))
		user_hourly_forecast = []
		for i in range(start_idx, end_idx):
			# format date time to hour
			hour = times[i].split("T")[1]
			user_hourly_forecast.append({
				"original_time": times[i],
				"time": hour,
				"temperature": temps[i] if i < len(temps) else None,
				"windspeed": winds[i] if i < len(winds) else None,
				"beaufort": beaufort_scale(winds[i]) if i < len(winds) else None,
				"winddirection": wind_directions[i] if i < len(wind_directions) else None,
				"cardinal": wind_direction_cardinal(wind_directions[i]) if i < len(wind_directions) else None,
				"weather_code": weather_codes[i] if i < len(weather_codes) else None,
				"icon": get_weather_icon(weather_codes[i], is_day=is_day_flags[i]) if i < len(weather_codes) else None
			})

	return render_template("index.html", cities=cities_current_weather, styles=styles, user_location=user_location, user_hourly_forecast=user_hourly_forecast)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Validate, check for existing user, etc.
        password_hash = generate_password_hash(password)
        # Insert into DB...
        conn = get_db()
        c = conn.cursor()
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
        conn.commit()
        conn.close()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
	if request.method == 'POST':
		username = request.form['username']
		password = request.form['password']

		# Fetch user from DB...
		conn = get_db()
		c = conn.cursor()
		c.execute('SELECT * FROM users WHERE username = ?', (username,))
		user = c.fetchone()
		conn.close()

		if user and check_password_hash(user['password_hash'], password):
			session['user_id'] = user['id']
			return redirect(url_for('index'))
		
		flash('Invalid credentials', 'danger')
	return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Route for /<city> to show today's forecast for that city
@app.route("/<city_name>")
def city_forecast(city_name):
	# Find city by name (case-insensitive match) in DB
	conn = get_db()
	c = conn.cursor()
	c.execute('SELECT id, name, lat, lon, timezone FROM cities WHERE slug = ?', (city_name.lower(),))
	row = c.fetchone()
	conn.close()
	if not row:
		return abort(404, description="City not found")

	city = {"id": row[0], "name": row[1], "lat": row[2], "lon": row[3], "timezone": row[4]}
	weather = get_weather(city, city['timezone'])

	# Use city's timezone for current time and find the starting index
	# of the current hour
	timezone_str = city["timezone"]
	tz = zoneinfo.ZoneInfo(timezone_str)
	now = datetime.now(tz)

	# Prepare 24-hour hourly forecast for user's location (if available)
	user_hourly_forecast = None
	if weather and weather.get("hourly"):
		hourly = weather["hourly"]

		# open-meteo returns arrays: time, temperature_2m, wind_speed_10m, etc.
		times = hourly.get("time", [])
		temps = hourly.get("temperature_2m", [])
		winds = hourly.get("wind_speed_10m", [])
		wind_directions = hourly.get("wind_direction_10m", [])
		weather_codes = hourly.get("weather_code", [])
		is_day_flags = hourly.get("is_day", [])  # 1 for day, 0 for night

		start_idx = 0
		for i, t in enumerate(times):
			tdt = dateutil.parser.isoparse(t)
			if tdt.tzinfo is None:
				tdt = tdt.replace(tzinfo=tz)
			# Find the first hour that is >= current hour (rounded down)
			if tdt.hour == now.hour and tdt.date() == now.date():
				start_idx = i
				break
			elif tdt > now:
				start_idx = i
				break

		# Always get 24 hours from start_idx
		end_idx = min(start_idx + 24, len(times))
		user_hourly_forecast = []
		for i in range(start_idx, end_idx):
			# change hour format to 12-hour format
			hour = times[i].split("T")[1]
			user_hourly_forecast.append({
				"original_time": times[i],
				"time": hour,
				"temperature": temps[i] if i < len(temps) else None,
				"windspeed": winds[i] if i < len(winds) else None,
				"beaufort": beaufort_scale(winds[i]) if i < len(winds) else None,
				"winddirection": wind_directions[i] if i < len(wind_directions) else None,
				"cardinal": wind_direction_cardinal(wind_directions[i]) if i < len(wind_directions) else None,
				"weather_code": weather_codes[i] if i < len(weather_codes) else None,
				"icon": get_weather_icon(weather_codes[i], is_day=is_day_flags[i]) if i < len(weather_codes) else None
			})
			
	# Get all styles ordered by position
	conn = get_db()
	c = conn.cursor()
	c.execute('SELECT id, name, position FROM styles ORDER BY position ASC')
	styles = [dict(id=row[0], name=row[1], position=row[2]) for row in c.fetchall()]

	# Get default report for the first style (assume "Normal Weather Report" or first in list)
	default_style = styles[0]
	style_id = default_style['id']
	style_name = default_style['name']
	time_period = get_time_period_from_json(weather)
	today = now.strftime("%Y-%m-%d")

	# Check for cached report in DB
	c.execute('''SELECT weather_json, report_text FROM weather_reports
				WHERE user_id IS NULL AND city_id = ? AND style_id = ? AND time_period = ? AND date = ?''',
			  (city["id"], style_id, time_period, today))
	row = c.fetchone()

	if row:
		# Cached report found
		report = row[1]
	else:
		# Not cached, call API and store
		report = call_llm_api(city["name"], weather, style_name)
		c.execute('''INSERT INTO weather_reports (city_id, style_id, time_period, date, weather_json, report_text)
					VALUES (?, ?, ?, ?, ?, ?)''',
				(city["id"], style_id, time_period, today, json.dumps(weather), report))
		conn.commit()

	conn.close()	

	logged_in = session.get('user_id') is not None
	return render_template("city.html", city=city, report=report, weather=weather, user_hourly_forecast=user_hourly_forecast, styles=styles, logged_in=logged_in)


if __name__ == "__main__":
	app.run(debug=True)

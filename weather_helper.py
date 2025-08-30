"""
weather_helper.py

Maps open-meteo weather codes and day/night to icon filenames in /static/icons/static/.
"""

from datetime import datetime, timedelta
import dateutil.parser

# Mapping based on open-meteo weather codes:
# https://open-meteo.com/en/docs#api_form
# Adjust as needed to match your icon set and desired granularity.

WEATHER_ICON_MAP = {
    # code: (day_icon, night_icon, neutral_icon)
    0: ("clear-day.svg", "clear-night.svg", "clear-day.svg"),  # Clear sky
    1: ("cloudy-1-day.svg", "cloudy-1-night.svg", "cloudy-1.svg"),  # Mainly clear
    2: ("cloudy-2-day.svg", "cloudy-2-night.svg", "cloudy-2.svg"),  # Partly cloudy
    3: ("cloudy-3-day.svg", "cloudy-3-night.svg", "cloudy-3.svg"),  # Overcast
    45: ("fog-day.svg", "fog-night.svg", "fog.svg"),  # Fog
    48: ("frost-day.svg", "frost-night.svg", "frost.svg"),  # Depositing rime fog
    51: ("rainy-1-day.svg", "rainy-1-night.svg", "rainy-1.svg"),  # Drizzle: Light
    53: ("rainy-2-day.svg", "rainy-2-night.svg", "rainy-2.svg"),  # Drizzle: Moderate
    55: ("rainy-3-day.svg", "rainy-3-night.svg", "rainy-3.svg"),  # Drizzle: Dense
    56: ("rain-and-sleet-mix.svg", "rain-and-sleet-mix.svg", "rain-and-sleet-mix.svg"),  # Freezing Drizzle: Light
    57: ("rain-and-sleet-mix.svg", "rain-and-sleet-mix.svg", "rain-and-sleet-mix.svg"),  # Freezing Drizzle: Dense
    61: ("rainy-1-day.svg", "rainy-1-night.svg", "rainy-1.svg"),  # Rain: Slight
    63: ("rainy-2-day.svg", "rainy-2-night.svg", "rainy-2.svg"),  # Rain: Moderate
    65: ("rainy-3-day.svg", "rainy-3-night.svg", "rainy-3.svg"),  # Rain: Heavy
    66: ("rain-and-sleet-mix.svg", "rain-and-sleet-mix.svg", "rain-and-sleet-mix.svg"),  # Freezing Rain: Light
    67: ("rain-and-sleet-mix.svg", "rain-and-sleet-mix.svg", "rain-and-sleet-mix.svg"),  # Freezing Rain: Heavy
    71: ("snowy-1-day.svg", "snowy-1-night.svg", "snowy-1.svg"),  # Snow fall: Slight
    73: ("snowy-2-day.svg", "snowy-2-night.svg", "snowy-2.svg"),  # Snow fall: Moderate
    75: ("snowy-3-day.svg", "snowy-3-night.svg", "snowy-3.svg"),  # Snow fall: Heavy
    77: ("snowy-1-day.svg", "snowy-1-night.svg", "snowy-1.svg"),  # Snow grains
    80: ("rainy-1-day.svg", "rainy-1-night.svg", "rainy-1.svg"),  # Rain showers: Slight
    81: ("rainy-2-day.svg", "rainy-2-night.svg", "rainy-2.svg"),  # Rain showers: Moderate
    82: ("rainy-3-day.svg", "rainy-3-night.svg", "rainy-3.svg"),  # Rain showers: Violent
    85: ("snowy-1-day.svg", "snowy-1-night.svg", "snowy-1.svg"),  # Snow showers: Slight
    86: ("snowy-2-day.svg", "snowy-2-night.svg", "snowy-2.svg"),  # Snow showers: Heavy
    95: ("isolated-thunderstorms-day.svg", "isolated-thunderstorms-night.svg", "isolated-thunderstorms.svg"),  # Thunderstorm: Slight/Moderate
    96: ("severe-thunderstorm.svg", "severe-thunderstorm.svg", "severe-thunderstorm.svg"),  # Thunderstorm with hail: Slight
    99: ("severe-thunderstorm.svg", "severe-thunderstorm.svg", "severe-thunderstorm.svg"),  # Thunderstorm with hail: Heavy
}

DEFAULT_ICON = "cloudy.svg"

def get_weather_icon(weathercode, is_day=None):
    """
    Returns the icon filename for a given open-meteo weather code and day/night flag.
    - weathercode: int, open-meteo weather code
    - is_day: int or bool or None. 1/True for day, 0/False for night, None for neutral/default.
    """
    icons = WEATHER_ICON_MAP.get(weathercode)
    if not icons:
        return DEFAULT_ICON
    if is_day is None:
        return icons[2]  # neutral/default
    if is_day in (1, True):
        return icons[0]
    if is_day in (0, False):
        return icons[1]
    return icons[2]

def get_weather_oneword(weathercode, is_day=None):
    """
    Returns a one-word weather description for a given open-meteo weather code.
    """
    code_map = {
        # Daytime sunny, nighttime clear
        0: is_day and "sunny" or "clear",
        1: "mostly clear",
        2: "partly cloudy",
        3: "cloudy",
        45: "fog",
        48: "fog",
        51: "drizzle",
        53: "drizzle",
        55: "drizzle",
        56: "freezing drizzle",
        57: "freezing drizzle",
        61: "rain",
        63: "rain",
        65: "rain",
        66: "freezing rain",
        67: "freezing rain",
        71: "snow",
        73: "snow",
        75: "snow",
        77: "snow",
        80: "rain showers",
        81: "rain showers",
        82: "rain showers",
        85: "snow showers",
        86: "snow showers",
        95: "thunderstorm",
        96: "thunderstorm",
        99: "thunderstorm",
    }
    return code_map.get(weathercode, "unknown")

def get_weather_simplified(weathercode, is_day=None):
    """
    Returns a simplified one-word weather description for a given open-meteo weather code.
    """
    code_map = {
        # Daytime sunny, nighttime clear
        0: is_day and "sunny" or "clear",
        1: "cloudy",
        2: "cloudy",
        3: "cloudy",
        45: "fog",
        48: "fog",
        51: "rainy",
        53: "rainy",
        55: "rainy",
        56: "rainy",
        57: "rainy",
        61: "rainy",
        63: "rainy",
        65: "rainy",
        66: "rainy",
        67: "rainy",
        71: "snowy",
        73: "snowy",
        75: "snowy",
        77: "snowy",
        80: "rainy",
        81: "rainy",
        82: "rainy",
        85: "snowy",
        86: "snowy",
        95: "thunderstorm",
        96: "thunderstorm",
        99: "thunderstorm",
    }
    return code_map.get(weathercode, "unknown")

def hourly_dicts_from_openmeteo(hourly):
    # Convert parallel lists to list of dicts
    keys = list(hourly.keys())
    length = len(hourly[keys[0]])
    return [
        {k: hourly[k][i] for k in keys}
        for i in range(length)
    ]


def filtered_hourly_dicts_from_openmeteo(hourly, start_hour=None, end_hour=None):
    """
    Convert parallel lists to list of dicts, filtered by start_hour and end_hour (inclusive).
    - start_hour, end_hour: datetime objects (local time, matching the timezone of the API call/time strings)
    Defaults: start_hour = now (rounded down), end_hour = start_hour + 24h
    """
    keys = list(hourly.keys())
    length = len(hourly[keys[0]])
    # Parse all times to datetime
    times = [dateutil.parser.isoparse(t) for t in hourly['time']]
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    if start_hour is None:
        start_hour = now
    else:
        start_hour = start_hour.replace(minute=0, second=0, microsecond=0)
    if end_hour is None:
        end_hour = start_hour + timedelta(hours=24)
    else:
        end_hour = end_hour.replace(minute=0, second=0, microsecond=0)
    # Build filtered list
    result = []
    for i in range(length):
        t = times[i]
        if start_hour <= t < end_hour:
            result.append({k: hourly[k][i] for k in keys})
    return result

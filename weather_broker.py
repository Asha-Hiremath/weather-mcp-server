"""Weather Broker - Adapter module for Open-Meteo API calls.

This module handles all HTTP requests to weather APIs and returns clean dicts.
Keeps MCP tool functions thin by pushing HTTP/parsing logic here.

Using Open-Meteo API: https://open-meteo.com/
- No signup, no API key required
- ~10,000 calls/day for non-commercial use
- Supports current weather, forecast, and historical data
"""

import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Open-Meteo API endpoints
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# Simple city-to-coordinates cache (production would use a geocoding service)
CITY_COORDS = {
    "chicago": (41.8781, -87.6298),
    "austin": (30.2672, -97.7431),
    "new york": (40.7128, -74.0060),
    "san francisco": (37.7749, -122.4194),
    "seattle": (47.6062, -122.3321),
    "miami": (25.7617, -80.1918),
    "boston": (42.3601, -71.0589),
    "denver": (39.7392, -104.9903),
    "los angeles": (34.0522, -118.2437),
    "portland": (45.5152, -122.6784),
}


class WeatherBrokerError(Exception):
    """Base exception for weather broker errors."""
    pass


class LocationNotFoundError(WeatherBrokerError):
    """Raised when a location cannot be resolved."""
    pass


class APIError(WeatherBrokerError):
    """Raised when the weather API returns an error."""
    pass


def resolve_location(location: str) -> Dict[str, Any]:
    """Resolve a location string to lat/lon coordinates.
    
    Args:
        location: City name (e.g., "Chicago"), city with state (e.g., "Austin, TX"),
                 or "lat,lon" string (e.g., "41.8781,-87.6298")
    
    Returns:
        Dict with keys:
        - name: str - Resolved location name
        - latitude: float
        - longitude: float
    
    Raises:
        LocationNotFoundError: If location cannot be resolved
    """
    location = location.strip()
    
    # Check if lat,lon format
    if ',' in location:
        try:
            lat_str, lon_str = location.split(',', 1)
            lat = float(lat_str.strip())
            lon = float(lon_str.strip())
            return {
                "name": f"{lat:.4f}, {lon:.4f}",
                "latitude": lat,
                "longitude": lon
            }
        except ValueError:
            pass  # Not a valid lat,lon, try as city name
    
    # Check hardcoded cities (case-insensitive)
    location_lower = location.lower()
    # Try direct match
    if location_lower in CITY_COORDS:
        lat, lon = CITY_COORDS[location_lower]
        return {
            "name": location.title(),
            "latitude": lat,
            "longitude": lon
        }
    
    # Try matching first word (e.g., "Austin, TX" -> "austin")
    city_part = location_lower.split(',')[0].strip()
    if city_part in CITY_COORDS:
        lat, lon = CITY_COORDS[city_part]
        return {
            "name": location.title(),
            "latitude": lat,
            "longitude": lon
        }
    
    # Try Open-Meteo geocoding API
    try:
        response = requests.get(
            GEOCODING_URL,
            params={"name": location, "count": 1, "language": "en", "format": "json"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if not data.get("results"):
            raise LocationNotFoundError(f"Location not found: {location}")
        
        result = data["results"][0]
        return {
            "name": result.get("name", location),
            "latitude": result["latitude"],
            "longitude": result["longitude"]
        }
    
    except requests.RequestException as e:
        logger.error(f"Geocoding API error for '{location}': {e}")
        raise LocationNotFoundError(f"Could not resolve location: {location}")


def get_current_weather(location: str) -> Dict[str, Any]:
    """Get current weather conditions for a location.
    
    Args:
        location: City name, "City, State", or "lat,lon"
    
    Returns:
        Dict with keys:
        - location: str - Resolved location name
        - temperature: float - Current temp in °F
        - conditions: str - Weather description
        - humidity: int - Relative humidity %
        - wind_speed: float - Wind speed in mph
        - wind_direction: int - Wind direction in degrees
        - timestamp: str - ISO 8601 timestamp
    
    Raises:
        LocationNotFoundError: If location cannot be resolved
        APIError: If weather API call fails
    """
    loc = resolve_location(location)
    
    try:
        response = requests.get(
            WEATHER_URL,
            params={
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,weather_code",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "auto"
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        current = data.get("current", {})
        weather_code = current.get("weather_code", 0)
        
        return {
            "location": loc["name"],
            "temperature": current.get("temperature_2m"),
            "conditions": _weather_code_to_description(weather_code),
            "humidity": current.get("relative_humidity_2m"),
            "wind_speed": current.get("wind_speed_10m"),
            "wind_direction": current.get("wind_direction_10m"),
            "timestamp": current.get("time")
        }
    
    except requests.RequestException as e:
        logger.error(f"Weather API error for {location}: {e}")
        raise APIError(f"Failed to fetch current weather: {str(e)}")


def get_forecast(location: str, days: int = 7) -> Dict[str, Any]:
    """Get multi-day weather forecast.
    
    Args:
        location: City name, "City, State", or "lat,lon"
        days: Number of days to forecast (1-16, default 7)
    
    Returns:
        Dict with keys:
        - location: str - Resolved location name
        - days: int - Number of forecast days
        - forecast: List[Dict] - Daily forecasts, each with:
            - date: str - YYYY-MM-DD
            - temp_max: float - High temp in °F
            - temp_min: float - Low temp in °F
            - precipitation_chance: int - Precipitation probability %
            - conditions: str - Weather description
    
    Raises:
        LocationNotFoundError: If location cannot be resolved
        APIError: If weather API call fails
    """
    loc = resolve_location(location)
    days = max(1, min(days, 16))  # Clamp to API limits
    
    try:
        response = requests.get(
            WEATHER_URL,
            params={
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                "temperature_unit": "fahrenheit",
                "timezone": "auto",
                "forecast_days": days
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        temp_max = daily.get("temperature_2m_max", [])
        temp_min = daily.get("temperature_2m_min", [])
        precip_prob = daily.get("precipitation_probability_max", [])
        weather_codes = daily.get("weather_code", [])
        
        forecast_list = []
        for i in range(len(dates)):
            forecast_list.append({
                "date": dates[i],
                "temp_max": temp_max[i] if i < len(temp_max) else None,
                "temp_min": temp_min[i] if i < len(temp_min) else None,
                "precipitation_chance": precip_prob[i] if i < len(precip_prob) else 0,
                "conditions": _weather_code_to_description(weather_codes[i]) if i < len(weather_codes) else "Unknown"
            })
        
        return {
            "location": loc["name"],
            "days": len(forecast_list),
            "forecast": forecast_list
        }
    
    except requests.RequestException as e:
        logger.error(f"Forecast API error for {location}: {e}")
        raise APIError(f"Failed to fetch forecast: {str(e)}")


def predict_umbrella_needed(location: str, target_date: Optional[str] = None) -> Dict[str, Any]:
    """Predict if an umbrella is needed based on precipitation forecast.
    
    Decision threshold: Recommend umbrella if precipitation chance > 40%.
    
    Args:
        location: City name, "City, State", or "lat,lon"
        target_date: Optional date string (YYYY-MM-DD). If None, uses tomorrow.
    
    Returns:
        Dict with keys:
        - location: str - Resolved location name
        - date: str - Target date (YYYY-MM-DD)
        - umbrella_needed: bool - Recommendation
        - precipitation_chance: int - Precipitation probability %
        - confidence: str - "high" (>70%), "medium" (40-70%), "low" (<40%)
        - reasoning: str - Explanation of the recommendation
    
    Raises:
        LocationNotFoundError: If location cannot be resolved
        APIError: If weather API call fails
    """
    # Default to tomorrow if no date specified
    if target_date is None:
        target_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Get forecast
    forecast_data = get_forecast(location, days=7)
    
    # Find the target date in forecast
    target_forecast = None
    for day in forecast_data["forecast"]:
        if day["date"] == target_date:
            target_forecast = day
            break
    
    if target_forecast is None:
        raise APIError(f"Forecast not available for date: {target_date}")
    
    precip_chance = target_forecast["precipitation_chance"] or 0
    umbrella_needed = precip_chance > 40
    
    # Determine confidence level
    if precip_chance > 70:
        confidence = "high"
        reasoning = f"High precipitation chance ({precip_chance}%) - definitely bring an umbrella."
    elif precip_chance > 40:
        confidence = "medium"
        reasoning = f"Moderate precipitation chance ({precip_chance}%) - umbrella recommended."
    else:
        confidence = "low"
        reasoning = f"Low precipitation chance ({precip_chance}%) - umbrella likely not needed."
    
    return {
        "location": forecast_data["location"],
        "date": target_date,
        "umbrella_needed": umbrella_needed,
        "precipitation_chance": precip_chance,
        "confidence": confidence,
        "reasoning": reasoning,
        "conditions": target_forecast["conditions"],
        "temp_high": target_forecast["temp_max"],
        "temp_low": target_forecast["temp_min"]
    }


def _weather_code_to_description(code: int) -> str:
    """Convert WMO weather code to human-readable description.
    
    WMO Weather interpretation codes (WW): https://open-meteo.com/en/docs
    """
    code_map = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Foggy",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail"
    }
    return code_map.get(code, f"Unknown (code {code})")
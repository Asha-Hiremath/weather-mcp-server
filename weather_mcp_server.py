"""Weather MCP Server - FastMCP server exposing weather forecast tools.

This MCP server provides three main tools for weather queries:
1. get_current_weather - Current conditions
2. get_forecast - Multi-day forecast
3. predict_umbrella_needed - Recommendation based on precipitation

Built with FastMCP for Databricks Agent Bricks integration.
Backed by Open-Meteo API (no API key required).
"""

import logging
from typing import Optional
from fastmcp import FastMCP

# Import broker functions
from weather_broker import (
    get_current_weather as broker_get_current_weather,
    get_forecast as broker_get_forecast,
    predict_umbrella_needed as broker_predict_umbrella,
    LocationNotFoundError,
    APIError
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("Weather Forecast Server")


@mcp.tool()
def get_current_weather(location: str) -> dict:
    """Get current weather conditions for a location.
    
    Returns real-time temperature, humidity, wind speed, and conditions.
    
    Args:
        location: City name (e.g., "Chicago"), city with state ("Austin, TX"),
                 or lat/lon coordinates ("41.88,-87.63")
    
    Returns:
        Dict containing:
        - location: str - Resolved location name
        - temperature: float - Current temperature in °F
        - conditions: str - Weather description (e.g., "Partly cloudy")
        - humidity: int - Relative humidity percentage
        - wind_speed: float - Wind speed in mph
        - wind_direction: int - Wind direction in degrees
        - timestamp: str - ISO 8601 timestamp of observation
    
    Examples:
        >>> get_current_weather("Chicago")
        {'location': 'Chicago', 'temperature': 72.5, 'conditions': 'Partly cloudy', ...}
        
        >>> get_current_weather("Austin, TX")
        {'location': 'Austin', 'temperature': 85.2, 'conditions': 'Clear sky', ...}
    """
    try:
        logger.info(f"Fetching current weather for: {location}")
        result = broker_get_current_weather(location)
        logger.info(f"Successfully fetched current weather for {result['location']}")
        return result
    
    except LocationNotFoundError as e:
        logger.warning(f"Location not found: {location}")
        return {
            "error": "location_not_found",
            "message": str(e),
            "suggestion": "Try a major city name, or provide coordinates as 'lat,lon'"
        }
    
    except APIError as e:
        logger.error(f"Weather API error: {e}")
        return {
            "error": "api_error",
            "message": str(e),
            "suggestion": "The weather service may be temporarily unavailable. Try again in a moment."
        }
    
    except Exception as e:
        logger.exception(f"Unexpected error fetching weather for {location}")
        return {
            "error": "unexpected_error",
            "message": str(e)
        }


@mcp.tool()
def get_forecast(location: str, days: int = 7) -> dict:
    """Get multi-day weather forecast for a location.
    
    Returns daily high/low temperatures, precipitation chances, and conditions.
    
    Args:
        location: City name (e.g., "Chicago"), city with state ("Austin, TX"),
                 or lat/lon coordinates ("41.88,-87.63")
        days: Number of days to forecast (1-16, default 7)
    
    Returns:
        Dict containing:
        - location: str - Resolved location name
        - days: int - Number of forecast days returned
        - forecast: List[Dict] - Daily forecasts, each with:
            - date: str - Date in YYYY-MM-DD format
            - temp_max: float - High temperature in °F
            - temp_min: float - Low temperature in °F
            - precipitation_chance: int - Precipitation probability (0-100%)
            - conditions: str - Weather description
    
    Examples:
        >>> get_forecast("Seattle", days=3)
        {
            'location': 'Seattle',
            'days': 3,
            'forecast': [
                {'date': '2026-08-09', 'temp_max': 75, 'temp_min': 58, 'precipitation_chance': 20, ...},
                {'date': '2026-08-10', 'temp_max': 73, 'temp_min': 57, 'precipitation_chance': 60, ...},
                {'date': '2026-08-11', 'temp_max': 70, 'temp_min': 55, 'precipitation_chance': 80, ...}
            ]
        }
    """
    try:
        logger.info(f"Fetching {days}-day forecast for: {location}")
        result = broker_get_forecast(location, days)
        logger.info(f"Successfully fetched forecast for {result['location']}")
        return result
    
    except LocationNotFoundError as e:
        logger.warning(f"Location not found: {location}")
        return {
            "error": "location_not_found",
            "message": str(e),
            "suggestion": "Try a major city name, or provide coordinates as 'lat,lon'"
        }
    
    except APIError as e:
        logger.error(f"Forecast API error: {e}")
        return {
            "error": "api_error",
            "message": str(e),
            "suggestion": "The weather service may be temporarily unavailable. Try again in a moment."
        }
    
    except Exception as e:
        logger.exception(f"Unexpected error fetching forecast for {location}")
        return {
            "error": "unexpected_error",
            "message": str(e)
        }


@mcp.tool()
def predict_umbrella_needed(location: str, date: Optional[str] = None) -> dict:
    """Predict if an umbrella is needed based on precipitation forecast.
    
    Makes a recommendation using a 40% precipitation threshold:
    - Precipitation chance > 40%: Umbrella recommended
    - Precipitation chance <= 40%: Umbrella likely not needed
    
    Confidence levels:
    - High (>70%): Very likely to rain
    - Medium (40-70%): Moderate chance of rain
    - Low (<40%): Unlikely to rain
    
    Args:
        location: City name (e.g., "Chicago"), city with state ("Austin, TX"),
                 or lat/lon coordinates ("41.88,-87.63")
        date: Target date in YYYY-MM-DD format. If None, defaults to tomorrow.
    
    Returns:
        Dict containing:
        - location: str - Resolved location name
        - date: str - Target date (YYYY-MM-DD)
        - umbrella_needed: bool - Recommendation (True = bring umbrella)
        - precipitation_chance: int - Precipitation probability (0-100%)
        - confidence: str - "high", "medium", or "low"
        - reasoning: str - Explanation of the recommendation
        - conditions: str - Weather description
        - temp_high: float - High temperature in °F
        - temp_low: float - Low temperature in °F
    
    Examples:
        >>> predict_umbrella_needed("Miami")
        {
            'location': 'Miami',
            'date': '2026-08-10',
            'umbrella_needed': True,
            'precipitation_chance': 75,
            'confidence': 'high',
            'reasoning': 'High precipitation chance (75%) - definitely bring an umbrella.',
            'conditions': 'Moderate rain',
            'temp_high': 88,
            'temp_low': 78
        }
        
        >>> predict_umbrella_needed("Phoenix", date="2026-08-15")
        {
            'location': 'Phoenix',
            'date': '2026-08-15',
            'umbrella_needed': False,
            'precipitation_chance': 10,
            'confidence': 'low',
            'reasoning': 'Low precipitation chance (10%) - umbrella likely not needed.',
            ...
        }
    """
    try:
        logger.info(f"Predicting umbrella need for: {location} on {date or 'tomorrow'}")
        result = broker_predict_umbrella(location, date)
        logger.info(f"Prediction for {result['location']}: {'Yes' if result['umbrella_needed'] else 'No'}")
        return result
    
    except LocationNotFoundError as e:
        logger.warning(f"Location not found: {location}")
        return {
            "error": "location_not_found",
            "message": str(e),
            "suggestion": "Try a major city name, or provide coordinates as 'lat,lon'"
        }
    
    except APIError as e:
        logger.error(f"Prediction API error: {e}")
        return {
            "error": "api_error",
            "message": str(e),
            "suggestion": "The forecast may not be available for that date. Try a date within the next 7 days."
        }
    
    except Exception as e:
        logger.exception(f"Unexpected error predicting umbrella need for {location}")
        return {
            "error": "unexpected_error",
            "message": str(e)
        }


if __name__ == "__main__":
    import os
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from starlette.responses import JSONResponse
    from starlette.middleware.cors import CORSMiddleware
    
    # Get port from environment (Render uses PORT env var)
    port = int(os.environ.get("PORT", 8000))
    
    logger.info(f"Starting Weather MCP Server on port {port}...")
    
    # Create a tools endpoint that returns the tool list in JSON
    async def tools_endpoint(request):
        """Returns the list of available MCP tools in JSON format"""
        tools = [
            {
                "name": "get_current_weather",
                "description": "Get the current weather for a specific location. Returns temperature, conditions, humidity, and wind speed.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name, optionally with state/country (e.g., 'Seattle', 'London, UK', 'Tokyo, Japan')"
                        }
                    },
                    "required": ["location"]
                }
            },
            {
                "name": "get_forecast",
                "description": "Get weather forecast for the next few days for a specific location. Returns multi-day forecast with temperatures and conditions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name, optionally with state/country"
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days to forecast (1-7)",
                            "default": 3
                        }
                    },
                    "required": ["location"]
                }
            },
            {
                "name": "predict_umbrella_needed",
                "description": "Predict if an umbrella will be needed based on weather forecast. Checks precipitation probability and conditions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name, optionally with state/country"
                        },
                        "date": {
                            "type": "string",
                            "description": "Date to check (YYYY-MM-DD format, defaults to today if not provided)"
                        }
                    },
                    "required": ["location"]
                }
            }
        ]
        
        return JSONResponse({
            "tools": tools,
            "version": "1.0",
            "capabilities": ["weather_current", "weather_forecast", "predictions"]
        })
    
    # Health check endpoint
    async def health_check(request):
        return JSONResponse({"status": "ok", "service": "weather-mcp-server"})
    
    # Create Starlette app with routes
    app = Starlette(
        routes=[
            Route("/health", health_check, methods=["GET"]),
            Route("/tools", tools_endpoint, methods=["GET", "POST", "OPTIONS"]),
            Route("/", health_check, methods=["GET"]),
        ]
    )
    
    # Add CORS middleware to allow requests from AI Gateway
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Run the server
    logger.info(f"Server endpoints:")
    logger.info(f"  Health: http://0.0.0.0:{port}/health")
    logger.info(f"  Tools:  http://0.0.0.0:{port}/tools")
    uvicorn.run(app, host="0.0.0.0", port=port)
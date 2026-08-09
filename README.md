# Weather Forecast MCP Server + Agent Bricks Agent

**Homework Submission for Databricks Lakebase App Day 3 Bootcamp**  
**Date:** 2026-08-08  
**Author:** Asha

## Overview

This project implements a weather-prediction MCP (Model Context Protocol) server that exposes weather forecast tools backed by the Open-Meteo API, along with a Databricks Agent Bricks agent that uses these tools to answer natural-language weather questions and make predictions.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Query                               │
│           "Will it rain in Chicago tomorrow?"               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      v
┌─────────────────────────────────────────────────────────────┐
│              Agent Bricks Agent                             │
│  - Interprets user intent                                   │
│  - Decides which tools to call                              │
│  - Formats final answer                                     │
└─────────────────────┬───────────────────────────────────────┘
                      │ MCP Protocol (SSE)
                      v
┌─────────────────────────────────────────────────────────────┐
│         Weather MCP Server (FastMCP)                        │
│  Endpoint: /sse                                             │
│  Tools:                                                     │
│    - get_current_weather()                                  │
│    - get_forecast()                                         │
│    - predict_umbrella_needed()                              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      v
┌─────────────────────────────────────────────────────────────┐
│           Weather Broker (weather_broker.py)                │
│  - HTTP requests to Open-Meteo API                          │
│  - Geocoding (city → lat/lon)                               │
│  - Response parsing and error handling                      │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTPS
                      v
┌─────────────────────────────────────────────────────────────┐
│              Open-Meteo API (Free)                          │
│  https://api.open-meteo.com                                 │
│  - No API key required                                      │
│  - ~10,000 calls/day                                        │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. MCP Server (`weather_mcp_server.py`)

FastMCP-based server exposing three weather tools:

#### Tool 1: `get_current_weather(location: str)`
- Returns real-time weather conditions for a location
- **Input**: City name ("Chicago"), "City, State" ("Austin, TX"), or "lat,lon" coordinates
- **Output**: Temperature (°F), conditions, humidity, wind speed/direction, timestamp

#### Tool 2: `get_forecast(location: str, days: int = 7)`
- Returns multi-day weather forecast (1-16 days)
- **Input**: Location + number of days
- **Output**: Daily high/low temps, precipitation chance, conditions

#### Tool 3: `predict_umbrella_needed(location: str, date: Optional[str] = None)`
- Prediction/recommendation tool with threshold logic
- **Logic**: Recommends umbrella if precipitation chance > 40%
- **Input**: Location + optional date (defaults to tomorrow)
- **Output**: Boolean recommendation + confidence level + reasoning

### 2. Weather Broker (`weather_broker.py`)

Adapter module that handles all API interactions:
- `resolve_location()` - Geocoding via Open-Meteo Geocoding API
- `get_current_weather()` - Fetches current conditions
- `get_forecast()` - Fetches daily forecast
- `predict_umbrella_needed()` - Applies 40% threshold logic
- Custom exceptions: `LocationNotFoundError`, `APIError`

### 3. Configuration

**app.yaml**
```yaml
command:
  - "python"
  - "weather_mcp_server.py"

env:
  - name: LOG_LEVEL
    value: INFO
```

**requirements.txt**
- `fastmcp>=0.1.0` - MCP server framework
- `requests>=2.31.0` - HTTP client
- `uvicorn>=0.27.0` - ASGI server

## Weather API Choice: Open-Meteo

**Why Open-Meteo?**
- ✅ No signup or API key required
- ✅ ~10,000 calls/day (non-commercial)
- ✅ Current weather, forecast, and historical data
- ✅ Global coverage with geocoding built-in
- ✅ Free tier sufficient for development and testing

**APIs Used:**
- Geocoding: `https://geocoding-api.open-meteo.com/v1/search`
- Weather: `https://api.open-meteo.com/v1/forecast`

## Deployment

### MCP Server Deployment

**Databricks App URL:**  
https://weather-mcp-server-1803245401151092.aws.databricksapps.com

**MCP SSE Endpoint:**  
https://weather-mcp-server-1803245401151092.aws.databricksapps.com/sse

**Source Code Location:**  
`/Workspace/Users/asha.acps@gmail.com/weather-mcp-server/`

### Agent Bricks Agent Setup

#### Step 1: Register MCP Server as External Tool

1. Navigate to **Agent Bricks** in your Databricks workspace
2. Go to **External Tools** → **Add MCP Server**
3. Configure:
   - **Name**: Weather Forecast MCP
   - **Endpoint URL**: `https://weather-mcp-server-1803245401151092.aws.databricksapps.com/sse`
   - **Transport**: SSE (Server-Sent Events)
   - **Authentication**: None (public endpoint)

#### Step 2: Create Agent

1. Create new Agent Bricks agent
2. **Name**: Weather Assistant
3. **System Prompt** (see below)
4. **External Tools**: Select "Weather Forecast MCP"

#### Recommended System Prompt

```
You are a helpful weather assistant that provides accurate, real-time weather information and predictions.

Your capabilities:
- Get current weather conditions for any location
- Provide multi-day forecasts (up to 16 days)
- Make umbrella recommendations based on precipitation likelihood

Guidelines:
1. Always use the weather tools to get current data - never guess or use outdated information
2. For location queries, accept city names ("Seattle"), city+state ("Austin, TX"), or coordinates
3. If a location cannot be resolved, ask the user to clarify or provide a major nearby city
4. When making predictions, explain your reasoning (e.g., "40% precipitation chance, so umbrella recommended")
5. If the API call fails, tell the user there was an issue fetching weather data and suggest trying again
6. For date-specific questions, use get_forecast() and find the matching date
7. Be conversational but concise - users want quick, actionable weather information

Error handling:
- Bad location → Ask user to clarify or suggest a major city
- API outage → Acknowledge the issue, don't make up data
- Future date out of range → Explain forecast limit is 16 days

Examples:
- "Will it rain in Chicago tomorrow?" → Call get_forecast("Chicago", days=2) and check tomorrow's precipitation
- "Should I bring a jacket to Austin this weekend?" → Call get_forecast("Austin, TX", days=7) and check weekend temps
- "What's the weather like in Miami right now?" → Call get_current_weather("Miami")
```

## Error Handling

### Clean Error Returns

All tool functions return structured error dicts instead of raising exceptions:

```python
{
    "error": "location_not_found" | "api_error" | "unexpected_error",
    "message": "Location not found: Xyzabc",
    "suggestion": "Try a major city name, or provide coordinates as 'lat,lon'"
}
```

### Location Resolution

1. Try exact match in hardcoded city cache (Chicago, Austin, NYC, etc.)
2. Try first-word match ("Austin, TX" → "austin")
3. Call Open-Meteo Geocoding API
4. Return `LocationNotFoundError` if all fail

## Testing & Demonstration

### Test Queries

**Query 1: Current Weather**
```
User: "What's the weather like in Seattle right now?"

Agent:
- Calls: get_current_weather("Seattle")
- Response: "In Seattle, it's currently 58°F with partly cloudy skies. 
            Humidity is 75%, and winds are light at 8 mph from the northwest."
```

**Query 2: Forecast Query**
```
User: "Will it rain in Austin this weekend?"

Agent:
- Calls: get_forecast("Austin, TX", days=7)
- Filters to Saturday/Sunday
- Response: "This weekend in Austin: Saturday will be sunny with a high of 92°F 
            and only 10% chance of rain. Sunday looks similar at 90°F with 15% 
            chance of rain. You should have great weather!"
```

**Query 3: Prediction/Recommendation**
```
User: "Should I bring an umbrella to Miami tomorrow?"

Agent:
- Calls: predict_umbrella_needed("Miami")
- Response: "Yes, you should bring an umbrella to Miami tomorrow. There's a 65% 
            chance of rain (moderate confidence), so it's likely you'll need it. 
            Expect a high of 86°F and low of 77°F with moderate rain."
```

## Security & Best Practices

✅ **No secrets in code** - Open-Meteo requires no API key  
✅ **Error handling** - Clean error messages, no stack traces exposed  
✅ **Separation of concerns** - MCP tools are thin, broker handles HTTP  
✅ **Type hints** - All functions use Python type annotations  
✅ **Comprehensive docstrings** - Args, Returns, Examples for every tool  
✅ **Logging** - Structured logging for debugging and monitoring  

## Local Development

### Prerequisites
- Python 3.11+
- Databricks CLI configured

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run MCP server locally
python weather_mcp_server.py

# Server runs on http://0.0.0.0:8000
# SSE endpoint: http://0.0.0.0:8000/sse
```

### Deploy to Databricks

```bash
# Sync local changes to workspace
databricks sync --watch . /Workspace/Users/<your-email>/weather-mcp-server

# Deploy app
databricks apps deploy weather-mcp-server \
  --source-code-path /Workspace/Users/<your-email>/weather-mcp-server

# Check status
databricks apps get weather-mcp-server

# View logs
databricks apps logs weather-mcp-server --tail-lines 100
```

## Submission

**Repository:** [Your GitHub repo link]  
**MCP Server App:** https://weather-mcp-server-1803245401151092.aws.databricksapps.com/sse  
**Agent Bricks Agent:** [Your Agent Bricks agent link]

### Files Included

```
weather-mcp-server/
├── README.md                    # This file
├── app.yaml                     # Databricks App configuration
├── requirements.txt             # Python dependencies
├── weather_mcp_server.py        # MCP server with 3 tools
└── weather_broker.py            # Weather API adapter/broker
```

## What Makes This "Good"

✅ **Clear tool docstrings** - Args/Returns/Examples matching the reference pattern  
✅ **Error handling** - Bad locations return clean errors, agent can react sensibly  
✅ **Prediction logic** - Umbrella tool applies 40% threshold with reasoning  
✅ **No secrets committed** - No API keys required or hardcoded  
✅ **Specific system prompt** - Agent won't hallucinate weather data  
✅ **Separate broker module** - All HTTP/parsing logic isolated from MCP tools  
✅ **Deployed and running** - Live Databricks App ready for Agent Bricks integration  

## Future Enhancements (Stretch Goals)

- [ ] Severe weather alerts (NWS API integration)
- [ ] Historical weather lookup
- [ ] Multi-city comparison tool
- [ ] Dashboard app showing agent query history
- [ ] Unit tests with mocked API responses
- [ ] Rate limiting and caching

## References

- [Open-Meteo API Documentation](https://open-meteo.com/en/docs)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [Databricks Apps Documentation](https://docs.databricks.com/en/apps/index.html)
- [Agent Bricks Documentation](https://docs.databricks.com/en/generative-ai/agent-framework/)

---

**License:** MIT  
**Contact:** asha.acps@gmail.com
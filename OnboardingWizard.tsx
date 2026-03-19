# GridIQ Frontend — Environment Variables
# Copy to .env.local and adjust for your environment

# API base URL — when using vite dev server proxy, leave empty ("")
# In production, set to your deployed API URL
VITE_API_URL=http://localhost:8000/api/v1

# WebSocket URL
VITE_WS_URL=ws://localhost:8000/api/v1

# Mapbox token (for geographic grid map — get free at mapbox.com)
VITE_MAPBOX_TOKEN=pk.your_mapbox_token_here

# Feature flags
VITE_ENABLE_DARK_MODE=true
VITE_ENABLE_MAPBOX=false

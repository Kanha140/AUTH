import os
from dotenv import load_dotenv

load_dotenv()

# Discord Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_BOT_TOKEN_HERE")
MAIN_OWNER_ID = int(os.getenv("OWNER_ID", "1378068938847424522"))
OWNER_ID = MAIN_OWNER_ID
GUILD_ID = int(os.getenv("GUILD_ID", "1564210205988753551"))

# Discord Webhook Logs Configuration
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# Auth API Server Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("PORT", os.getenv("API_PORT", "5000")))

# Database Configuration
DB_PATH = os.path.join(os.path.dirname(__file__), "auth_bot.db")

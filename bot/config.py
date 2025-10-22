import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram API credentials - you need to get these from https://my.telegram.org
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# Session name for the userbot
SESSION_NAME = "userbot"

# Sudo users (Telegram user IDs who can control the bot)
# Add your own Telegram user ID here
SUDO_USERS = set(map(int, os.getenv("SUDO_USERS", "").split(","))) if os.getenv("SUDO_USERS") else set()

# Delay range for sticker sending (in seconds)
MIN_DELAY = 5
MAX_DELAY = 20
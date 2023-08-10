import os
from dotenv import load_dotenv

load_dotenv()
DISCORD_API_SECRET = os.getenv("DISCORD_API_TOKEN")
USERS_PATH = os.getenv("USERS_PATH")

import os
from dotenv import load_dotenv

load_dotenv()

# L.U.N.A. configuration

LUNA_NAME = "Luna"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

# Email
EMAIL_ADDRESS = os.getenv("GMAIL_USER")
EMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")  # Use App Password, not regular password

# Database
DATABASE_PATH = "data/luna.db"
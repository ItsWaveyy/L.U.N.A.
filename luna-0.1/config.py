import os
from dotenv import load_dotenv

load_dotenv()

LUNA_MODE = os.getenv(
    "LUNA_MODE",
    "auto",
).lower()

if LUNA_MODE not in {
    "auto",
    "online",
    "offline",
}:
    LUNA_MODE = "auto"

# L.U.N.A. configuration

LUNA_NAME = "Luna"

# AI Providers
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Local AI
OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL", "http://127.0.0.1:11434"
)

# LiveKit
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

# Email
EMAIL_ADDRESS = os.getenv("GMAIL_USER")
EMAIL_PASSWORD = os.getenv(
    "GMAIL_APP_PASSWORD"
)  # Use App Password, not regular password

# Database
DATABASE_PATH = "data/luna.db"
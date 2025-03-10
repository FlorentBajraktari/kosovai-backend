import os
from dotenv import load_dotenv

# Ngarko variablat nga .env
load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY nuk është vendosur në .env")

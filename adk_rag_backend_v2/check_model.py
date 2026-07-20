import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY_1") or os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: Could not find GEMINI_API_KEY in .env")
    exit(1)

client = genai.Client(api_key=api_key)

print("Available Models:")
print("-" * 40)

try:
    for model in client.models.list():
        # Just print the raw name directly
        print(f" - {model.name}")
except Exception as e:
    print(f"Failed to list models: {e}")
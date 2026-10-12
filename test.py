from google import genai
from dotenv import load_dotenv

load_dotenv()

MODEL = "gemini-3.5-flash-lite"
PROMPT = "Become a customer service that classify the needs of {user}"

client = genai.Client()


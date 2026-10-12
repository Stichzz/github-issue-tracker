import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ServerError

load_dotenv()

client = genai.Client()

# List of models in order of preference
MODELS = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
PROMPT = "Create a concise, step-by-step roadmap for mastering AI automation engineering to be job ready."

config = types.GenerateContentConfig(
    max_output_tokens=1500,
)

response_stream = None

for model_name in MODELS:
    print(f"Connecting to {model_name}...")
    try:
        response_stream = client.models.generate_content_stream(
            model=model_name,
            contents=PROMPT,
            config=config,
        )
        # Test if the stream responds without raising a 503
        first_chunk = next(response_stream, None)
        if first_chunk:
            print(f"Connected successfully to {model_name}!\n" + "-" * 40)
            if first_chunk.text:
                print(first_chunk.text, end="", flush=True)
            break
    except ServerError as e:
        print(f"⚠️ {model_name} is overloaded (503). Trying fallback...")
        continue
    except Exception as e:
        print(f"⚠️ Error with {model_name}: {e}")
        continue

# Stream the remainder of the response
if response_stream:
    for chunk in response_stream:
        if chunk.text:
            print(chunk.text, end="", flush=True)
    print("\n" + "-" * 40 + "\nDone!")
else:
    print(
        "❌ All model endpoints are currently experiencing high demand. Please try again shortly."
    )

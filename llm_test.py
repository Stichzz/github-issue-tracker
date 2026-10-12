from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ServerError
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

load_dotenv()

MODEL = "gemini-3.5-flash-lite"
TIMEOUT_MS = 30_000

PROMPT = """You triage GitHub issues for a software project.
Priority: P0 = security problem, data loss or outage; P1 = crash or a main feature is broken;
P2 = a bug that has a workaround; P3 = minor, cosmetic or nice-to-have.
Category: Bug, Feature (a new capability), Question, or Docs (documentation or typos).

Issue title: {title}"""


class Triage(BaseModel):
    priority: Literal["P0", "P1", "P2", "P3"]
    category: Literal["Bug", "Feature", "Question", "Docs"]


client = genai.Client(http_options=types.HttpOptions(timeout=TIMEOUT_MS))

@retry(
        retry=retry_if_exception_type(ServerError),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, max=30),
        reraise=True
)
def triage_with_llm(title):
    response = client.models.generate_content(
        model=MODEL,
        contents=PROMPT.format(title=title),
        config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=Triage,
        ),
    )

    return response.parsed.model_dump()


titles = (
    "App crashes when saving",
    "Typo in the address form",
    "Data loss when saving twice",
)
for title in titles:
    try:
        print(title, "->", triage_with_llm(title))
    except ServerError as e:
        print(title, "-> skipped: ", e.message)

# GitHub Issue Tracker & Auto-Triage

Syncs a GitHub user's repositories and issues into SQLite, then uses an LLM
(Gemini) to classify each new issue by type and priority.

## Features
- Paginated GitHub REST API sync, safe to re-run (inserts new, updates changed, skips unchanged)
- SQLite storage with foreign keys and one transaction per sync step
- LLM triage with structured output (Pydantic schema), so the model must return valid fields
- Retries with exponential backoff; if the LLM is overloaded the issue is skipped and retried on the next run
- Run reports for each stage

## Tech
Python, requests, SQLite, Pydantic, google-genai (Gemini), tenacity, python-dotenv

## How it works
GitHub API → `sync_repositories` / `sync_issues` → SQLite → `triage_issues` → Gemini → triage saved

## Setup (Windows PowerShell)
```powershell
git clone https://github.com/Stichzz/github-issue-tracker.git
cd github-issue-tracker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```
1. Get a free Gemini API key at [aistudio.google.com](https://aistudio.google.com).
2. Copy `.env.example` to `.env` and add your key as `GEMINI_API_KEY`.
3. In `issue_tracker.py`, change `USERNAME` to your GitHub username.

## Run
```powershell
python issue_tracker.py
```

## Design decisions
- Functions raise errors and the caller decides what to do, so one bad issue never stops the run.
- Failed triage leaves `triaged_at` empty, so the next run retries it automatically.

## Limitations / next steps
- Runs on demand (polling), not on events
- No tests yet
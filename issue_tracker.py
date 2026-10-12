import sqlite3
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Literal

import requests
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
TIMEOUT_MS = 20_000
PROMPT = """You triage GitHub issues for a software project.
Priority: P0 = security problem, data loss or outage; P1 = crash or a main feature is broken;
P2 = a bug that has a workaround; P3 = minor, cosmetic or nice-to-have.
Category: Bug, Feature (a new capability), Question, or Docs (documentation or typos).

Issue title: {title}"""

DB_NAME = "github.db"

USERNAME = "Stichzz"
API_URL = "https://api.github.com"
REPOS_URL = f"{API_URL}/users/{USERNAME}/repos"


REPO_FIELDS = (
    "id",
    "name",
    "full_name",
    "html_url",
    "description",
    "language",
    "stargazers_count",
    "forks_count",
    "open_issues_count",
    "created_at",
    "updated_at",
)


class Triage(BaseModel):
    priority: Literal["P0", "P1", "P2", "P3"]
    category: Literal["Bug", "Feature", "Question", "Docs"]

client = genai.Client(http_options=types.HttpOptions(timeout=TIMEOUT_MS))

@contextmanager
def connect_database():
    connection = sqlite3.connect(DB_NAME)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def init_db():
    query_repositories = """
    CREATE TABLE IF NOT EXISTS repositories (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        full_name TEXT NOT NULL,
        html_url TEXT,
        description TEXT,
        language TEXT,
        stargazers_count INTEGER,
        forks_count INTEGER,
        open_issues_count INTEGER,
        created_at TEXT,
        updated_at TEXT
    );
    """

    query_issues = """
    CREATE TABLE IF NOT EXISTS issues (
        id INTEGER PRIMARY KEY,
        repository_id INTEGER NOT NULL,
        issue_number INTEGER NOT NULL,
        title TEXT NOT NULL,
        state TEXT NOT NULL,
        author TEXT NOT NULL,
        url TEXT,
        priority TEXT DEFAULT 'P3',
        category TEXT DEFAULT 'Uncategorized',
        triaged_at TEXT,
        FOREIGN KEY (repository_id) REFERENCES repositories (id)
    );
    """

    with connect_database() as connection:
        connection.execute(query_repositories)
        connection.execute(query_issues)

def get_data():
    params = {"per_page": 100}

    try:
        data = fetch_all_pages(REPOS_URL, params)

        repositories = {
            repo["id"]: {key: repo[key] for key in REPO_FIELDS} for repo in data
        }

        return True, repositories, "Data requested successfully"

    except requests.exceptions.Timeout:
        return False, None, "Requests timed out"

    except requests.exceptions.ConnectionError:
        return False, None, "Could not connect to Github"

    except requests.exceptions.HTTPError as err:
        return False, None, f"HTTP error: {err.response.status_code}"

    except requests.exceptions.JSONDecodeError:
        return False, None, "Github returned invalid JSON"

    except requests.exceptions.RequestException as err:
        return False, None, f"Request Failed: {err}"


def get_repository(connection, repository_id):
    query = """
        SELECT *
        FROM repositories
        WHERE id = ?
    """
    cursor = connection.execute(query, (repository_id,))
    return cursor.fetchone()

def save_repository(connection, repository: dict):
    query = """
        INSERT INTO repositories (
            id, 
            name, 
            full_name, 
            html_url, 
            description, 
            language, 
            stargazers_count, 
            forks_count, 
            open_issues_count, 
            created_at, 
            updated_at
        )
        VALUES (
            :id, 
            :name, 
            :full_name, 
            :html_url, 
            :description, 
            :language, 
            :stargazers_count, 
            :forks_count, 
            :open_issues_count, 
            :created_at, 
            :updated_at
            );
    """

    connection.execute(query, repository)

def update_repository(connection, repository: dict):
    query = """
        UPDATE repositories
        SET 
            name = :name,
            full_name = :full_name,
            html_url = :html_url,
            description = :description,
            language = :language,
            stargazers_count = :stargazers_count,
            forks_count = :forks_count,
            open_issues_count = :open_issues_count,
            created_at = :created_at,
            updated_at = :updated_at
        WHERE id = :id
    """
    connection.execute(query, repository)

def sync_repository(connection, repository):
    existing = get_repository(connection, repository["id"])

    if existing is None:
        save_repository(connection, repository)
        return "inserted", None


    old = dict(existing)
    changed = {
        key: {"old": old[key], "new": new}
        for key, new in repository.items()
        if old[key] != new
    }

    if not changed:
        return "unchanged", None
    
    update_repository(connection, repository)
    return "updated", changed

def sync_repositories(repositories):
    changelog = {}
    report = Counter()

    with connect_database() as connection:
        for repository in repositories.values():
            result, changed = sync_repository(connection, repository)
            report[result] += 1

            if result == "updated":
                changelog[repository["id"]] = (repository["name"], changed)
            elif result == "inserted":
                changelog[repository["id"]] = (repository["name"], result)

    return changelog, report

def fetch_all_pages(url, params=None):
    items = []
    while url:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        items.extend(response.json())
        url = response.links.get("next", {}).get("url")
        params = None
    return items

def get_issues(full_name, repository_id):
    url = f"{API_URL}/repos/{full_name}/issues"
    params = {"state": "all", "per_page": 100}
    raw_issues = fetch_all_pages(url, params)

    return [
        {
            "id": issue["id"],
            "repository_id": repository_id,
            "issue_number": issue["number"],
            "title": issue["title"],
            "state": issue["state"],
            "author": issue["user"]["login"],
            "url": issue["html_url"],
        }
        for issue in raw_issues
        if "pull_request" not in issue
    ]


def get_issue(connection, issue_id):
    cursor = connection.execute("SELECT * FROM issues WHERE id = ?", (issue_id,))
    return cursor.fetchone()


def save_issue(connection, issue):
    query = """
        INSERT INTO issues (
            id,
            repository_id,
            issue_number,
            title,
            state,
            author,
            url
        )
        VALUES (
        :id,
        :repository_id,
        :issue_number,
        :title,
        :state,
        :author,
        :url
        )
"""

    connection.execute(query, issue)


def update_issue(connection, issue):
    query = """
        UPDATE issues
        SET
            repository_id = :repository_id,
            issue_number = :issue_number,
            title = :title,
            state = :state,
            author = :author,
            url = :url
        WHERE id = :id
    """
    connection.execute(query, issue)


def sync_issue(connection, issue):
    existing = get_issue(connection, issue["id"])

    if existing is None:
        save_issue(connection, issue)
        return "added"

    if any(existing[key] != value for key, value in issue.items()):
        update_issue(connection, issue)
        return "updated"

    return "unchanged"


def sync_issues(repositories):
    issue_changelog = {}
    issue_report = Counter()

    with connect_database() as connection:
        for repository in repositories.values():
            full_name = repository["full_name"]

            try:
                issues = get_issues(full_name, repository["id"])
            except requests.exceptions.RequestException as e:
                print(f"Skipping issues for {full_name}: {e}")
                continue

            for issue in issues:
                result = sync_issue(connection, issue)
                issue_report[result] += 1

                if result in ("added", "updated"):
                    issue_number = issue["issue_number"]
                    issue_changelog[issue["id"]] = (
                        f"{full_name}#{issue_number}", result,
                    )

    return issue_changelog, issue_report

def get_untriaged_issues(connection):
    query = "SELECT * FROM issues WHERE triaged_at IS NULL"
    return connection.execute(query).fetchall()

def save_triage(connection, issue_id, triage):
    query = """
        UPDATE issues
        SET
            priority = :priority,
            category = :category,
            triaged_at = :triaged_at
        WHERE id = :id
"""
    connection.execute(query, {**triage, "id": issue_id})


@retry(
    retry=retry_if_exception_type(ServerError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, max=30),
    reraise=True,
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


def triage_issues():
    report = Counter()
    triaged_at = datetime.now(timezone.utc).isoformat()

    with connect_database() as connection:
        for issue in get_untriaged_issues(connection):
            issue_id = issue["id"]

            try:
                triage = triage_with_llm(issue["title"])
            except ServerError as err:
                print(f"Skipping issue {issue_id}: {err.message}")
                report["skipped"] += 1
                continue

            save_triage(connection, issue_id, {**triage, "triaged_at": triaged_at})
            report[triage["priority"]] += 1

    return report


def main():
    init_db()

    data_valid, data, reason = get_data()
    if not data_valid:
        print(reason)
        return

    changelog, report = sync_repositories(data)
    print(changelog)
    print("Repo report: ", report)

    issue_changelog, issue_report = sync_issues(data)
    print(issue_changelog)
    print("Issue report: ", dict(issue_report) or "No issues found")

    triage_report = triage_issues()
    print("Triage report: ", dict(triage_report) or "Nothing to triage")

if __name__ == "__main__":
    main()

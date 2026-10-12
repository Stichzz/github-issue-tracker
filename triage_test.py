CATEGORY_KEYWORDS = {
    "Bug": ("bug", "error", "crash", "fails", "broken", "exception"),
    "Feature": ("feature", "add", "support", "improve", "request"),
    "Question": ("how", "why", "help", "?"),
    "Docs": ("docs", "documentation", "readme", "typo"),
}
PRIORITY_KEYWORDS = {
    "P0": ("security", "data loss", "outage"),
    "P1": ("crash", "cannot", "broken"),
    "P2": ("error", "fails", "bug"),
}
DEFAULT_CATEGORY = "Uncategorized"
DEFAULT_PRIORITY = "P3"


def first_match(text, rules, default):
    for label, keywords in rules.items():
        if any(word in text for word in keywords):
            return label
    return default


def triage_issue(issue):
    title = issue["title"].lower()
    return {
        "priority": first_match(title, PRIORITY_KEYWORDS, DEFAULT_PRIORITY),
        "category": first_match(title, CATEGORY_KEYWORDS, DEFAULT_CATEGORY),
    }

for title in ("App crashes when saving", "Add dark mode", "Typo in the address form", "Can't find the button", "App doesn't open"):
    print(title, "->", triage_issue({"title": title}))

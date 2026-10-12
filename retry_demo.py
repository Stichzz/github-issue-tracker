from tenacity import retry, stop_after_attempt

calls = []

@retry(stop=stop_after_attempt(3))
def unreliable():
    calls.append(1)
    print("try", len(calls))
    if len(calls) < 3:
        raise ConnectionError("busy")
    return "ok"

print(unreliable())
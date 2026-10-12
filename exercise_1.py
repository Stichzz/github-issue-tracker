class RateLimiter:
    def __init__(self, name, max_call):
        self.name = name
        self.max_call = max_call
        self.calls_made = 0

    def allow(self):
        if self.calls_made < self.max_call:
            self.calls_made += 1
            return True
        return False

    def reset(self):
        self.calls_made = 0
        return f"{self.name} calls made reset to 0"

    def remaining(self):
        return self.max_call - self.calls_made

test = RateLimiter("azoth", 5)
print(test.allow())
print(test.allow())
print(test.allow())
print(test.remaining())
print(test.allow())
print(test.allow())
print(test.remaining())
print(test.allow())
print(test.reset())
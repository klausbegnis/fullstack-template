"""Headers a browser attaches to every request the integration tier replays.

A browser always sends `Origin` on a mutation, and the API refuses a
cookie-authenticated mutation that proves no allowed origin. Integration
clients send the same allowed Origin by default; a test about a foreign or
missing origin overrides it per request.
"""

BROWSER_ORIGIN = "http://localhost:3000"
BROWSER_HEADERS = {"Origin": BROWSER_ORIGIN}

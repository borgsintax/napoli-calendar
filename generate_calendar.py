import requests
from ics import Calendar

KEYWORD = "Napoli"

final_calendar = Calendar()

with open("feeds.json") as f:
    feeds = __import__("json").load(f)

for name, url in feeds.items():
    cal = Calendar(requests.get(url).text)
    for event in cal.events:
        if KEYWORD.lower() in event.name.lower():
            event.name = "⚽ " + event.name
            final_calendar.events.add(event)

with open("napoli.ics", "w") as f:
    f.writelines(final_calendar)

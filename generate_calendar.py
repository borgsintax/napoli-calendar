import json
import requests
from ics import Calendar


KEYWORD = "Napoli"
EXCLUDE_YEAR = 2024   # escludiamo gli eventi di questo anno


def load_calendar(url: str) -> Calendar:
    """Scarica il feed ICS e lo converte in Calendar."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return Calendar(resp.text)


def event_time_key(event) -> str | None:
    """
    Restituisce una chiave basata SOLO sull'orario di inizio
    (data + ora al minuto), usata per riconoscere i duplicati.
    """
    if not event.begin:
        return None

    # Normalizziamo in UTC e arrotondiamo al minuto
    dt = event.begin.to("UTC")
    return dt.format("YYYY-MM-DD HH:mm")


def add_events_from_calendar(
    cal: Calendar,
    seen_times: set[str],
    final_calendar: Calendar,
    skip_if_seen: bool
):
    """
    Aggiunge gli eventi del Napoli da un calendario:
    - se skip_if_seen=True (secondario), salta quelli con stessa data+ora
    - se skip_if_seen=False (primario), aggiunge sempre
    - esclude gli eventi del 2024
    """
    for event in cal.events:
        name = event.name or ""

        # tiene solo eventi del Napoli
        if KEYWORD.lower() not in name.lower():
            continue

        # esclude 2024
        if event.begin and event.begin.year < EXCLUDE_YEAR:
            continue

        key = event_time_key(event)

        # deduplica nel secondario
        if skip_if_seen and key is not None and key in seen_times:
            continue

        # aggiungi prefisso al summary
        if not name.startswith("⚽ "):
            event.name = "⚽ " + name

        # salva evento nel calendario finale
        final_calendar.events.add(event)

        # registra la chiave oraria per dedup
        if key is not None:
            seen_times.add(key)


def main():
    # 1) Legge gli URL
    with open("feeds.json", encoding="utf-8") as f:
        feeds = json.load(f)

    primary_url = feeds["primary"]
    secondary_url = feeds["secondary"]

    final_calendar = Calendar()
    seen_times: set[str] = set()

    # 2) Feed PRIMARIO: inserisce tutto (tranne 2024)
    primary_cal = load_calendar(primary_url)
    add_events_from_calendar(
        cal=primary_cal,
        seen_times=seen_times,
        final_calendar=final_calendar,
        skip_if_seen=False
    )

    # 3) Feed SECONDARIO: inserisce solo partite mancanti (tranne 2024)
    secondary_cal = load_calendar(secondary_url)
    add_events_from_calendar(
        cal=secondary_cal,
        seen_times=seen_times,
        final_calendar=final_calendar,
        skip_if_seen=True
    )
    # 4) DEBUG: mostra il contenuto generato dell'ICS
    print("===== DEBUG: ICS GENERATO =====")
    ics_text = final_calendar.serialize()
    print(ics_text)
    print("===== FINE DEBUG =====")

    # 5) Scrive il file ICS finale
    with open("napoli.ics", "w", encoding="utf-8") as f:
        f.write(ics_text)



if __name__ == "__main__":
    main()

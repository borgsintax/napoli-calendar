import json
from datetime import timezone

import requests
from ics import Calendar


KEYWORD = "Napoli"
MIN_YEAR = 2025  # includi solo eventi dal 2025 in poi


def load_calendar(url: str) -> Calendar:
    """Scarica il feed ICS e lo converte in un oggetto Calendar."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return Calendar(resp.text)


def get_event_datetime(event):
    """Restituisce il datetime di inizio dell'evento (timezone-aware)."""
    if not event.begin:
        return None
    # event.begin è un Arrow; .datetime è un datetime timezone-aware
    return event.begin.datetime


def get_event_year(event):
    dt = get_event_datetime(event)
    return dt.year if dt is not None else None


def event_time_key(event) -> str | None:
    """
    Chiave di deduplica basata su data+ora (in UTC, arrotondata al minuto).
    Serve solo a evitare doppi tra primary e secondary.
    """
    dt = get_event_datetime(event)
    if dt is None:
        return None

    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime("%Y-%m-%d %H:%M")


def is_cup_event(name: str) -> bool:
    """
    Riconosce eventi di Coppa / Supercoppa basandosi sul SUMMARY.
    Esempi visti nel tuo ICS:
      - 'Napoli - Modena FC [COP]'
      - 'Napoli - Cagliari [COP] (1-1)'
    """
    s = (name or "").lower()
    return (
        "[cop]" in s
        or "coppa" in s
        or "supercoppa" in s
        or "super cup" in s
    )


def add_events_from_calendar(
    cal: Calendar,
    seen_times: set[str],
    final_calendar: Calendar,
    *,
    skip_if_seen: bool,
    cup_only: bool,
):
    """
    Aggiunge eventi del Napoli da un calendario, con regole:

    - include SOLO eventi dal MIN_YEAR in poi
    - se cup_only=True → solo eventi di coppa / supercoppa
    - se skip_if_seen=True → se esiste già un evento nello stesso orario, salta
    """
    added = 0

    for event in cal.events:
        name = event.name or ""

        # 1) Deve essere una partita del Napoli
        if KEYWORD.lower() not in name.lower():
            continue

        # 2) Filtro sull'anno (solo dal 2025 in poi)
        year = get_event_year(event)
        if year is None or year < MIN_YEAR:
            continue

        # 3) Per il secondario, tieni solo le coppe
        if cup_only and not is_cup_event(name):
            continue

        # 4) Deduplica per orario (usata solo sul secondario)
        key = event_time_key(event)
        if skip_if_seen and key is not None and key in seen_times:
            continue

        # 5) Prefisso estetico
        if not name.startswith("⚽ "):
            event.name = "⚽ " + name

        final_calendar.events.add(event)
        added += 1

        if key is not None:
            seen_times.add(key)

    print(
        f"DEBUG: aggiunti {added} eventi "
        f"(cup_only={cup_only}, skip_if_seen={skip_if_seen})"
    )


def main():
    # 1) Legge gli URL dei feed
    with open("feeds.json", encoding="utf-8") as f:
        feeds = json.load(f)

    primary_url = feeds["primary"]
    secondary_url = feeds["secondary"]

    final_calendar = Calendar()
    seen_times: set[str] = set()

    # 2) Feed PRIMARIO (footballwebpages): base di tutto
    primary_cal = load_calendar(primary_url)
    add_events_from_calendar(
        cal=primary_cal,
        seen_times=seen_times,
        final_calendar=final_calendar,
        skip_if_seen=False,   # il primario non salta nulla per orario
        cup_only=False,       # prende tutte le competizioni dal 2025 in poi
    )

    # 3) Feed SECONDARIO (fixtur.es): solo coppe mancanti
    secondary_cal = load_calendar(secondary_url)
    add_events_from_calendar(
        cal=secondary_cal,
        seen_times=seen_times,
        final_calendar=final_calendar,
        skip_if_seen=True,    # evita doppi per orario rispetto al primario
        cup_only=True,        # solo Coppa Italia / Supercoppa / coppe
    )

    print(f"DEBUG: eventi totali nel calendario finale = {len(final_calendar.events)}")

    # 4) Scrive il file ICS finale
    ics_text = final_calendar.serialize()
    with open("napoli.ics", "w", encoding="utf-8") as f:
        f.write(ics_text)


if __name__ == "__main__":
    main()

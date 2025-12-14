import json
import re
from typing import Iterable, Tuple, Optional

import requests
from ics import Calendar, Event


KEYWORD = "Napoli"

PRIMARY_KEY = "primary"
SECONDARY_KEY = "secondary"


def download_calendar(url: str) -> Calendar:
    """Scarica il feed ICS e lo converte in Calendar."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return Calendar(resp.text)


def normalize_team_name(name: str) -> str:
    """Normalizza il nome squadra per il confronto."""
    name = name.lower()
    name = re.sub(r"[^a-z0-9 ]+", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def extract_teams(summary: str) -> Optional[Tuple[str, str]]:
    """
    Prova a estrarre i nomi delle due squadre dal SUMMARY.
    Funziona con formati tipo:
      "Napoli - Inter"
      "Inter v Napoli"
      "Napoli vs Milan"
    Restituisce (team1, team2) oppure None se non riesce a parsare.
    """
    if not summary:
        return None

    text = summary
    # uniforma qualche separatore
    text = text.replace("–", "-").replace("—", "-")

    separators = [" vs ", " v ", " - ", "-"]
    for sep in separators:
        if sep in text:
            parts = text.split(sep)
            if len(parts) == 2:
                team1 = normalize_team_name(parts[0])
                team2 = normalize_team_name(parts[1])
                if team1 and team2:
                    return team1, team2
    return None


def build_signature(event: Event) -> Tuple[Optional[str], str]:
    """
    Crea una 'firma' per l'evento per riconoscere i duplicati.
    Preferisce (data, squadre_ordinate).
    In fallback usa (data, summary_normalizzato).
    """
    date_str = None
    if event.begin:
        date_str = event.begin.date().isoformat()

    summary = event.name or ""
    teams = extract_teams(summary)
    if teams:
        t1, t2 = teams
        key_name = " vs ".join(sorted((t1, t2)))
    else:
        key_name = normalize_team_name(summary)

    return date_str, key_name


def iter_napoli_events(cal: Calendar) -> Iterable[Event]:
    """Ritorna solo gli eventi che contengono 'Napoli' nel nome."""
    for event in cal.events:
        name = event.name or ""
        if KEYWORD.lower() in name.lower():
            yield event


def main() -> None:
    # 1) Legge gli URL dei feed
    with open("feeds.json", encoding="utf-8") as f:
        feeds = json.load(f)

    if PRIMARY_KEY not in feeds or SECONDARY_KEY not in feeds:
        raise SystemExit(
            "feeds.json deve contenere almeno le chiavi 'primary' e 'secondary'"
        )

    final_calendar = Calendar()
    seen_signatures = set()

    # 2) Feed principale: prendiamo TUTTE le partite del Napoli
    primary_cal = download_calendar(feeds[PRIMARY_KEY])
    for event in iter_napoli_events(primary_cal):
        sig = build_signature(event)

        name = event.name or ""
        if not name.startswith("⚽ "):
            event.name = "⚽ " + name

        final_calendar.events.add(event)
        seen_signatures.add(sig)

    # 3) Feed secondario: solo gli eventi NON presenti nel principale
    secondary_cal = download_calendar(feeds[SECONDARY_KEY])
    for event in iter_napoli_events(secondary_cal):
        sig = build_signature(event)
        if sig in seen_signatures:
            # è una partita che abbiamo già dal feed principale → la saltiamo
            continue

        name = event.name or ""
        if not name.startswith("⚽ "):
            event.name = "⚽ " + name

        final_calendar.events.add(event)
        seen_signatures.add(sig)

    # 4) Scrive il file ICS finale in modo corretto
    with open("napoli.ics", "w", encoding="utf-8") as f:
        f.write(final_calendar.serialize())


if __name__ == "__main__":
    main()

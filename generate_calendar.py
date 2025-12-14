import json
import re

import requests
from ics import Calendar


KEYWORD = "Napoli"


def load_calendar(url: str) -> Calendar:
    """Scarica il feed ICS e lo converte in Calendar."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return Calendar(resp.text)


def normalize_summary(summary: str) -> str:
    """
    Normalizza il nome della partita per confronti "parziali".
    - minuscolo
    - toglie punteggiature strane, punteggi, parentesi, numeri
    - compatta gli spazi
    """
    s = summary.lower()

    # normalizza separatori
    s = s.replace("–", " ").replace("—", " ").replace("-", " ")

    # rimuove contenuto tra parentesi (es. punteggi, minuti, ecc.)
    s = re.sub(r"\([^)]*\)", " ", s)

    # rimuove cifre (es. risultati 2-1, 1^ giornata, ecc.)
    s = re.sub(r"\d", " ", s)

    # tiene solo lettere, spazi
    s = re.sub(r"[^a-zàèéìòù\s]", " ", s)

    # compatta spazi
    s = re.sub(r"\s+", " ", s)

    return s.strip()


def collect_napoli_events(cal: Calendar):
    """
    Estrae solo gli eventi che contengono 'Napoli' nel nome
    e restituisce tuple (data_str, summary_normalizzato, event).
    """
    result = []
    for e in cal.events:
        name = e.name or ""
        if KEYWORD.lower() not in name.lower():
            continue

        # prefisso carino per il calendario
        if not name.startswith("⚽ "):
            e.name = "⚽ " + name

        date_str = e.begin.date().isoformat() if e.begin else None
        norm = normalize_summary(name)
        result.append((date_str, norm, e))
    return result


def is_duplicate(date_str: str, norm_secondary: str, primary_index):
    """
    Ritorna True se, in quella data, esiste già nel primario
    una partita 'simile' (almeno una parola in comune diversa da 'napoli').
    """
    if date_str not in primary_index:
        return False

    # token del secondario, esclusa la parola 'napoli'
    tokens2 = [t for t in norm_secondary.split() if t != "napoli"]
    if not tokens2:
        return False

    for norm_primary in primary_index[date_str]:
        tokens1 = [t for t in norm_primary.split() if t != "napoli"]
        # parole in comune (es. 'inter', 'milan', 'juventus'…)
        common = set(tokens1) & set(tokens2)
        if common:
            return True

    return False


def main():
    # 1) Legge gli URL dei feed
    with open("feeds.json", encoding="utf-8") as f:
        feeds = json.load(f)

    primary_url = feeds["primary"]
    secondary_url = feeds["secondary"]

    final_calendar = Calendar()

    # 2) Feed PRIMARIO: prendiamo tutti gli eventi del Napoli
    primary_cal = load_calendar(primary_url)
    primary_events = collect_napoli_events(primary_cal)

    # indicizzazione per data
    primary_index = {}
    for date_str, norm, event in primary_events:
        final_calendar.events.add(event)
        primary_index.setdefault(date_str, []).append(norm)

    # 3) Feed SECONDARIO: aggiungiamo solo quelli mancanti
    secondary_cal = load_calendar(secondary_url)
    secondary_events = collect_napoli_events(secondary_cal)

    for date_str, norm, event in secondary_events:
        # se è "parzialmente uguale" a uno del primario, lo saltiamo
        if is_duplicate(date_str, norm, primary_index):
            continue

        final_calendar.events.add(event)
        primary_index.setdefault(date_str, []).append(norm)

    # 4) Scrive il file ICS finale in modo corretto
    with open("napoli.ics", "w", encoding="utf-8") as f:
        f.write(final_calendar.serialize())


if __name__ == "__main__":
    main()

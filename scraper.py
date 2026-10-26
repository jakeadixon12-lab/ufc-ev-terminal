import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
}

def clean_odds(val_str):
    if not val_str:
        return None
    val_str = val_str.replace("▲", "").replace("▼", "").strip()
    try:
        return int(val_str)
    except ValueError:
        return None

def is_valid_ufc_event(title):
    t = title.lower()
    # Reject speculative future pools, futures, and prop sub-sections
    if any(blocked in t for blocked in ["future event", "futures", "props", "speculative"]):
        return False
    # Only keep UFC events
    return "ufc" in t or "fight night" in t

def scrape_bestfightodds(max_events=3):
    url = "https://www.bestfightodds.com"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    bouts = []

    # BestFightOdds wraps each card in table-header / table-div blocks
    sections = soup.find_all("div", class_=re.compile(r"table-div|table-header", re.I))
    if not sections:
        sections = [soup]

    discovered_events = []

    for sec in sections:
        header_el = sec.find_previous(["h1", "h2", "div"], class_=re.compile(r"table-header|event-header|content-list-title", re.I))
        if not header_el:
            header_el = sec.find(["h1", "h2", "span"], class_=re.compile(r"header|title", re.I))

        raw_title = header_el.get_text(strip=True) if header_el else ""

        if not is_valid_ufc_event(raw_title):
            continue

        if raw_title not in discovered_events:
            # Stop once we have reached the first 3 chronological UFC events
            if len(discovered_events) >= max_events:
                break
            discovered_events.append(raw_title)

        event_name = raw_title

        table = sec.find("table") if sec.name != "table" else sec
        if not table:
            continue

        thead = table.find("thead")
        headers = []
        if thead:
            for th in thead.find_all("th"):
                img = th.find("img")
                name = img.get("title", "") if img else th.get_text(strip=True)
                headers.append(name.lower())

        tbody = table.find("tbody")
        if not tbody:
            continue

        rows = tbody.find_all("tr")
        i = 0
        while i < len(rows) - 1:
            r1 = rows[i]
            r2 = rows[i + 1]

            f1_tag = r1.find("th") or r1.find("td")
            f2_tag = r2.find("th") or r2.find("td")

            if not f1_tag or not f2_tag:
                i += 1
                continue

            f1_name = f1_tag.get_text(strip=True)
            f2_name = f2_tag.get_text(strip=True)

            if not f1_name or not f2_name:
                i += 2
                continue

            odds_dict = {}
            cells_1 = r1.find_all("td")
            cells_2 = r2.find_all("td")

            for col_idx, cell1 in enumerate(cells_1):
                book = headers[col_idx + 1] if col_idx + 1 < len(headers) else f"book_{col_idx}"
                cell2 = cells_2[col_idx] if col_idx < len(cells_2) else None

                o1 = clean_odds(cell1.get_text(strip=True))
                o2 = clean_odds(cell2.get_text(strip=True)) if cell2 else None

                if o1 is not None or o2 is not None:
                    odds_dict[book] = {"f1_odds": o1, "f2_odds": o2}

            if odds_dict:
                bouts.append({
                    "event_name": event_name,
                    "fighter_1": f1_name,
                    "fighter_2": f2_name,
                    "odds": odds_dict
                })

            i += 2

    return bouts
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.8"
}

def clean_odds(val_str):
    if not val_str:
        return None
    val_str = val_str.replace("▲", "").replace("▼", "").strip()
    try:
        return int(val_str)
    except ValueError:
        return None

def clean_event_title(title):
    t = title.strip()
    if t.lower().endswith(" odds"):
        t = t[:-5].strip()
    return t

def scrape_bestfightodds(max_events=3):
    url = "https://www.bestfightodds.com"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    bouts = []

    # Find all table-div elements that contain the real fight tables
    table_divs = soup.find_all("div", class_="table-div")
    print(f"[Debug] Found {len(table_divs)} fight table containers.")

    events_captured = 0

    for t_div in table_divs:
        # The event header sits directly preceding this table-div
        prev_header = t_div.find_previous("div", class_="table-header")
        if not prev_header:
            continue

        raw_title = prev_header.get_text(strip=True)
        lower_title = raw_title.lower()

        # Stop scanning as soon as we reach Future Events
        if any(term in lower_title for term in ["future event", "futures", "props"]):
            print(f"[Debug] Reached futures boundary at '{raw_title}'. Terminating scan.")
            break

        # Filter strictly for UFC events
        if "ufc" not in lower_title and "fight night" not in lower_title:
            print(f"[Debug] Skipping non-UFC promotion: '{raw_title}'")
            continue

        event_name = clean_event_title(raw_title)

        table = t_div.find("table")
        if not table:
            continue

        # Extract book names from this specific event table
        thead = table.find("thead")
        book_headers = []
        if thead:
            for th in thead.find_all("th"):
                img = th.find("img")
                name = img.get("title", "") if img else th.get_text(strip=True)
                book_headers.append(name.lower() if name else "")

        tbody = table.find("tbody") or table
        rows = tbody.find_all("tr")

        event_bout_count = 0
        i = 0
        while i < len(rows) - 1:
            r1 = rows[i]
            r2 = rows[i + 1]

            f1_tag = r1.find(["th", "td"])
            f2_tag = r2.find(["th", "td"])

            if not f1_tag or not f2_tag:
                i += 1
                continue

            f1_name = f1_tag.get_text(strip=True)
            f2_name = f2_tag.get_text(strip=True)

            if not f1_name or not f2_name or f1_name.lower() in ["fighter", "matchup"]:
                i += 1
                continue

            cells_1 = r1.find_all("td")
            cells_2 = r2.find_all("td")

            if not cells_1 or not cells_2:
                i += 1
                continue

            odds_dict = {}
            for col_idx, cell1 in enumerate(cells_1):
                book = book_headers[col_idx + 1] if col_idx + 1 < len(book_headers) else f"book_{col_idx}"
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
                event_bout_count += 1

            i += 2

        print(f"[Debug] Event '{event_name}': successfully parsed {event_bout_count} bouts.")
        events_captured += 1
        if events_captured >= max_events:
            print(f"[Debug] Reached {max_events} UFC events cap. Done.")
            break

    print(f"[✔] Total bouts extracted: {len(bouts)} across {events_captured} UFC events.")
    return bouts
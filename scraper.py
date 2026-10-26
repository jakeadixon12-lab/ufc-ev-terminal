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
    # Strip off trailing ' Odds' for cleaner terminal tab titles
    if t.lower().endswith(" odds"):
        t = t[:-5].strip()
    return t

def scrape_bestfightodds(max_events=3):
    url = "https://www.bestfightodds.com"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    bouts = []

    # Target all event table header divs
    headers = soup.find_all("div", class_="table-header")
    print(f"[Debug] Total table-header containers found on page: {len(headers)}")

    events_parsed = 0

    for header_div in headers:
        title_el = header_div.find(["a", "h1", "h2", "span"])
        raw_title = title_el.get_text(strip=True) if title_el else "UFC Event"
        lower_title = raw_title.lower()

        # Stop at Future Events / Futures boundary
        if any(term in lower_title for term in ["future", "futures", "props"]):
            print(f"[Debug] Reached futures boundary at '{raw_title}'. Stopping.")
            break

        # Filter strictly for UFC events
        if "ufc" not in lower_title and "fight night" not in lower_title:
            print(f"[Debug] Skipping non-UFC promotion: '{raw_title}'")
            continue

        event_name = clean_event_title(raw_title)

        # Locate table container: look at immediate sibling or search forward until next header
        table_div = header_div.find_next_sibling("div", class_=re.compile(r"table-div|table-wrapper", re.I))
        if not table_div:
            table_div = header_div.find_next("div", class_=re.compile(r"table-div|table-wrapper", re.I))

        if not table_div:
            print(f"[Debug] No table container found for '{event_name}'")
            continue

        table = table_div.find("table")
        if not table:
            continue

        # Extract book names from any th tags in the table head or first tr
        book_headers = []
        for th in table.find_all("th"):
            img = th.find("img")
            name = img.get("title", "") if img else th.get_text(strip=True)
            if name:
                book_headers.append(name.lower())

        # Pull all rows directly from table (do not rely on <tbody>)
        all_trs = table.find_all("tr")
        # Filter out header tr
        rows = [tr for tr in all_trs if not tr.find("th", class_=re.compile(r"th-header|header", re.I))]

        event_bouts_count = 0
        i = 0
        while i < len(rows) - 1:
            r1 = rows[i]
            r2 = rows[i + 1]

            f1_tag = r1.find(["th", "td"], class_=re.compile(r"item-name|fighter|name", re.I)) or r1.find(["th", "td"])
            f2_tag = r2.find(["th", "td"], class_=re.compile(r"item-name|fighter|name", re.I)) or r2.find(["th", "td"])

            if not f1_tag or not f2_tag:
                i += 1
                continue

            f1_name = f1_tag.get_text(strip=True)
            f2_name = f2_tag.get_text(strip=True)

            # Skip header or empty rows
            if not f1_name or not f2_name or f1_name.lower() in ["fighter", "matchup", "event"]:
                i += 1
                continue

            odds_dict = {}
            cells_1 = r1.find_all("td")
            cells_2 = r2.find_all("td")

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
                event_bouts_count += 1

            i += 2

        print(f"[Debug] Event parsed: '{event_name}' with {event_bouts_count} bouts.")
        events_parsed += 1
        if events_parsed >= max_events:
            break

    return bouts
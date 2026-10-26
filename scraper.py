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

def is_prop_name(name):
    lower = name.lower()
    return any(p in lower for p in ["over", "under", "round", "decision", "distance", "draw", "points", "inside"])

def scrape_bestfightodds(max_events=3):
    url = "https://www.bestfightodds.com"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    bouts = []

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

        # Locate table container
        table = header_div.find_next("table")
        if not table:
            continue

        # Extract sportsbook names from header row
        book_headers = []
        thead = table.find("thead")
        header_row = thead.find("tr") if thead else table.find("tr")
        if header_row:
            for th in header_row.find_all("th"):
                img = th.find("img")
                name = img.get("title", "") if img else th.get_text(strip=True)
                book_headers.append(name.lower() if name else "")

        # Parse ALL rows that contain cells
        all_trs = table.find_all("tr")
        parsed_rows = []

        for tr in all_trs:
            name_cell = tr.find(["th", "td"])
            if not name_cell:
                continue

            name = name_cell.get_text(strip=True)
            if not name or name.lower() in ["fighter", "matchup", "event"]:
                continue

            # Extract odds from each td in this row
            cells = tr.find_all("td")
            if not cells:
                continue

            row_odds = {}
            for col_idx, cell in enumerate(cells):
                # Book index offset: first column in thead corresponds to fighter name
                book_name = book_headers[col_idx + 1] if col_idx + 1 < len(book_headers) else f"book_{col_idx}"
                val = clean_odds(cell.get_text(strip=True))
                if val is not None:
                    row_odds[book_name] = val

            parsed_rows.append({
                "name": name,
                "is_prop": is_prop_name(name),
                "odds": row_odds
            })

        # Pair fighters sequentially (skipping intermediate props)
        event_bouts_count = 0
        idx = 0
        while idx < len(parsed_rows) - 1:
            row_a = parsed_rows[idx]

            # If row_a is a standalone prop, increment and continue
            if row_a["is_prop"]:
                idx += 1
                continue

            # Find the very next fighter row (row_b)
            row_b = None
            next_fighter_idx = idx + 1
            while next_fighter_idx < len(parsed_rows):
                if not parsed_rows[next_fighter_idx]["is_prop"]:
                    row_b = parsed_rows[next_fighter_idx]
                    break
                next_fighter_idx += 1

            if not row_b:
                break

            f1_name = row_a["name"]
            f2_name = row_b["name"]

            # Merge odds for both fighters across books
            all_books = set(row_a["odds"].keys()).union(set(row_b["odds"].keys()))
            odds_dict = {}
            for b in all_books:
                odds_dict[b] = {
                    "f1_odds": row_a["odds"].get(b),
                    "f2_odds": row_b["odds"].get(b)
                }

            if odds_dict:
                bouts.append({
                    "event_name": event_name,
                    "fighter_1": f1_name,
                    "fighter_2": f2_name,
                    "odds": odds_dict
                })
                event_bouts_count += 1

            # Advance past row_b
            idx = next_fighter_idx + 1

        print(f"[Debug] Event parsed: '{event_name}' with {event_bouts_count} bouts.")
        events_parsed += 1
        if events_parsed >= max_events:
            break

    return bouts
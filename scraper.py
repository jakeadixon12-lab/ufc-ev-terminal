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

def clean_event_title(header_el):
    """Extract strictly the clean event title (e.g., 'UFC Vegas 123', 'UFC 334')."""
    # Prefer the primary anchor link inside header
    anchor = header_el.find("a")
    raw = anchor.get_text(strip=True) if anchor else header_el.get_text(strip=True)
    # Remove clutter like 'Odds', arrows, dates
    cleaned = re.sub(r"\bOdds\b.*", "", raw, flags=re.I).strip()
    return cleaned if cleaned else raw.strip()

def scrape_bestfightodds(max_events=3):
    url = "https://www.bestfightodds.com"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    bouts = []

    table_divs = soup.find_all("div", class_="table-div")
    print(f"[Debug] Found {len(table_divs)} fight table containers.")

    events_captured = 0

    for t_div in table_divs:
        prev_header = t_div.find_previous("div", class_="table-header")
        if not prev_header:
            continue

        raw_header_text = prev_header.get_text(strip=True)
        lower_header = raw_header_text.lower()

        # Stop scanning at Future Events
        if any(term in lower_header for term in ["future event", "futures", "props"]):
            print(f"[Debug] Reached futures boundary at '{raw_header_text}'. Terminating scan.")
            break

        # Filter strictly for UFC events
        if "ufc" not in lower_header and "fight night" not in lower_header:
            print(f"[Debug] Skipping non-UFC promotion: '{raw_header_text[:40]}...'")
            continue

        event_name = clean_event_title(prev_header)

        # Locate the table inside this table-div
        table = t_div.find("table")
        if not table:
            continue

        # Extract book column names from thead
        book_headers = []
        thead = table.find("thead")
        if thead:
            for th in thead.find_all("th"):
                img = th.find("img")
                name = img.get("title", "") if img else th.get_text(strip=True)
                book_headers.append(name.lower() if name else "")

        # Extract all rows from this event's table
        all_trs = table.find_all("tr")
        # Filter for rows that actually contain data cells
        data_trs = [tr for tr in all_trs if tr.find_all("td")]

        event_bout_count = 0
        i = 0
        while i < len(data_trs) - 1:
            r1 = data_trs[i]
            r2 = data_trs[i + 1]

            # In BestFightOdds, fighter name is in the first th (or first td)
            f1_cell = r1.find(["th", "td"])
            f2_cell = r2.find(["th", "td"])

            f1_name = f1_cell.get_text(strip=True) if f1_cell else ""
            f2_name = f2_cell.get_text(strip=True) if f2_cell else ""

            # Check if this row is an empty row or subheader
            if not f1_name or not f2_name:
                i += 1
                continue

            cells_1 = r1.find_all("td")
            cells_2 = r2.find_all("td")

            # Must have odds columns
            if not cells_1 or not cells_2:
                i += 1
                continue

            odds_dict = {}
            for col_idx, cell1 in enumerate(cells_1):
                # Map col_idx to the book_headers extracted from thead
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
            else:
                i += 1

        print(f"[Debug] Event '{event_name}': successfully parsed {event_bout_count} bouts.")
        events_captured += 1
        if events_captured >= max_events:
            print(f"[Debug] Reached {max_events} UFC events cap. Done.")
            break

    print(f"[✔] Total bouts extracted: {len(bouts)} across {events_captured} UFC events.")
    return bouts
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

    # BestFightOdds primary board table
    table = soup.find("table", class_=re.compile(r"team-odds-table|odds-table", re.I))
    if not table:
        table = soup.find("table")

    if not table:
        print("[!] No odds table found on page.")
        return []

    # Extract all book header labels across columns
    book_headers = []
    thead = table.find("thead")
    header_tr = thead.find("tr") if thead else table.find("tr")
    if header_row := header_tr:
        for th in header_row.find_all("th"):
            img = th.find("img")
            name = img.get("title", "") if img else th.get_text(strip=True)
            book_headers.append(name.lower() if name else "")

    print(f"[Debug] Detected {len(book_headers)} table header columns.")

    current_event = None
    discovered_ufc_events = []
    
    # Process every row sequentially top to bottom
    all_trs = table.find_all("tr")
    print(f"[Debug] Scanning {len(all_trs)} total table rows.")

    i = 0
    while i < len(all_trs):
        tr = all_trs[i]

        # 1. Check if this row is an Event Header Banner
        header_el = tr.find(["th", "td", "a", "h2", "span"], class_=re.compile(r"table-header|content-list-title|header", re.I))
        if not header_el and tr.find("th") and len(tr.find_all("td")) == 0:
            header_el = tr.find("th")

        row_text = tr.get_text(strip=True) if tr else ""
        
        # If the row is a section divider or banner
        if header_el or "odds" in row_text.lower():
            candidate_title = clean_event_title(header_el.get_text(strip=True) if header_el else row_text)
            candidate_lower = candidate_title.lower()

            # Boundary: Stop as soon as we reach Future Events
            if any(term in candidate_lower for term in ["future event", "futures", "props"]):
                print(f"[Debug] Reached Futures boundary at '{candidate_title}'. Terminating scan.")
                break

            # If this is a valid UFC event, switch context
            if "ufc" in candidate_lower or "fight night" in candidate_lower:
                if candidate_title != current_event:
                    if candidate_title not in discovered_ufc_events:
                        if len(discovered_ufc_events) >= max_events:
                            print(f"[Debug] Reached max limit of {max_events} UFC events. Stopping.")
                            break
                        discovered_ufc_events.append(candidate_title)
                    current_event = candidate_title
                    print(f"[Debug] Switched active event to: '{current_event}'")
            elif any(promo in candidate_lower for promo in ["bellator", "pfl", "ksw", "one championship", "cage warriors"]):
                # Non-UFC promo header - mute current_event so its fights get skipped
                current_event = None

            i += 1
            continue

        # 2. If we are not currently inside an accepted UFC card, skip this row
        if not current_event:
            i += 1
            continue

        # 3. Process candidate matchup (pairs of rows with odds cells)
        cells_1 = tr.find_all("td")
        if not cells_1 or len(cells_1) < 2:
            i += 1
            continue

        # Look for fighter 2 on the next line
        if i + 1 >= len(all_trs):
            break

        next_tr = all_trs[i + 1]
        cells_2 = next_tr.find_all("td")
        if not cells_2 or len(cells_2) < 2:
            i += 1
            continue

        f1_tag = tr.find("th") or tr.find("td")
        f2_tag = next_tr.find("th") or next_tr.find("td")

        f1_name = f1_tag.get_text(strip=True) if f1_tag else ""
        f2_name = f2_tag.get_text(strip=True) if f2_tag else ""

        # Discard header text or invalid rows
        if not f1_name or not f2_name or f1_name.lower() in ["fighter", "matchup", "event"]:
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
                "event_name": current_event,
                "fighter_1": f1_name,
                "fighter_2": f2_name,
                "odds": odds_dict
            })
            # Advance past both fighter rows
            i += 2
        else:
            i += 1

    print(f"[✔] Successfully scraped {len(bouts)} bouts across {len(discovered_ufc_events)} live events.")
    return bouts
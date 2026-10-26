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

def scrape_bestfightodds(max_events=3):
    url = "https://www.bestfightodds.com"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    bouts = []

    # BestFightOdds pairs each card with a table-header followed by table-div
    headers = soup.find_all("div", class_="table-header")
    print(f"[Debug] Total table-header containers found on page: {len(headers)}")

    events_parsed = 0

    for header_div in headers:
        # Extract title text
        title_el = header_div.find(["a", "h1", "h2", "span"])
        raw_title = title_el.get_text(strip=True) if title_el else "UFC Event"
        lower_title = raw_title.lower()

        # Stop as soon as we reach Future Events or generic props
        if any(term in lower_title for term in ["future", "futures", "props"]):
            print(f"[Debug] Reached futures boundary at '{raw_title}'. Stopping.")
            break

        # Locate the adjacent table container
        table_div = header_div.find_next_sibling("div", class_="table-div")
        if not table_div:
            table_div = header_div.find_next("div", class_="table-div")

        if not table_div:
            continue

        table = table_div.find("table")
        if not table:
            continue

        # Extract books from table header
        thead = table.find("thead")
        book_headers = []
        if thead:
            for th in thead.find_all("th"):
                img = th.find("img")
                name = img.get("title", "") if img else th.get_text(strip=True)
                book_headers.append(name.lower())

        tbody = table.find("tbody")
        if not tbody:
            continue

        rows = tbody.find_all("tr")
        if not rows:
            continue

        event_bouts_count = 0
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
                book = book_headers[col_idx + 1] if col_idx + 1 < len(book_headers) else f"book_{col_idx}"
                cell2 = cells_2[col_idx] if col_idx < len(cells_2) else None

                o1 = clean_odds(cell1.get_text(strip=True))
                o2 = clean_odds(cell2.get_text(strip=True)) if cell2 else None

                if o1 is not None or o2 is not None:
                    odds_dict[book] = {"f1_odds": o1, "f2_odds": o2}

            if odds_dict:
                bouts.append({
                    "event_name": raw_title,
                    "fighter_1": f1_name,
                    "fighter_2": f2_name,
                    "odds": odds_dict
                })
                event_bouts_count += 1

            i += 2

        print(f"[Debug] Event parsed: '{raw_title}' with {event_bouts_count} bouts.")
        events_parsed += 1
        if events_parsed >= max_events:
            break

    return bouts
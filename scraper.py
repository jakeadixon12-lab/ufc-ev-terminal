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

def scrape_bestfightodds(max_events=3):
    url = "https://www.bestfightodds.com"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    bouts = []

    # BestFightOdds structures cards inside div.table-div or tables within content containers
    event_divs = soup.find_all("div", class_=re.compile(r"table-div|table-header", re.I))
    if not event_divs:
        event_divs = soup.find_all("table")

    valid_events_count = 0
    seen_event_names = []

    for item in event_divs:
        # Find the title of this section
        title_el = item.find_previous(["h1", "h2", "div", "span"], class_=re.compile(r"table-header|event-header|content-list-title|header", re.I))
        if not title_el:
            title_el = item.find(["h1", "h2", "span", "a"])

        raw_title = title_el.get_text(strip=True) if title_el else "Upcoming UFC Card"
        lower_title = raw_title.lower()

        # Stop as soon as we hit the Future Events or generic Props section
        if any(b in lower_title for b in ["future event", "futures", "props", "speculative"]):
            break

        table = item if item.name == "table" else item.find("table")
        if not table:
            continue

        # Extract sportsbooks from table header
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
        if not rows:
            continue

        if raw_title not in seen_event_names:
            if valid_events_count >= max_events:
                break
            seen_event_names.append(raw_title)
            valid_events_count += 1

        event_name = raw_title

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
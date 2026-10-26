import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

def clean_american_odds(raw_text: str) -> int | None:
    """Extracts integer American odds (+150, -220) from strings containing arrows or spaces."""
    if not raw_text:
        return None
    # Strip non-ASCII (arrows like ▲ ▼)
    cleaned = re.sub(r"[^\d+\-]", "", raw_text)
    match = re.search(r"([+-]\d{3,4})", cleaned)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None

def scrape_bestfightodds() -> list[dict]:
    """
    Scrapes live fight odds from BestFightOdds.com.
    Returns a list of structured fight rows with book-by-book moneylines.
    """
    url = "https://www.bestfightodds.com/"
    response = requests.get(url, headers=HEADERS, timeout=12)
    if response.status_code != 200:
        raise RuntimeError(f"BestFightOdds HTTP error: {response.status_code}")

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table", class_="odds-table")

    all_bouts = []

    for table in tables:
        # Determine table/event header
        header_row = table.find("thead")
        if not header_row:
            continue

        # Extract sportsbook column titles
        book_headers = header_row.find_all("th")[1:]
        book_names = [th.get_text(strip=True) for th in book_headers]

        # BestFightOdds arranges each bout as two consecutive <tr> rows
        tbody = table.find("tbody")
        if not tbody:
            continue

        rows = tbody.find_all("tr")
        i = 0
        while i < len(rows) - 1:
            r1 = rows[i]
            r2 = rows[i + 1]

            th1 = r1.find("th")
            th2 = r2.find("th")

            if not th1 or not th2:
                i += 1
                continue

            f1_name = th1.get_text(strip=True)
            f2_name = th2.get_text(strip=True)

            tds_1 = r1.find_all("td")
            tds_2 = r2.find_all("td")

            bout_odds = {}
            for idx, book in enumerate(book_names):
                if idx < len(tds_1) and idx < len(tds_2):
                    o1 = clean_american_odds(tds_1[idx].get_text(strip=True))
                    o2 = clean_american_odds(tds_2[idx].get_text(strip=True))
                    if o1 is not None and o2 is not None:
                        bout_odds[book] = {
                            "f1_odds": o1,
                            "f2_odds": o2
                        }

            if bout_odds:
                all_bouts.append({
                    "fighter_1": f1_name,
                    "fighter_2": f2_name,
                    "odds": bout_odds,
                    "scraped_at": datetime.now(timezone.utc).isoformat()
                })
            i += 2

    return all_bouts

def parse_raw_text_odds(pasted_text: str) -> list[dict]:
    """
    Parses tab-separated or space-separated odds copied directly from
    BestFightOdds or FightOdds.io text blocks.
    """
    lines = [line.strip() for line in pasted_text.strip().split("\n") if line.strip()]
    if not lines:
        return []

    # Detect header columns if present
    parsed_bouts = []
    # Regular expression for matching lines like: "Renato Moicano +113 -136 +106..."
    for line in lines:
        parts = re.split(r"\t+|\s{2,}", line)
        if len(parts) >= 2:
            name = parts[0].strip()
            odds = [clean_american_odds(p) for p in parts[1:] if clean_american_odds(p) is not None]
            parsed_bouts.append({"name": name, "odds": odds})

    return parsed_bouts

if __name__ == "__main__":
    print("Testing live scrape from BestFightOdds.com...")
    try:
        bouts = scrape_bestfightodds()
        print(f"Successfully scraped {len(bouts)} bouts!")
        if bouts:
            sample = bouts[0]
            print(f"Sample Bout: {sample['fighter_1']} vs {sample['fighter_2']}")
            print("Available Books:", list(sample['odds'].keys())[:6])
    except Exception as e:
        print(f"Scraper encountered error: {e}")
import os
import sys
import time
from supabase import create_client, Client
import scraper
import engine

raw_url = os.environ.get("SUPABASE_URL", "")
raw_key = os.environ.get("SUPABASE_KEY", "")

clean_url = raw_url.strip().strip("'").strip('"') if raw_url else ""
clean_key = raw_key.strip().strip("'").strip('"') if raw_key else ""

if clean_url.startswith("http://") or clean_url.startswith("https://"):
    SUPABASE_URL = clean_url
else:
    SUPABASE_URL = "https://tviydjpxxhplnyqvzosb.supabase.co"

SUPABASE_KEY = clean_key if clean_key else "sb_publishable_qGixbj6WiH_lgUrZ4ubirQ_ALu_czCS"

print(f"[Init] Connecting to Supabase project: {SUPABASE_URL}")

def parse_and_sync():
    sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("\n[⚡] Starting live odds ingestion across sources...")
    
    # Dynamically scrapes the top 3 live UFC events found chronologically on the page
    bfo_bouts = scraper.scrape_bestfightodds(max_events=3)
    print(f"[BFO] Scraped {len(bfo_bouts)} matchups across the next 3 UFC events.")
    
    if not bfo_bouts:
        print("[!] Warning: Scraper returned 0 bouts. Preserving existing records.")
        return

    sample_keys = set()
    for b in bfo_bouts[:5]:
        sample_keys.update(b.get("odds", {}).keys())
    print(f"[Debug] Sportsbook keys detected on page: {list(sample_keys)}")

    rows_to_insert = []

    for bout in bfo_bouts:
        f1 = bout.get("fighter_1", "").strip()
        f2 = bout.get("fighter_2", "").strip()
        event_name = bout.get("event_name", "UFC Upcoming Event").strip()
        odds_dict = bout.get("odds", {})

        if not f1 or not f2 or not odds_dict:
            continue

        sharp_key = next((k for k in odds_dict.keys() if any(bm in k.lower() for bm in ["pin", "circa", "betonline", "heritage"])), None)
        
        sharp_f1 = None
        sharp_f2 = None
        fair1 = None
        fair2 = None

        if sharp_key:
            sharp_f1 = odds_dict[sharp_key].get("f1_odds")
            sharp_f2 = odds_dict[sharp_key].get("f2_odds")

        if sharp_f1 is None or sharp_f2 is None:
            dk_fallback = next((k for k in odds_dict.keys() if "draft" in k.lower()), None)
            if dk_fallback and odds_dict[dk_fallback].get("f1_odds") and odds_dict[dk_fallback].get("f2_odds"):
                sharp_f1 = odds_dict[dk_fallback].get("f1_odds")
                sharp_f2 = odds_dict[dk_fallback].get("f2_odds")
            else:
                for k, v in odds_dict.items():
                    if v.get("f1_odds") is not None and v.get("f2_odds") is not None:
                        sharp_f1 = v.get("f1_odds")
                        sharp_f2 = v.get("f2_odds")
                        break

        if sharp_f1 is not None and sharp_f2 is not None:
            try:
                prob1, prob2, fair1, fair2 = engine.devig_multiplicative(sharp_f1, sharp_f2)
            except Exception:
                fair1, fair2 = None, None

        books_payload = {}
        for book_name, prices in odds_dict.items():
            books_payload[book_name] = {
                "f1": prices.get("f1_odds"),
                "f2": prices.get("f2_odds")
            }

        rows_to_insert.append({
            "source": "BestFightOdds",
            "event_name": event_name,
            "fighter_1": f1,
            "fighter_2": f2,
            "pin_f1": sharp_f1,
            "pin_f2": sharp_f2,
            "fair_1": fair1,
            "fair_2": fair2,
            "all_books": books_payload
        })

    print(f"[Engine] Processed {len(rows_to_insert)} bouts ready for insertion.")

    if rows_to_insert:
        print("[Supabase] Refreshing market_odds table...")
        sb.table("market_odds").delete().gte("id", 0).execute()
        
        batch_size = 25
        for i in range(0, len(rows_to_insert), batch_size):
            batch = rows_to_insert[i:i + batch_size]
            sb.table("market_odds").insert(batch).execute()
            print(f"[Supabase] Uploaded batch {i // batch_size + 1} ({len(batch)} fights)...")
            
        print(f"[✔] Successfully published {len(rows_to_insert)} bouts across live events to Supabase!")
    else:
        print("[!] No bouts could be structured.")

if __name__ == "__main__":
    parse_and_sync()
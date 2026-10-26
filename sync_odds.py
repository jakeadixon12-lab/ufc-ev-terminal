import os
import sys
import time
from supabase import create_client, Client
import scraper
import engine

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://tviydjpxxhplnyqvzosb.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_qGixbj6WiH_lgUrZ4ubirQ_ALu_czCS")

def parse_and_sync():
    sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("\n[⚡] Starting live odds ingestion across sources...")
    
    bfo_bouts = scraper.scrape_bestfightodds()
    print(f"[BFO] Scraped {len(bfo_bouts)} matchups from BestFightOdds.")
    
    rows_to_insert = []

    for bout in bfo_bouts:
        f1 = bout["fighter_1"]
        f2 = bout["fighter_2"]
        odds_dict = bout["odds"]

        sharp_key = next((k for k in odds_dict.keys() if any(bm in k.lower() for bm in ["pinnacle", "circa"])), None)
        if not sharp_key:
            continue

        sharp_f1 = odds_dict[sharp_key].get("f1_odds")
        sharp_f2 = odds_dict[sharp_key].get("f2_odds")
        if sharp_f1 is None or sharp_f2 is None:
            continue

        prob1, prob2, fair1, fair2 = engine.devig_multiplicative(sharp_f1, sharp_f2)

        books_payload = {}
        for book_name, prices in odds_dict.items():
            books_payload[book_name] = {
                "f1": prices.get("f1_odds"),
                "f2": prices.get("f2_odds")
            }

        rows_to_insert.append({
            "source": "BestFightOdds",
            "event_name": "UFC Upcoming",
            "fighter_1": f1,
            "fighter_2": f2,
            "pin_f1": sharp_f1,
            "pin_f2": sharp_f2,
            "fair_1": fair1,
            "fair_2": fair2,
            "all_books": books_payload
        })

    if rows_to_insert:
        sb.table("market_odds").delete().gte("id", 0).execute()
        
        batch_size = 25
        for i in range(0, len(rows_to_insert), batch_size):
            batch = rows_to_insert[i:i + batch_size]
            sb.table("market_odds").insert(batch).execute()
            
        print(f"[✔] Successfully published {len(rows_to_insert)} fully-analyzed bouts to Supabase!")
    else:
        print("[!] No active bouts with sharp lines found.")

if __name__ == "__main__":
    if "--loop" in sys.argv:
        print("[🔄] Terminal Auto-Pilot running. Syncing every 5 minutes. Press Ctrl+C to stop.")
        while True:
            try:
                parse_and_sync()
            except Exception as e:
                print(f"[Error] Sync failed: {e}")
            time.sleep(300)
    else:
        parse_and_sync()
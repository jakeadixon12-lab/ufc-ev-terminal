import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

import database
import engine
import scraper
import ai_analyst

app = FastAPI(title="UFC +EV Terminal API")

# Ensure static directory exists for frontend files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic Schemas
class BetCreate(BaseModel):
    event_name: str
    fighter_selected: str
    opponent: str
    sportsbook: str
    odds_placed: int
    stake: float
    potential_payout: float
    expected_value: float

class BetSettle(BaseModel):
    status: str  # WON, LOST, PUSH

class CustomDevigRequest(BaseModel):
    sharp_odds_a: int
    sharp_odds_b: int
    offered_odds: int
    bankroll: float = 200.0

@app.get("/")
def serve_dashboard():
    return FileResponse("static/index.html")

# 1. Bankroll & Metrics Overview
@app.get("/api/metrics")
def get_metrics(initial_bankroll: float = 200.0, db: Session = Depends(get_db)):
    wagers = db.query(database.Wager).all()

    total_staked = sum(w.stake for w in wagers)
    pending_staked = sum(w.stake for w in wagers if w.status == "PENDING")

    realized_profit = 0.0
    settled_count = 0
    won_count = 0
    total_theoretical_ev_dollars = 0.0

    for w in wagers:
        total_theoretical_ev_dollars += (w.stake * w.expected_value)
        if w.status == "WON":
            realized_profit += (w.potential_payout - w.stake)
            settled_count += 1
            won_count += 1
        elif w.status == "LOST":
            realized_profit -= w.stake
            settled_count += 1
        elif w.status == "PUSH":
            settled_count += 1

    current_bankroll = initial_bankroll + realized_profit - pending_staked
    win_rate = (won_count / settled_count * 100.0) if settled_count > 0 else 0.0

    return {
        "initial_bankroll": initial_bankroll,
        "current_cash": round(current_bankroll, 2),
        "pending_exposure": round(pending_staked, 2),
        "total_portfolio_value": round(current_bankroll + pending_staked, 2),
        "realized_profit": round(realized_profit, 2),
        "theoretical_ev_dollars": round(total_theoretical_ev_dollars, 2),
        "total_bets": len(wagers),
        "settled_bets": settled_count,
        "win_rate": round(win_rate, 1)
    }

# 2. Get All Wagers
@app.get("/api/wagers")
def get_wagers(db: Session = Depends(get_db)):
    return db.query(database.Wager).order_by(database.Wager.date_placed.desc()).all()

# 3. Add a New Wager
@app.post("/api/wagers")
def add_wager(bet: BetCreate, db: Session = Depends(get_db)):
    new_wager = database.Wager(
        event_name=bet.event_name,
        fighter_selected=bet.fighter_selected,
        opponent=bet.opponent,
        sportsbook=bet.sportsbook,
        odds_placed=bet.odds_placed,
        stake=bet.stake,
        potential_payout=bet.potential_payout,
        expected_value=bet.expected_value,
        status="PENDING"
    )
    db.add(new_wager)
    db.commit()
    db.refresh(new_wager)
    return new_wager

# 4. Settle a Wager
@app.put("/api/wagers/{bet_id}/settle")
def settle_wager(bet_id: int, payload: BetSettle, db: Session = Depends(get_db)):
    wager = db.query(database.Wager).filter(database.Wager.id == bet_id).first()
    if not wager:
        raise HTTPException(status_code=404, detail="Wager not found")

    valid_statuses = ["WON", "LOST", "PUSH", "PENDING"]
    status_upper = payload.status.upper()
    if status_upper not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")

    wager.status = status_upper
    db.commit()
    return {"status": "success", "bet_id": bet_id, "new_status": status_upper}

# 5. Live +EV Scanner
@app.get("/api/scan_ev")
def scan_live_ev(bankroll: float = 200.0, min_ev: float = 0.01):
    try:
        raw_bouts = scraper.scrape_bestfightodds()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraper error: {str(e)}")

    flagged_bets = []

    for bout in raw_bouts:
        f1 = bout["fighter_1"]
        f2 = bout["fighter_2"]
        odds_dict = bout["odds"]

        # Identify sharp benchmark
        benchmark_name = None
        sharp_o1 = None
        sharp_o2 = None

        for bm in ["Pinnacle", "Circa", "Polymarket"]:
            matched_key = next((k for k in odds_dict.keys() if bm.lower() in k.lower()), None)
            if matched_key:
                benchmark_name = bm
                sharp_o1 = odds_dict[matched_key]["f1_odds"]
                sharp_o2 = odds_dict[matched_key]["f2_odds"]
                break

        if not benchmark_name or sharp_o1 is None or sharp_o2 is None:
            continue

        p1, p2, fair1, fair2 = engine.devig_multiplicative(sharp_o1, sharp_o2)

        for book_name, book_prices in odds_dict.items():
            if benchmark_name.lower() in book_name.lower():
                continue

            o1 = book_prices.get("f1_odds")
            o2 = book_prices.get("f2_odds")

            if o1 is not None:
                ev1 = engine.calculate_ev(p1, o1)
                if ev1 >= min_ev:
                    stake_sug = engine.calculate_kelly_stake(bankroll, p1, o1, fraction=0.25)
                    rationale = ai_analyst.generate_ev_rationale(f1, f2, book_name, o1, fair1, ev1, benchmark_name)
                    flagged_bets.append({
                        "fighter": f1,
                        "opponent": f2,
                        "book": book_name,
                        "offered_odds": o1,
                        "benchmark": benchmark_name,
                        "benchmark_line": f"{sharp_o1:+d} / {sharp_o2:+d}",
                        "fair_odds": fair1,
                        "ev_pct": round(ev1 * 100.0, 2),
                        "suggested_stake": stake_sug,
                        "rationale": rationale
                    })

            if o2 is not None:
                ev2 = engine.calculate_ev(p2, o2)
                if ev2 >= min_ev:
                    stake_sug = engine.calculate_kelly_stake(bankroll, p2, o2, fraction=0.25)
                    rationale = ai_analyst.generate_ev_rationale(f2, f1, book_name, o2, fair2, ev2, benchmark_name)
                    flagged_bets.append({
                        "fighter": f2,
                        "opponent": f1,
                        "book": book_name,
                        "offered_odds": o2,
                        "benchmark": benchmark_name,
                        "benchmark_line": f"{sharp_o2:+d} / {sharp_o1:+d}",
                        "fair_odds": fair2,
                        "ev_pct": round(ev2 * 100.0, 2),
                        "suggested_stake": stake_sug,
                        "rationale": rationale
                    })

    return {"count": len(flagged_bets), "bets": flagged_bets}

# 6. Manual De-Vig Calculator
@app.post("/api/calculate_custom")
def calculate_custom(req: CustomDevigRequest):
    p_a, p_b, fair_a, fair_b = engine.devig_multiplicative(req.sharp_odds_a, req.sharp_odds_b)
    ev = engine.calculate_ev(p_a, req.offered_odds)
    stake = engine.calculate_kelly_stake(req.bankroll, p_a, req.offered_odds, fraction=0.25)

    return {
        "true_prob_a": round(p_a * 100.0, 2),
        "true_prob_b": round(p_b * 100.0, 2),
        "fair_odds_a": fair_a,
        "fair_odds_b": fair_b,
        "ev_pct": round(ev * 100.0, 2),
        "quarter_kelly_stake": stake
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
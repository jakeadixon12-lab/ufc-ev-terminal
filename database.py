from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./ufc_betting.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Wager(Base):
    __tablename__ = "wagers"
    id = Column(Integer, primary_key=True, index=True)
    event_name = Column(String)
    fighter_selected = Column(String)
    opponent = Column(String)
    sportsbook = Column(String)
    odds_placed = Column(Integer)        # e.g. +250
    stake = Column(Float)                # e.g. 3.00
    potential_payout = Column(Float)     # e.g. 10.50
    expected_value = Column(Float)       # e.g. 0.0402 (+4.02%)
    closing_odds = Column(Integer, nullable=True) # Final benchmark line
    clv_percentage = Column(Float, nullable=True) # Closing line value %
    status = Column(String, default="PENDING")    # PENDING, WON, LOST, PUSH
    date_placed = Column(DateTime, default=datetime.utcnow)

class ScrapedOdds(Base):
    __tablename__ = "scraped_odds"
    id = Column(Integer, primary_key=True, index=True)
    event_name = Column(String)
    fighter_name = Column(String)
    opponent_name = Column(String)
    sportsbook = Column(String)
    moneyline = Column(Integer)
    is_closing_line = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Pre-seed your 3 active bets if the table is empty
    if db.query(Wager).count() == 0:
        seed_wagers = [
            Wager(
                event_name="UFC Fight Night: Moicano vs. Nolan",
                fighter_selected="Nick Klein",
                opponent="Joe Kropschot",
                sportsbook="Caesars",
                odds_placed=250,
                stake=3.00,
                potential_payout=10.50,
                expected_value=0.0402,
                status="PENDING"
            ),
            Wager(
                event_name="UFC Fight Night: Moicano vs. Nolan",
                fighter_selected="Nick Klein (Promo Boost)",
                opponent="Joe Kropschot",
                sportsbook="Caesars",
                odds_placed=500,  # Effective odds for $2 -> $12
                stake=2.00,
                potential_payout=12.00,
                expected_value=0.7832,
                status="PENDING"
            ),
            Wager(
                event_name="UFC Fight Night: Moicano vs. Nolan",
                fighter_selected="Dakota Hope",
                opponent="Francis Marshall",
                sportsbook="FanDuel",
                odds_placed=215,
                stake=4.00,
                potential_payout=12.60,
                expected_value=0.0288,
                status="PENDING"
            )
        ]
        db.add_all(seed_wagers)
        db.commit()
        print("Database initialized and 3 active wagers pre-seeded!")
    else:
        print("Database already initialized.")
    db.close()

if __name__ == "__main__":
    init_db()
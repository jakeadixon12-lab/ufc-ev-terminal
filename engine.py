import math

def american_to_implied_prob(odds: int) -> float:
    """Converts American odds (+150, -200) to implied probability (0.0 to 1.0)."""
    if odds > 0:
        return 100.0 / (odds + 100.0)
    elif odds < 0:
        return abs(odds) / (abs(odds) + 100.0)
    raise ValueError("Odds cannot be zero.")

def implied_prob_to_american(prob: float) -> int:
    """Converts a probability (0.0 to 1.0) back into fair American odds."""
    if not (0.0 < prob < 1.0):
        raise ValueError("Probability must be strictly between 0 and 1.")
    if prob >= 0.5:
        return int(round(-((prob / (1.0 - prob)) * 100.0)))
    else:
        return int(round(((1.0 - prob) / prob) * 100.0))

def american_to_decimal_payout(odds: int) -> float:
    """Calculates gross return multiplier (stake + profit per $1 staked)."""
    if odds > 0:
        return (odds / 100.0) + 1.0
    elif odds < 0:
        return (100.0 / abs(odds)) + 1.0
    raise ValueError("Odds cannot be zero.")

def devig_multiplicative(sharp_odds_a: int, sharp_odds_b: int) -> tuple[float, float, int, int]:
    """
    Strips the vig from a 2-way sharp market (e.g. Pinnacle or Circa).
    Returns: (fair_prob_a, fair_prob_b, fair_american_a, fair_american_b)
    """
    raw_a = american_to_implied_prob(sharp_odds_a)
    raw_b = american_to_implied_prob(sharp_odds_b)
    total_vig = raw_a + raw_b

    fair_prob_a = raw_a / total_vig
    fair_prob_b = raw_b / total_vig

    fair_odds_a = implied_prob_to_american(fair_prob_a)
    fair_odds_b = implied_prob_to_american(fair_prob_b)

    return fair_prob_a, fair_prob_b, fair_odds_a, fair_odds_b

def calculate_ev(true_prob: float, offered_odds: int) -> float:
    """
    EV = (True Probability * Decimal Payout) - 1.0
    Returns EV as a decimal (e.g., 0.052 for +5.20%).
    """
    decimal_payout = american_to_decimal_payout(offered_odds)
    return (true_prob * decimal_payout) - 1.0

def calculate_kelly_stake(bankroll: float, true_prob: float, offered_odds: int, fraction: float = 0.25) -> float:
    """
    Calculates stake based on Fractional Kelly Criterion.
    Default fraction is 0.25 (Quarter-Kelly) to protect a small bankroll against downswings.
    """
    # Net decimal odds (b) is payout minus 1
    b = (offered_odds / 100.0) if offered_odds > 0 else (100.0 / abs(offered_odds))
    p = true_prob
    q = 1.0 - p

    full_kelly = (b * p - q) / b

    if full_kelly <= 0:
        return 0.0

    target_stake = bankroll * (full_kelly * fraction)
    # Return rounded to 2 decimal places, with a $1.00 minimum if EV is positive
    return max(1.00, round(target_stake, 2))

def calculate_clv(wager_odds: int, closing_odds: int) -> float:
    """
    Calculates Closing Line Value (CLV%):
    Compares the price you got vs. the final closing price.
    Positive CLV means you beat the closing market.
    """
    p_wager = american_to_decimal_payout(wager_odds)
    p_close = american_to_decimal_payout(closing_odds)
    return (p_wager / p_close) - 1.0

if __name__ == "__main__":
    # Self-test using Dakota Hope (+230 vs Pinnacle -242/+202)
    p_marsh, p_hope, fair_marsh, fair_hope = devig_multiplicative(-242, 202)
    ev_hope = calculate_ev(p_hope, 230)
    stake = calculate_kelly_stake(200.0, p_hope, 230, fraction=0.25)

    print(f"Fair Prob Hope: {p_hope*100:.2f}% (Fair Line: {fair_hope:+d})")
    print(f"Calculated EV at +230: {ev_hope*100:+.2f}%")
    print(f"Quarter-Kelly Stake ($200 roll): ${stake:.2f}")
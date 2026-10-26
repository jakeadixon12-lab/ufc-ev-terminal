import os
from google import genai
from google.genai import errors

def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None

def generate_ev_rationale(
    fighter: str,
    opponent: str,
    sportsbook: str,
    offered_odds: int,
    fair_odds: int,
    ev_percentage: float,
    benchmark_name: str = "Pinnacle"
) -> str:
    """
    Generates a concise quantitative rationale explaining why a wager is +EV.
    Falls back to a local algorithmic string if the Gemini API is unreachable or not configured.
    """
    client = get_gemini_client()
    
    # Fallback template if GEMINI_API_KEY is missing or offline
    fallback_text = (
        f"{fighter} at {offered_odds:+d} on {sportsbook} offers a +{ev_percentage*100:.2f}% mathematical edge. "
        f"{sportsbook}'s price diverges from {benchmark_name}'s no-vig fair value ({fair_odds:+d}), "
        f"indicating a lagging retail line against sharp consensus."
    )
    
    if not client:
        return fallback_text

    prompt = f"""
You are an expert quantitative sports betting analyst specializing in MMA and UFC pricing models.
A wager has been flagged by our pricing engine as mathematically Positive Expected Value (+EV):

- Matchup: {fighter} vs. {opponent}
- Sportsbook Offering Bet: {sportsbook} at {offered_odds:+d}
- Sharp Market Benchmark: {benchmark_name} (De-vigged fair price is {fair_odds:+d})
- Positive EV Edge: +{ev_percentage * 100:.2f}%

Provide a concise, direct 2-to-3 sentence explanation covering:
1. The mathematical divergence between the retail book and the sharp market-maker benchmark.
2. The market dynamic causing it (e.g., retail sportsbook lagging line movement, shading toward public favorites, or DWCS/prelim mispricing).
Do not use conversational fluff. Be objective, precise, and professional.
"""
    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt
        )
        return response.text.strip()
    except errors.APIError:
        try:
            fallback_response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            return fallback_response.text.strip()
        except Exception as e:
            return fallback_text + f" (AI detail unavailable: {str(e)})"
    except Exception as e:
        return fallback_text + f" (AI detail unavailable: {str(e)})"

if __name__ == "__main__":
    print("Testing AI Analyst module...")
    test_rationale = generate_ev_rationale(
        fighter="Dakota Hope",
        opponent="Francis Marshall",
        sportsbook="FanDuel",
        offered_odds=215,
        fair_odds=206,
        ev_percentage=0.0288,
        benchmark_name="Polymarket/Pinnacle"
    )
    print("\nResult Rationale:")
    print(test_rationale)
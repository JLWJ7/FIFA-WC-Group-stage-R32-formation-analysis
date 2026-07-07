"""
Scrape group-stage and Round-of-32 formations (home & away) for the
FIFA World Cup 2026 from SofaScore's internal API.

Output: wc2026_group_formations.csv

Run:
    uv venv --python 3.10.18
    .venv\\Scripts\\activate          # Windows
    uv pip install curl_cffi
    python wc2026_formations.py

Notes:
- SofaScore is behind Cloudflare. `curl_cffi` impersonates a real Chrome
  browser so the API stops returning 403. Plain `requests` will NOT work.
- This keeps GROUP STAGE and ROUND OF 32 games, and filters out the
  later knockout rounds (R16, QF, SF, Final).
- Scraping SofaScore is against their ToS; keep volume low and personal.
"""

import csv
import sys
import time

try:
    from curl_cffi import requests          # pip install curl_cffi
except ImportError:
    sys.exit("Missing dependency. Run:  uv pip install curl_cffi")

TOURNAMENT_ID = 16        # FIFA World Cup (unique-tournament id)
SEASON_ID = 58210         # 2026 edition
BASE = "https://api.sofascore.com/api/v1"
DELAY = 1.0               # seconds between requests — be polite
OUT = "wc2026_group_r32_formations.csv"

# SofaScore names each knockout round in `roundInfo.name`. Note that its
# `cupRoundType` field is the number of *matches* in the round (16 for the
# Round of 32, 8 for the R16, ...), NOT the number of teams — so we match
# on the name, which is unambiguous.
R32_ROUND_NAME = "Round of 32"


def get(url):
    """GET a SofaScore JSON endpoint while impersonating Chrome."""
    r = requests.get(url, impersonate="chrome", timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def all_season_events():
    """Yield every event in the season by walking the paginated feeds."""
    for feed in ("last", "next"):          # past + upcoming
        page = 0
        while True:
            url = f"{BASE}/unique-tournament/{TOURNAMENT_ID}/season/{SEASON_ID}/events/{feed}/{page}"
            data = get(url)
            if not data or not data.get("events"):
                break
            yield from data["events"]
            if not data.get("hasNextPage"):
                break
            page += 1
            time.sleep(DELAY)


def stage_of(event):
    """
    Classify an event's stage.

    Group-stage games have a plain matchday round with no `cupRoundType`
    and no round `name`. Knockout games carry a `name` (e.g. "Round of 32",
    "Round of 16", ...); the 3rd-place match is named but has no
    `cupRoundType`, so keying off `name` alone keeps it out of the group set.

    Returns "group", "R32", or None (for rounds we don't want).
    """
    round_info = event.get("roundInfo") or {}
    if round_info.get("name") == R32_ROUND_NAME:
        return "R32"
    if "cupRoundType" not in round_info and not round_info.get("name"):
        return "group"
    return None


def formations(event_id):
    """Return (home_formation, away_formation) or (None, None) if unconfirmed."""
    data = get(f"{BASE}/event/{event_id}/lineups")
    if not data or not data.get("confirmed", False):
        return None, None
    home = (data.get("home") or {}).get("formation")
    away = (data.get("away") or {}).get("formation")
    return home, away


def main():
    rows = []
    print("Fetching season events...")
    events = [(stage, e) for e in all_season_events()
              if (stage := stage_of(e)) is not None]
    print(f"Found {len(events)} group-stage + R32 events. Fetching lineups...")

    for stage, e in events:
        eid = e["id"]
        home_team = e["homeTeam"]["name"]
        away_team = e["awayTeam"]["name"]
        group = (e.get("roundInfo") or {}).get("name", "")

        # --- result / winner ---
        # winnerCode: 1 = home win, 2 = away win, 3 = draw, None = not played
        wc = e.get("winnerCode")
        home_score = (e.get("homeScore") or {}).get("current", "")
        away_score = (e.get("awayScore") or {}).get("current", "")
        status_type = (e.get("status") or {}).get("type", "")  # "finished" when done
        winner = {1: home_team, 2: away_team, 3: "Draw"}.get(wc, "")

        try:
            hf, af = formations(eid)
        except Exception as exc:
            print(f"  ! {home_team} vs {away_team} (id {eid}): {exc}")
            hf = af = None

        lineup_state = "ok" if hf and af else "no lineup"
        score_str = f"{home_score}-{away_score}" if status_type == "finished" else "TBD"
        print(f"  [{stage}] {home_team} {hf or '-'} {score_str} {af or '-'} {away_team}"
              f"  [{lineup_state} | winner: {winner or '-'}]")

        rows.append({
            "event_id": eid,
            "stage": stage,
            "group": group,
            "status": status_type,
            "home_team": home_team,
            "home_formation": hf or "",
            "home_score": home_score,
            "away_team": away_team,
            "away_formation": af or "",
            "away_score": away_score,
            "winner": winner,
        })
        time.sleep(DELAY)

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
    
    
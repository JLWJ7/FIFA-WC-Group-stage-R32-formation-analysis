"""
Analyse WC2026 group-stage formations from wc2026_group_formations.csv
(produced by wc2026_formations.py) using Plotly horizontal bar charts.

Produces a single interactive file: wc2026_dashboard.html with 4 charts:
  1. Total formation usage (both teams)
  2. Usage split by home vs away
  3. Win rate (%) per formation
  4. Average goals scored vs conceded per formation

Run:
    uv pip install pandas plotly
    python wc2026_analyse.py
Then open wc2026_dashboard.html in your browser.
"""

import sys
import pandas as pd
import plotly.graph_objects as go

CSV = "wc2026_group_r32_formations.csv"
OUT = "wc2026_dashboard.html"

BLUE, ORANGE, GREEN, RED = "#2a6fdb", "#db6b2a", "#2aa860", "#d6453d"


def load_usages(path):
    """
    Explode each finished match into two usage records (home + away side),
    each with that team's formation, outcome, goals for and goals against.
    """
    df = pd.read_csv(path).fillna("")
    df = df[df["status"] == "finished"].copy()

    records = []
    for _, r in df.iterrows():
        try:
            hs, as_ = int(r["home_score"]), int(r["away_score"])
        except (ValueError, TypeError):
            continue
        for side in ("home", "away"):
            formation = str(r[f"{side}_formation"]).strip()
            if not formation:
                continue
            team = r[f"{side}_team"]
            gf, ga = (hs, as_) if side == "home" else (as_, hs)
            if r["winner"] == "Draw":
                outcome = "draw"
            elif r["winner"] == team:
                outcome = "win"
            else:
                outcome = "loss"
            records.append({"side": side, "formation": formation,
                            "outcome": outcome, "gf": gf, "ga": ga})

    if not records:
        sys.exit("No finished games with formations found. "
                 "Run the scraper after group-stage matches have results.")
    return pd.DataFrame(records)


def summarise(u):
    total = u["formation"].value_counts().rename("total")

    split = (u.groupby(["formation", "side"]).size()
             .unstack(fill_value=0)
             .reindex(columns=["home", "away"], fill_value=0))

    outcomes = (u.groupby(["formation", "outcome"]).size()
                .unstack(fill_value=0)
                .reindex(columns=["win", "draw", "loss"], fill_value=0))
    outcomes["games"] = outcomes.sum(axis=1)
    outcomes["win_rate"] = (outcomes["win"] / outcomes["games"] * 100).round(1)

    goals = u.groupby("formation").agg(avg_scored=("gf", "mean"),
                                       avg_conceded=("ga", "mean")).round(2)
    return total, split, outcomes, goals


def h_order(index_values):
    """Return list so the largest bar sits at the TOP of a horizontal chart."""
    return list(index_values)[::-1]


def fig_total(total):
    t = total.sort_values(ascending=True)  # ascending -> largest at top
    fig = go.Figure(go.Bar(
        x=t.values, y=t.index, orientation="h", marker_color=BLUE,
        text=t.values, textposition="outside",
        hovertemplate="%{y}: %{x} uses<extra></extra>"))
    fig.update_layout(title="Total formation usage — WC2026 group stage + R32",
                      xaxis_title="Times used (both teams)",
                      yaxis_title="Formation", height=450)
    return fig


def fig_home_away(split):
    order = split.sum(axis=1).sort_values(ascending=True).index
    s = split.loc[order]
    fig = go.Figure()
    fig.add_bar(y=s.index, x=s["home"], name="Home", orientation="h",
                marker_color=BLUE,
                hovertemplate="%{y} home: %{x}<extra></extra>")
    fig.add_bar(y=s.index, x=s["away"], name="Away", orientation="h",
                marker_color=ORANGE,
                hovertemplate="%{y} away: %{x}<extra></extra>")
    fig.update_layout(title="Formation usage: home vs away",
                      barmode="group", xaxis_title="Times used",
                      yaxis_title="Formation", height=500,
                      legend_title="Side")
    return fig


def fig_win_rate(outcomes):
    o = outcomes.sort_values("win_rate", ascending=True)
    labels = [f"{wr:.0f}%  (W{int(w)}-D{int(d)}-L{int(l)})"
              for wr, w, d, l in zip(o["win_rate"], o["win"], o["draw"], o["loss"])]
    fig = go.Figure(go.Bar(
        x=o["win_rate"], y=o.index, orientation="h", marker_color=GREEN,
        text=labels, textposition="outside",
        customdata=o[["win", "draw", "loss", "games"]].values,
        hovertemplate=("%{y}<br>Win rate: %{x:.1f}%<br>"
                       "W%{customdata[0]} D%{customdata[1]} L%{customdata[2]} "
                       "(%{customdata[3]} games)<extra></extra>")))
    fig.update_layout(title="Win rate by formation - WC2026 group stage + R32",
                      xaxis_title="Win rate (%)", xaxis_range=[0, 100],
                      yaxis_title="Formation", height=500)
    return fig


def fig_goals(goals):
    g = goals.sort_values("avg_scored", ascending=True)
    fig = go.Figure()
    fig.add_bar(y=g.index, x=g["avg_scored"], name="Avg scored", orientation="h",
                marker_color=GREEN,
                hovertemplate="%{y}: %{x:.2f} scored/game<extra></extra>")
    fig.add_bar(y=g.index, x=g["avg_conceded"], name="Avg conceded", orientation="h",
                marker_color=RED,
                hovertemplate="%{y}: %{x:.2f} conceded/game<extra></extra>")
    fig.update_layout(title="Average goals scored vs conceded per formation",
                      barmode="group", xaxis_title="Goals per game",
                      yaxis_title="Formation", height=500,
                      legend_title="")
    return fig


def main():
    u = load_usages(CSV)
    total, split, outcomes, goals = summarise(u)

    print("\n=== Total usage ===\n", total.to_string())
    print("\n=== Home vs Away ===\n", split.to_string())
    print("\n=== Outcomes & win rate ===\n", outcomes.to_string())
    print("\n=== Avg goals ===\n", goals.to_string())

    figs = [fig_total(total), fig_home_away(split),
            fig_win_rate(outcomes), fig_goals(goals)]

    # Write all four charts into one self-contained HTML file
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("<html><head><meta charset='utf-8'>"
                "<title>WC2026 formation analysis</title></head><body>")
        for i, fig in enumerate(figs):
            f.write(fig.to_html(full_html=False,
                                include_plotlyjs="cdn" if i == 0 else False))
        f.write("</body></html>")

    print(f"\nSaved interactive dashboard -> {OUT}")


if __name__ == "__main__":
    main()
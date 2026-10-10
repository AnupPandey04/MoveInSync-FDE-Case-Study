"""
MoveInSync Play Store review pipeline (v2)
Author: Anup Pandey (Reg. no. 12310363)

Answers "How are our Play Store ratings?" on demand. Re-run weekly.
  1. Collects the newest public reviews from the official Play listing
  2. Tags each review with one or more themes (keyword rules, multi-label)
  3. Writes: reviews_tagged.csv, monthly_summary.csv, theme_summary.csv, weekly_report.md

Setup:   pip install google-play-scraper pandas tabulate
Run:     python review_pipeline_v2.py                 (uses PACKAGE_ID below)
         python review_pipeline_v2.py com.some.app    (override the package)
         python review_pipeline_v2.py --find          (search the Play Store for candidates)

Changes from v1: fixed two rule bugs ("hang" matched "changes"; login OTP was counted as
check-in), added themes found while reading reviews (cab allocation/pooling, forced prompts,
session expiry, driver conduct), and split untagged reviews into "generic negative" vs "other".
Keyword tags are a first pass: spot-check ~50 tags each week.
"""
import re
import sys
from datetime import datetime, timezone

import pandas as pd
from google_play_scraper import Sort, reviews, search, app as app_info

PACKAGE_ID = "com.moveinsync.ets"   # verified: listing shows 4.64 stars / ~115K ratings
MAX_REVIEWS = 3000
LANG, COUNTRY = "en", "in"

THEMES = {
    "Location / ETA / tracking": r"\bgps\b|location|track|\beta\b|live (location|tracking)|wrong (time|location)|\bmap\b|late\b|delay|pick-?up time|arriv(al|ing|es)? time|timing|on time|real[- ]?time|not updat",
    "Booking & trip changes": r"\bbook|schedule|roster|shuttle|confirm|cancel|ride option|wrong date|edit option|no edit|can'?t (edit|change)|change (the )?address",
    "Cab allocation / routing / pooling": r"assign|allocat|\bclub|pooling|\bpool\b|routing|\broute|seater|fills? \d|no (cab|vehicle)|cab (not|never|didn)|not (come|coming|showed)|did ?n'?t (come|show)|never (picked|come)",
    "Notifications": r"notif|reminder|\balert|alarm|\bping",
    "Check-in / no-show / QR": r"no[- ]?show|check[- ]?in|\breached\b|boarding|marked (absent|no)|missed (the )?(cab|pickup)|unable to scan|\bqr\b|\bscan",
    "Login / OTP / session": r"login|log in|logs? ?out|logging out|sign in|password|\bsso\b|verification|session|\botp\b",
    "Crash / won't open / performance": r"crash|\bhang|freez|(not|n't|unable to|cannot|can ?not) (be )?(open|opens|opening|install|access|load)|doesn'?t (open|load)|closes|white screen|\blag|loading|\bbug|glitch|not working|\berror\b|app (is )?down|application is down|downtime|very slow|stuck",
    "Usability / UI changes": r"confus|difficult|complicated|\bui\b|\bux\b|design|interface|hard to use|user[- ]friendly|new (version|update|flow)|update(s|d)? (and|but|made)|frequent(ly)? updat|navigation",
    "Forced prompts (rating/policy/permissions)": r"permission|microphone|privacy|policy|policies|\bagree|terms|rate every|forced? (me )?to (give )?rat|mandatory review|asks? for (a )?(review|feedback)|asking for feedback|rating after",
    "Driver conduct & safety": r"\bsafe|safety|\bsos\b|driver.{0,40}(rude|rash|abusive|behav|speed|unprofessional)|abusive|harass|unsafe|women|goons",
    "Support / ops management": r"support|customer care|no response|helpdesk|help option|coordination|management|transport team|complain",
}
COMPILED = {k: re.compile(v, re.I) for k, v in THEMES.items()}


def tag(text: str):
    text = text or ""
    hits = [k for k, rx in COMPILED.items() if rx.search(text)]
    if hits:
        return hits
    return ["Generic negative (no detail)"] if len(text.split()) <= 8 else ["Other / unclassified"]


def find_candidates():
    for r in search("MoveInSync", lang=LANG, country=COUNTRY, n_hits=10):
        print(r["appId"], "|", r["title"], "|", r.get("developer"), "|", r.get("score"))


def collect(pkg):
    info = app_info(pkg, lang=LANG, country=COUNTRY)
    print(f"Listing: {info['title']} | score {info['score']:.2f} | ratings {info['ratings']:,} | "
          f"histogram (1..5 stars): {info['histogram']}")
    rows, token = [], None
    while len(rows) < MAX_REVIEWS:
        batch, token = reviews(pkg, lang=LANG, country=COUNTRY, sort=Sort.NEWEST,
                               count=200, continuation_token=token)
        rows += batch
        if not token or not batch:
            break
    return info, pd.DataFrame(rows)


def main():
    if "--find" in sys.argv:
        find_candidates()
        return
    pkg = next((a for a in sys.argv[1:] if not a.startswith("--")), PACKAGE_ID)
    info, df = collect(pkg)
    if df.empty:
        print("No reviews returned. Check the package id (run with --find).")
        return

    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
    df = df.rename(columns={"at": "date", "score": "rating", "content": "text",
                            "reviewCreatedVersion": "app_version"})
    df["date"] = pd.to_datetime(df["date"])
    df["themes"] = df["text"].apply(tag)
    df["themes_str"] = df["themes"].apply("|".join)
    df["retrieved_at"] = retrieved
    df["month"] = df["date"].dt.to_period("M").astype(str)

    cols = ["date", "rating", "text", "app_version", "themes_str", "thumbsUpCount", "retrieved_at"]
    df[[c for c in cols if c in df.columns]].to_csv("reviews_tagged.csv", index=False)

    monthly = df.groupby("month").agg(
        reviews=("rating", "size"),
        avg_rating=("rating", "mean"),
        pct_1_2_star=("rating", lambda s: (s <= 2).mean() * 100),
    ).round(2)
    monthly.to_csv("monthly_summary.csv")

    low = df[df["rating"] <= 2]
    theme_low = low.explode("themes").groupby("themes").size().sort_values(ascending=False)
    theme_all = df.explode("themes").groupby("themes").size()
    theme_summary = pd.DataFrame({
        "low_star_reviews": theme_low,
        "pct_of_low_star": (theme_low / max(len(low), 1) * 100).round(1),
        "all_reviews": theme_all,
    }).fillna(0)
    theme_summary["pct_of_theme_that_is_low_star"] = (
        theme_summary["low_star_reviews"] / theme_summary["all_reviews"].replace(0, pd.NA) * 100).round(1)
    theme_summary.to_csv("theme_summary.csv")

    last28 = df[df["date"] >= df["date"].max() - pd.Timedelta(days=28)]
    last7 = df[df["date"] >= df["date"].max() - pd.Timedelta(days=7)]
    with open("weekly_report.md", "w", encoding="utf-8") as f:
        f.write(f"# Play Store weekly report\nRetrieved: {retrieved}\n\n")
        f.write(f"Listing: {info['title']} ({pkg}) | overall {info['score']:.2f} | {info['ratings']:,} ratings\n")
        f.write(f"Star histogram (1..5): {info['histogram']}\n\n")
        f.write(f"Sample: {len(df)} newest reviews ({df['date'].min().date()} to {df['date'].max().date()})\n")
        f.write(f"Last 7d: {len(last7)} reviews, avg {last7['rating'].mean():.2f}, {(last7['rating']<=2).mean()*100:.1f}% 1-2 star\n")
        f.write(f"Last 28d: {len(last28)} reviews, avg {last28['rating'].mean():.2f}, {(last28['rating']<=2).mean()*100:.1f}% 1-2 star\n\n")
        f.write("## Themes in 1-2 star reviews (multi-label)\n")
        f.write(theme_summary.sort_values("low_star_reviews", ascending=False).to_markdown() + "\n\n")
        f.write("## Monthly trend\n" + monthly.to_markdown() + "\n")
    print("Wrote reviews_tagged.csv, monthly_summary.csv, theme_summary.csv, weekly_report.md")
    print("Next: spot-check ~50 tagged reviews, compare themes with last week, and open a ticket per rising theme.")


if __name__ == "__main__":
    main()

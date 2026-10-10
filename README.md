# MoveInSync Play Store rating analysis

Candidate assignment for the MoveInSync Forward Deployed Engineer role (Drive TC.21569.2027.64403).
Author: Anup Pandey, Reg. no. 12310363.

**Question:** Why are the app's Play Store ratings where they are, and what should be fixed first?

## Start here

- `MoveInSync_FDE_Case_Study_Anup_Pandey.pdf` is the 4-page recommendation: findings, prioritised fixes, execution plan, scorecard, method and limits.

## What I found (short version)

- The listing (`com.moveinsync.ets`) shows 4.64 stars from 114,857 ratings. Only 7.1% of all-time ratings are 1 or 2 stars.
- Among the 3,000 newest written reviews, 27.2% are 1 or 2 stars. Written reviews skew negative, so this shows what unhappy users complain about, not how large the problem is.
- Of 815 low-star reviews, 26.6% cite the app failing to open or log in (OTP not arriving, forced logouts, crashes). Location/ETA (16.0%) and booking (13.6%) follow.
- The share of low-star reviews is flat over 13 months, so this is a chronic issue and not a recent regression.
- About 17% of low-star reviews concern service quality (allocation, pooling, drivers, support) rather than the app.

## Repeatable pipeline

The assignment says the ratings question will be asked repeatedly, so the analysis is a script.

```
pip install google-play-scraper pandas tabulate
python review_pipeline_v2.py                  # collect, tag, summarise
python review_pipeline_v2.py --find           # search the Play Store for the package id
```

It writes `reviews_tagged.csv`, `monthly_summary.csv`, `theme_summary.csv` and `weekly_report.md`.
Tagging uses keyword rules with multiple labels per review. They are a first pass: spot-check about 50 tags each week.

## Files in `sample_output/`

Output from the run on 10 Oct 2026 (3,000 newest English reviews from the India store, 21 Sep 2025 to 9 Oct 2026).

## Limits

- Written reviews are not representative of all users.
- Keyword tags were checked by hand on about 100 reviews; tag accuracy was not measured formally.
- English reviews on the India store only. No access to telemetry, support tickets or transport logs, so no causal claims.

## Tools

google-play-scraper, pandas, matplotlib, reportlab. Claude (an AI assistant) helped draft the script and the report wording; all figures come from the scraped data.

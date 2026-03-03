#!/usr/bin/env python3
"""
Epic Fury Dashboard Auto-Updater
Runs on a schedule via GitHub Actions. Searches for latest news,
calls Claude to update the HTML, then the workflow commits it back.
"""

import os
import re
import datetime
import anthropic

# ── Config ────────────────────────────────────────────────────────────────────
HTML_FILE = "dashboards/iran-israel-conflict-dashboards.html"
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16000
SEARCH_QUERIES = [
    "Operation Epic Fury Iran Israel latest updates today",
    "Iran war casualties killed injured 2026",
    "CENTCOM Iran operation targets struck update",
    "IDF intercepts missiles drones Iron Dome David's Sling today",
    "Iran missiles launched Gulf states intercepts today",
    "Hezbollah Israel Lebanon strikes today",
    "Iran US war ceasefire negotiations leadership 2026",
    "Gulf states air defense UAE Kuwait Bahrain Qatar intercepts Iran",
]
# ──────────────────────────────────────────────────────────────────────────────

def load_html() -> str:
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        return f.read()

def save_html(content: str) -> None:
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(content)

def build_update_prompt(html: str, timestamp: str) -> str:
    return f"""You are updating a live conflict dashboard HTML file tracking the Iran-Israel-US war (Operation Epic Fury / Operation Roaring Lion), which began February 28, 2026.

The current dashboard HTML is provided below. Your job is to find and update ALL of the following:

WHAT TO UPDATE:

1. TIMESTAMP - Update every occurrence of the current timestamp to: {timestamp}
   Also update the "AS OF [DATE]" span in the running totals section title.

2. TIMELINE ENTRIES - Add new entries for any events that occurred after the
   last dated entry in the HTML. New entries go BEFORE the comment that reads
   "PLACEHOLDER - keep for next update". Match existing entry structure exactly.
   Use data-fury: us-israel | iran | regional | diplomatic

3. RUNNING TOTALS STAT CARDS - Update all figures in the stats-grid div:
   - Iranian civilians killed (Red Crescent latest)
   - Iranian civilians injured
   - Israeli civilians killed
   - Israelis injured
   - US soldiers KIA (CENTCOM latest)
   - US soldiers seriously wounded
   - Targets struck by US/Israel (CENTCOM cumulative)
   - Number of countries struck by Iran

4. HEADER HSTAT STRIP - The small hstat summary row near the top of the Epic
   Fury panel. Update each hstat-val for: US KIA, ships sunk, leaders killed,
   countries struck, targets hit, and any other figures shown there.

5. MISSILES PER DAY BAR CHARTS - There are two bar charts tracking daily
   launch counts:
   a) "Iranian missiles/drones launched per day" (red bars) - add a new bar-row
      for each new day if launch figures are available; update any bars marked
      "ongoing" or "tallying" with confirmed figures
   b) "US & Israeli strikes launched per day" (blue/gold bars) - same: add new
      day rows, update any "ongoing" bars with confirmed figures

6. INTERCEPTS BY PLATFORM - The bar chart showing intercepts broken down by
   system (Iron Dome, David's Sling, Arrow-3, Arrow-2, Barak-8, US Patriot/
   THAAD, Gulf state systems, etc.). Update bar widths and values if new
   cumulative intercept figures have been released by IDF, CENTCOM, or Gulf
   MoDs. If new per-system data is available, remove "TBD" or "PRELIMINARY"
   flags from those rows.

7. CONFIRMED LEADERSHIP KILLED - The context-card listing assassinated officials.
   Add any newly confirmed kills. Remove entries marked "unconfirmed" if
   confirmation has since been issued.

CRITICAL RULES:
- Return ONLY the complete, valid HTML file. No explanation, no markdown, no fences.
- Do NOT remove or alter existing entries - only ADD new entries and UPDATE numbers.
- Do NOT truncate the file. Return every single line.
- Only use figures you actually found via web search - do not invent numbers.
- If a figure is unavailable, leave it as-is or mark it "pending".
- If no new developments exist since the last entry, just update the timestamp
  and return the full HTML unchanged.
- The returned HTML must be complete and valid - same length or longer than input.

WEB SEARCH QUERIES TO RUN:
{chr(10).join(f"- {q}" for q in SEARCH_QUERIES)}

CURRENT HTML FILE:
{html}"""

def update_dashboard() -> None:
    now = datetime.datetime.now(datetime.UTC)
    print(f"[{now.isoformat()}] Starting Epic Fury dashboard update...")

    html = load_html()
    print(f"  Loaded: {HTML_FILE} ({len(html):,} chars)")

    timestamp = now.strftime("%B %-d, %Y · %H:%M UTC")

    prompt = build_update_prompt(html, timestamp)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print(f"  Calling {MODEL} with web search enabled...")
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    # Pull the text block out (Claude may have emitted tool-use blocks first)
    updated_html = ""
    for block in response.content:
        if block.type == "text":
            updated_html = block.text.strip()
            break

    # Strip accidental markdown fences
    updated_html = re.sub(r"^```html?\n?", "", updated_html, flags=re.MULTILINE).strip()
    updated_html = re.sub(r"\n?```\s*$", "", updated_html, flags=re.MULTILINE).strip()

    # Safety checks before writing
    if "<html" not in updated_html:
        print("  ERROR: Response does not look like HTML. Aborting.")
        print(f"  First 500 chars of response: {updated_html[:500]}")
        exit(1)

    if len(updated_html) < len(html) * 0.85:
        print(f"  ERROR: Response ({len(updated_html):,} chars) is >15% shorter than original ({len(html):,} chars). Aborting.")
        print(f"  First 500 chars of response: {updated_html[:500]}")
        exit(1)

    if updated_html == html:
        print("  No changes - dashboard already up to date.")
        exit(0)

    save_html(updated_html)
    print(f"  Saved updated HTML ({len(updated_html):,} chars)")
    print(f"  Timestamp: {timestamp}")

if __name__ == "__main__":
    update_dashboard()

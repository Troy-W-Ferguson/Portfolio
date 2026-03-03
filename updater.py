#!/usr/bin/env python3
"""
Epic Fury Dashboard Auto-Updater
Extracts only the Epic Fury panel from the HTML, sends it to Claude
for updating, then splices the result back into the full file.
This avoids timeout issues from sending/receiving the entire large HTML.
"""

import os
import re
import datetime
import anthropic

# ── Config ────────────────────────────────────────────────────────────────────
HTML_FILE = "dashboards/iran-israel-conflict-dashboards.html"
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16000
PANEL_START_MARKER = '<div class="panel" id="panel-epicfury">'
PANEL_END_MARKER = "</div><!-- /panel-epicfury -->"
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

def extract_panel(html: str) -> tuple[str, int, int]:
    """
    Pulls out just the Epic Fury panel div from the full HTML.
    Returns (panel_html, start_index, end_index).
    """
    start = html.find(PANEL_START_MARKER)
    end = html.find(PANEL_END_MARKER)

    if start == -1 or end == -1:
        raise ValueError(
            f"Could not find Epic Fury panel markers in HTML.\n"
            f"Looking for:\n  START: {PANEL_START_MARKER}\n  END: {PANEL_END_MARKER}"
        )

    end_full = end + len(PANEL_END_MARKER)
    panel_html = html[start:end_full]
    return panel_html, start, end_full

def splice_panel(full_html: str, new_panel: str, start: int, end: int) -> str:
    """
    Replaces the old panel section in the full HTML with the updated one.
    """
    return full_html[:start] + new_panel + full_html[end:]

def build_update_prompt(panel_html: str, timestamp: str) -> str:
    return f"""You are updating a single HTML panel — the Epic Fury tab of a live conflict dashboard tracking the Iran-Israel-US war (Operation Epic Fury / Operation Roaring Lion), which began February 28, 2026.

You will receive ONLY the Epic Fury panel div. Update it and return ONLY the updated panel div — nothing else before or after it.

WHAT TO UPDATE:

1. TIMESTAMP - Update every occurrence of the current timestamp to: {timestamp}
   Also update the "AS OF [DATE]" span in the running totals section title.

2. TIMELINE ENTRIES - Add new entries for any events that occurred after the
   last dated entry in the panel. New entries go BEFORE the comment that reads
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

4. HEADER HSTAT STRIP - The small hstat summary row near the top of the panel.
   Update each hstat-val for: US KIA, ships sunk, leaders killed, countries
   struck, targets hit, and any other figures shown there.

5. MISSILES PER DAY BAR CHARTS - Two bar charts tracking daily launch counts:
   a) "Iranian missiles/drones launched per day" (red bars) - add a new bar-row
      for each new day if figures are available; update bars marked "ongoing"
      or "tallying" with confirmed figures
   b) "US & Israeli strikes launched per day" (blue/gold bars) - same treatment

6. INTERCEPTS BY PLATFORM - Bar chart showing intercepts by system (Iron Dome,
   David's Sling, Arrow-3, Arrow-2, Barak-8, US Patriot/THAAD, Gulf systems).
   Update values if new figures released by IDF, CENTCOM, or Gulf MoDs.
   Remove "TBD" or "PRELIMINARY" flags where data is now confirmed.

7. CONFIRMED LEADERSHIP KILLED - The context-card listing assassinated officials.
   Add newly confirmed kills. Update any entries still marked "unconfirmed".

CRITICAL RULES:
- Return ONLY the panel HTML, starting with: <div class="panel" id="panel-epicfury">
- End with exactly: </div><!-- /panel-epicfury -->
- No explanation, no markdown fences, no text before or after the HTML.
- Do NOT remove or alter existing entries - only ADD and UPDATE.
- Do NOT truncate. Return the complete panel.
- Only use figures found via web search - do not invent numbers.
- If a figure is unavailable, leave it as-is or mark "pending".
- If no new developments exist, just update the timestamp and return unchanged.

WEB SEARCH QUERIES TO RUN:
{chr(10).join(f"- {q}" for q in SEARCH_QUERIES)}

CURRENT EPIC FURY PANEL:
{panel_html}"""

def update_dashboard() -> None:
    now = datetime.datetime.now(datetime.UTC)
    print(f"[{now.isoformat()}] Starting Epic Fury dashboard update...")

    full_html = load_html()
    print(f"  Loaded: {HTML_FILE} ({len(full_html):,} chars)")

    # Extract just the Epic Fury panel
    try:
        panel_html, panel_start, panel_end = extract_panel(full_html)
    except ValueError as e:
        print(f"  ERROR: {e}")
        exit(1)

    print(f"  Extracted Epic Fury panel ({len(panel_html):,} chars)")

    timestamp = now.strftime("%B %-d, %Y · %H:%M UTC")
    prompt = build_update_prompt(panel_html, timestamp)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print(f"  Calling {MODEL} with web search enabled...")
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    # Pull the text block out
    updated_panel = ""
    for block in response.content:
        if block.type == "text":
            updated_panel = block.text.strip()
            break

    # Strip accidental markdown fences
    updated_panel = re.sub(r"^```html?\n?", "", updated_panel, flags=re.MULTILINE).strip()
    updated_panel = re.sub(r"\n?```\s*$", "", updated_panel, flags=re.MULTILINE).strip()

    # Safety checks
    if PANEL_START_MARKER not in updated_panel:
        print("  ERROR: Response does not contain the panel start marker. Aborting.")
        print(f"  First 500 chars of response: {updated_panel[:500]}")
        exit(1)

    if PANEL_END_MARKER not in updated_panel:
        print("  ERROR: Response does not contain the panel end marker. Aborting.")
        print(f"  Last 300 chars of response: {updated_panel[-300:]}")
        exit(1)

    if len(updated_panel) < len(panel_html) * 0.85:
        print(f"  ERROR: Updated panel ({len(updated_panel):,} chars) is >15% shorter than original ({len(panel_html):,} chars). Aborting.")
        exit(1)

    if updated_panel == panel_html:
        print("  No changes - dashboard already up to date.")
        exit(0)

    # Splice updated panel back into full HTML
    updated_full_html = splice_panel(full_html, updated_panel, panel_start, panel_end)
    save_html(updated_full_html)

    print(f"  Saved updated HTML ({len(updated_full_html):,} chars)")
    print(f"  Panel grew by {len(updated_panel) - len(panel_html):+,} chars")
    print(f"  Timestamp: {timestamp}")

if __name__ == "__main__":
    update_dashboard()

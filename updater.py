#!/usr/bin/env python3
"""
Epic Fury Dashboard Auto-Updater — JSON diff approach.
Claude returns only a small JSON object describing what changed.
Python applies the changes surgically to the HTML.
Target runtime: 30-60 seconds.
"""

import os
import re
import json
import time
import datetime
import anthropic

# ── Config ────────────────────────────────────────────────────────────────────
HTML_FILE = "dashboards/iran-israel-conflict-dashboards.html"
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16000
MAX_RETRIES = 3
PANEL_START_MARKER = '<div class="panel" id="panel-epicfury">'
PANEL_END_MARKER   = "</div><!-- /panel-epicfury -->"
TIMELINE_INSERT_MARKER = "<!-- ── PLACEHOLDER — keep for next update ── -->"
SEARCH_QUERIES = [
    "Operation Epic Fury Iran Israel latest updates today 2026",
    "Iran war casualties killed injured March 2026",
    "CENTCOM Iran operation targets struck update March 2026",
    "IDF Israel strikes Iran March 2026 air superiority",
    "Iran ceasefire negotiations unconditional surrender Trump March 2026",
    "Iran IRGC missile drone launches March 2026 wave strikes",
    "Lebanon displaced civilians Hezbollah March 2026",
]
# ──────────────────────────────────────────────────────────────────────────────

def load_html() -> str:
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        return f.read()

def save_html(content: str) -> None:
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(content)

def extract_panel(html: str) -> tuple[str, int, int]:
    start = html.find(PANEL_START_MARKER)
    end   = html.find(PANEL_END_MARKER)
    if start == -1 or end == -1:
        raise ValueError("Could not find Epic Fury panel markers in HTML.")
    end_full = end + len(PANEL_END_MARKER)
    return html[start:end_full], start, end_full

def extract_current_state(panel: str) -> str:
    """Return a compact plain-text summary of current dashboard state (~2k chars).
    Sent to Claude instead of the full 230k-char panel HTML."""
    lines = []

    # Current stats — extract all stat-num + stat-label pairs
    stat_pattern = re.compile(
        r'<div class="stat-num[^"]*">([^<]+)</div>\s*'
        r'<div class="stat-label[^"]*"[^>]*>([^<]+)</div>',
        re.S
    )
    lines.append("CURRENT RUNNING TOTALS (all fields — update any that have changed):")
    for val, label in stat_pattern.findall(panel):
        val = val.strip()
        label = re.sub(r'\s+', ' ', label.strip())
        if val and label:
            lines.append(f"  {val} — {label}")

    # Current timestamp
    ts_match = re.search(r'[A-Z][a-z]+ \d{1,2}, 20\d\d\s*·\s*\d{2}:\d{2} UTC', panel)
    if ts_match:
        lines.append(f"\nCURRENT TIMESTAMP: {ts_match.group()}")

    # Last 5 timeline entries (date + title only — enough to know what's already covered)
    entry_pattern = re.compile(
        r'<div class="tl-day">(\d+)</div><div class="tl-month">([^<]+)</div>'
        r'.*?<div class="tl-title">([^<]+)</div>',
        re.S
    )
    entries = entry_pattern.findall(panel)
    if entries:
        n = min(5, len(entries))
        lines.append(f"\nLAST {n} TIMELINE ENTRIES (most recent last — only add entries AFTER these):")
        for day, month, title in entries[-n:]:
            lines.append(f"  {month} {day}: {title[:120]}")

    return "\n".join(lines)

def build_prompt(state_summary: str, timestamp: str) -> str:
    return f"""Search the web for the latest developments in the Iran-Israel-US conflict (Operation Epic Fury), then return ONLY a JSON object describing what needs to change in the dashboard.

SEARCH THESE TOPICS:
{chr(10).join(f"- {q}" for q in SEARCH_QUERIES)}

After all searches are complete, return a single JSON object with this exact structure (omit any key if nothing changed):

{{
  "timestamp": "{timestamp}",

  "stats": {{
    "iran_killed": "1,332+",
    "iran_injured": "6,000+",
    "israel_killed": "12",
    "israel_injured": "121+",
    "us_kia": "18+",
    "us_wounded": "18+",
    "targets_struck": "3,000+",
    "countries_struck": "9+",
    "iranian_ships": "43+",
    "iranian_aircraft": "1 Yak-130 + 2 Su-24",
    "leb_hezb_killed": "123+ / TBD",
    "us_israel_aircraft": "TBD"
  }},

  "hstats": {{
    "us_kia": "18+",
    "ships_sunk": "43",
    "leaders_killed": "52",
    "countries_struck": "12",
    "targets_struck": "3,000+"
  }},

  "new_timeline_entries": [
    {{
      "data_fury": "iran",
      "day": "7",
      "month": "Mar",
      "badge_style": "background:rgba(255,80,80,0.15);color:var(--iran);border-color:rgba(255,80,80,0.3);",
      "badge_label": "Iran · Retaliation",
      "action_type": "Offensive · Description",
      "title": "Short title of the event",
      "details": "Full paragraph of detail about what happened, sourced from your web search.",
      "meta": [
        {{"icon": "📍", "text": "Location details"}},
        {{"icon": "💀", "text": "Casualty figures"}}
      ],
      "sources": [
        {{"label": "NBC News", "url": "https://nbcnews.com/example"}}
      ]
    }}
  ],

  "iranian_launch_bars": [
    {{"label": "Mar 7 (Day 8)", "width": "9%", "value": "down 90% vs Day 1", "opacity": "0.4", "preliminary": true}}
  ],

  "coalition_strike_bars": [
    {{"label": "Mar 7 — IAF", "width": "30%", "value": "80-jet wave", "color": "israel", "opacity": "0.65", "preliminary": true}}
  ],

  "new_leaders_killed": [
    "Name — Title. Details of killing."
  ]
}}

RULES:
- Output ONLY the raw JSON object — no markdown fences, no preamble, no explanation.
- Only include keys where you found confirmed new information via web search.
- Only include stats you found confirmed figures for — do not guess or lower existing figures.
- For new_timeline_entries: only include events that happened AFTER the last entry shown below.
- If nothing is new, return: {{"timestamp": "{timestamp}"}}

CURRENT DASHBOARD STATE (use this to determine what is already shown):
{state_summary}"""

# ── HTML patch functions ───────────────────────────────────────────────────────

def patch_timestamps(panel: str, timestamp: str) -> str:
    panel = re.sub(
        r'[A-Z][a-z]+ \d{1,2}, 20\d\d\s*·\s*\d{2}:\d{2} UTC',
        timestamp,
        panel
    )
    return panel

def patch_stat_card(panel: str, label_fragment: str, new_value: str) -> str:
    """Finds a stat-card containing label_fragment and replaces the stat-num value."""
    pattern = rf'(<div class="stat-num[^"]*">)[^<]+(</div>\s*<div class="stat-label[^"]*"[^>]*>[^<]*{re.escape(label_fragment)})'
    replacement = rf'\g<1>{new_value}\2'
    updated = re.sub(pattern, replacement, panel, count=1)
    if updated == panel:
        print(f"    WARNING: stat card not found for label fragment: '{label_fragment}'")
    return updated

def patch_hstat(panel: str, label_fragment: str, new_value: str) -> str:
    """Finds an hstat containing label_fragment and updates its hstat-val."""
    pattern = rf'(<div class="hstat-val[^"]*">)[^<]+(</div><div class="hstat-label">[^<]*{re.escape(label_fragment)})'
    replacement = rf'\g<1>{new_value}\2'
    updated = re.sub(pattern, replacement, panel, count=1)
    if updated == panel:
        print(f"    WARNING: hstat not found for label fragment: '{label_fragment}'")
    return updated

def build_timeline_entry(entry: dict) -> str:
    meta_html = "\n".join(
        f'            <span class="tl-meta-item"><span class="tl-meta-icon">{m["icon"]}</span>{m["text"]}</span>'
        for m in entry.get("meta", [])
    )
    sources_html = "\n".join(
        f'            <a class="source-link" href="{s["url"]}" target="_blank">{s["label"]}</a>'
        for s in entry.get("sources", [])
    )
    data_fury = entry['data_fury']
    dot_color = (
        'var(--iran)'     if 'iran' in data_fury else
        'var(--israel)'   if 'us-israel' in data_fury else
        'var(--accent)'   if 'diplomatic' in data_fury else
        'var(--jordan)'
    )
    return f"""
      <div class="tl-entry" data-fury="{data_fury}">
        <div class="tl-date"><div class="tl-day">{entry['day']}</div><div class="tl-month">{entry['month']}</div></div>
        <div class="tl-dot" style="background:{dot_color}"></div>
        <div class="tl-content">
          <div class="tl-header">
            <span class="tl-actor-badge" style="{entry['badge_style']}">{entry['badge_label']}</span>
            <span class="tl-action-type">{entry['action_type']}</span>
          </div>
          <div class="tl-title">{entry['title']}</div>
          <div class="tl-details">{entry['details']}</div>
          <div class="tl-meta">
{meta_html}
          </div>
          <div class="tl-sources">
            <span class="tl-sources-label">Sources:</span>
{sources_html}
          </div>
        </div>
      </div>"""

def build_bar_row(bar: dict, color_var: str) -> str:
    opacity = bar.get("opacity", "1.0")
    preliminary = bar.get("preliminary", False)
    val_color = "var(--muted)" if preliminary else f"var(--{color_var})"
    return f"""
      <div class="bar-row">
        <div class="bar-label">{bar['label']}</div>
        <div class="bar-track"><div class="bar-fill" style="width:{bar['width']};background:var(--{color_var});opacity:{opacity};"></div></div>
        <div class="bar-val" style="color:{val_color};">{bar['value']}</div>
      </div>"""

def apply_diff(panel: str, diff: dict) -> tuple[str, bool]:
    changed = False

    # 1. Timestamp
    if "timestamp" in diff:
        new_panel = patch_timestamps(panel, diff["timestamp"])
        if new_panel != panel:
            print(f"    Updated timestamps → {diff['timestamp']}")
            panel = new_panel
            changed = True

    # 2. Stat cards — all 12 running total fields
    stat_label_map = {
        "iran_killed":        "Iranian civilians killed",
        "iran_injured":       "Iranian civilians injured",
        "israel_killed":      "Israeli civilians killed",
        "israel_injured":     "Israelis injured",
        "us_kia":             "US soldiers KIA",
        "us_wounded":         "seriously wounded",
        "targets_struck":     "targets struck",
        "countries_struck":   "countries struck",
        "iranian_ships":      "Iranian naval vessels destroyed",
        "iranian_aircraft":   "Iranian military aircraft destroyed",
        "leb_hezb_killed":    "Lebanese Civilians",
        "us_israel_aircraft": "US/Israeli aircraft lost",
    }
    for key, label_fragment in stat_label_map.items():
        if key in diff.get("stats", {}):
            new_val = diff["stats"][key]
            new_panel = patch_stat_card(panel, label_fragment, new_val)
            if new_panel != panel:
                print(f"    Stat updated: {label_fragment} → {new_val}")
                panel = new_panel
                changed = True

    # 3. Hstats
    hstat_label_map = {
        "us_kia":          "KIA",
        "ships_sunk":      "ships",
        "leaders_killed":  "leaders",
        "countries_struck":"countries",
        "targets_struck":  "targets",
    }
    for key, label_fragment in hstat_label_map.items():
        if key in diff.get("hstats", {}):
            new_val = diff["hstats"][key]
            new_panel = patch_hstat(panel, label_fragment, new_val)
            if new_panel != panel:
                print(f"    Hstat updated: {label_fragment} → {new_val}")
                panel = new_panel
                changed = True

    # 4. New timeline entries
    for entry in diff.get("new_timeline_entries", []):
        entry_html = build_timeline_entry(entry)
        panel = panel.replace(
            TIMELINE_INSERT_MARKER,
            entry_html + "\n\n      " + TIMELINE_INSERT_MARKER,
            1
        )
        print(f"    Added timeline entry: {entry['title'][:60]}...")
        changed = True

    # 5. Iranian launch bars — insert before the footnote div
    for bar in diff.get("iranian_launch_bars", []):
        bar_html = build_bar_row(bar, "iran")
        insert_anchor = '<div style="font-size:9px;color:var(--muted);margin-top:8px;font-family:\'IBM Plex Mono\''
        panel = panel.replace(insert_anchor, bar_html + "\n      " + insert_anchor, 1)
        print(f"    Added Iranian launch bar: {bar['label']}")
        changed = True

    # 6. Coalition strike bars — insert before the second footnote div
    color_map = {"israel": "israel", "us": "us"}
    for bar in diff.get("coalition_strike_bars", []):
        color_var = color_map.get(bar.get("color", "israel"), "israel")
        bar_html = build_bar_row(bar, color_var)
        anchors = [m.start() for m in re.finditer(
            r'<div style="font-size:9px;color:var\(--muted\);margin-top:8px',
            panel
        )]
        if len(anchors) >= 2:
            insert_pos = anchors[1]
            panel = panel[:insert_pos] + bar_html + "\n      " + panel[insert_pos:]
            print(f"    Added coalition strike bar: {bar['label']}")
            changed = True

    # 7. New leadership kills
    for leader in diff.get("new_leaders_killed", []):
        leader_html = f'\n      <div class="context-item">{leader}</div>'
        anchor = '</div>\n\n    <!-- Key assassinations -->'
        if anchor not in panel:
            anchor = '</div>\n    <!-- Key assassinations -->'
        panel = panel.replace(anchor, leader_html + anchor, 1)
        print(f"    Added leader killed: {leader[:60]}...")
        changed = True

    return panel, changed

# ── Main ───────────────────────────────────────────────────────────────────────

def update_dashboard() -> None:
    now = datetime.datetime.now(datetime.UTC)
    print(f"[{now.isoformat()}] Starting Epic Fury dashboard update...")

    full_html = load_html()
    print(f"  Loaded: {HTML_FILE} ({len(full_html):,} chars)")

    try:
        panel_html, panel_start, panel_end = extract_panel(full_html)
    except ValueError as e:
        print(f"  ERROR: {e}")
        exit(1)

    print(f"  Extracted Epic Fury panel ({len(panel_html):,} chars)")

    # Build compact state summary instead of sending full panel HTML
    state_summary = extract_current_state(panel_html)
    print(f"  State summary ({len(state_summary):,} chars — sent to Claude instead of full panel)")

    timestamp = now.strftime("%B %-d, %Y · %H:%M UTC")
    prompt = build_prompt(state_summary, timestamp)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Retry loop with exponential backoff
    diff = None
    raw = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  Calling {MODEL} (attempt {attempt}/{MAX_RETRIES})...")
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=(
                    "You are a news analyst updating a live war dashboard. "
                    "Perform all web searches first to gather the latest information. "
                    "Then output ONLY the raw JSON object as your final message — "
                    "no markdown fences, no preamble, no explanation before or after the JSON."
                ),
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{"role": "user", "content": prompt}],
            )

            # Take the LAST text block — earlier blocks may be preamble before tool use
            raw = ""
            for block in response.content:
                if block.type == "text":
                    raw = block.text.strip()   # keep overwriting; last one wins

            # Strip accidental markdown fences
            raw = re.sub(r"^```json?\n?", "", raw, flags=re.MULTILINE).strip()
            raw = re.sub(r"\n?```\s*$", "", raw, flags=re.MULTILINE).strip()

            print(f"  Raw response ({len(raw)} chars): {raw[:200]}...")
            diff = json.loads(raw)
            break  # success

        except json.JSONDecodeError as e:
            print(f"  Attempt {attempt} failed — JSON parse error: {e}")
            if attempt < MAX_RETRIES:
                wait = 5 * attempt
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)
        except Exception as e:
            print(f"  Attempt {attempt} failed — {type(e).__name__}: {e}")
            if attempt < MAX_RETRIES:
                wait = 5 * attempt
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)

    if diff is None:
        print(f"  ERROR: All {MAX_RETRIES} attempts failed.")
        print(f"  Last raw response: {raw}")
        exit(1)

    print(f"  Parsed diff with keys: {list(diff.keys())}")

    # Apply the diff
    updated_panel, changed = apply_diff(panel_html, diff)

    if not changed:
        print("  No changes — dashboard already up to date.")
        exit(0)

    # Splice back into full HTML and save
    updated_full_html = full_html[:panel_start] + updated_panel + full_html[panel_end:]
    save_html(updated_full_html)
    print(f"  Saved ({len(updated_full_html):,} chars total)")
    print(f"  Timestamp: {timestamp}")

if __name__ == "__main__":
    update_dashboard()

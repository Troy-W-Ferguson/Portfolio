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
import datetime
import anthropic

# ── Config ────────────────────────────────────────────────────────────────────
HTML_FILE = "dashboards/iran-israel-conflict-dashboards.html"
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4000
PANEL_START_MARKER = '<div class="panel" id="panel-epicfury">'
PANEL_END_MARKER   = "</div><!-- /panel-epicfury -->"
TIMELINE_INSERT_MARKER = "<!-- ── PLACEHOLDER — keep for next update ── -->"
SEARCH_QUERIES = [
    "Operation Epic Fury Iran Israel latest updates today",
    "Iran war casualties killed injured 2026",
    "CENTCOM Iran operation targets struck update",
    "IDF intercepts missiles drones Iron Dome David's Sling today",
    "Hezbollah Israel Lebanon strikes today",
    "Iran US war ceasefire negotiations 2026",
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

def build_prompt(panel_html: str, timestamp: str) -> str:
    return f"""You are a news analyst updating a live war dashboard. Search the web for the latest developments in the Iran-Israel-US conflict (Operation Epic Fury), then return ONLY a JSON object describing what needs to change. Do not return any HTML.

SEARCH THESE TOPICS FIRST:
{chr(10).join(f"- {q}" for q in SEARCH_QUERIES)}

After searching, return a single JSON object with this exact structure (omit any key if nothing changed):

{{
  "timestamp": "{timestamp}",

  "stats": {{
    "iran_killed": "600+",
    "iran_injured": "900+",
    "israel_killed": "22",
    "us_kia": "7",
    "us_wounded": "20+",
    "targets_struck": "1,500+",
    "countries_struck": "9+"
  }},

  "hstats": {{
    "us_kia": "7",
    "ships_sunk": "12",
    "leaders_killed": "52",
    "countries_struck": "9",
    "targets_struck": "1500+"
  }},

  "new_timeline_entries": [
    {{
      "data_fury": "iran",
      "day": "4",
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
        {{"label": "NBC News", "url": "https://nbcnews.com/..."}}
      ]
    }}
  ],

  "iranian_launch_bars": [
    {{"label": "Mar 3 (Day 4)", "width": "25%", "value": "est. 200+", "opacity": "0.7", "preliminary": true}}
  ],

  "coalition_strike_bars": [
    {{"label": "Mar 3 — IAF", "width": "40%", "value": "extensive wave", "color": "israel", "opacity": "0.7", "preliminary": true}}
  ],

  "new_leaders_killed": [
    "Name — Title. Details of killing."
  ]
}}

RULES:
- Return ONLY the JSON object. No explanation, no markdown fences, no preamble.
- Only include keys where you actually found new information via web search.
- Only include stats you found confirmed figures for — do not guess.
- For new_timeline_entries, only include events that happened AFTER the most recent dated entry in the panel below.
- If nothing is new, return: {{"timestamp": "{timestamp}"}}

CURRENT PANEL (read this to understand current state before deciding what is new):
{panel_html}"""

# ── HTML patch functions ───────────────────────────────────────────────────────

def patch_timestamps(panel: str, timestamp: str) -> str:
    # Matches patterns like "March 3, 2026 · 06:00 UTC" or "March 10, 2026 · 12:00 UTC"
    panel = re.sub(
        r'[A-Z][a-z]+ \d{1,2}, 20\d\d\s*·\s*\d{2}:\d{2} UTC',
        timestamp,
        panel
    )
    # Also update the AS OF label
    panel = re.sub(
        r'AS OF \d+ [A-Z]{3} \d{2}:\d{2} UTC',
        f'AS OF {datetime.datetime.now(datetime.UTC).strftime("%-d %b %H:%M UTC")}',
        panel
    )
    return panel

def patch_stat_card(panel: str, label_fragment: str, new_value: str) -> str:
    """
    Finds a stat-card containing label_fragment in its stat-label,
    and replaces the stat-num value inside it.
    """
    pattern = rf'(<div class="stat-num[^"]*">)[^<]+(</div>\s*<div class="stat-label">[^<]*{re.escape(label_fragment)})'
    replacement = rf'\g<1>{new_value}\2'
    updated = re.sub(pattern, replacement, panel, count=1)
    if updated == panel:
        print(f"    WARNING: stat card not found for label fragment: '{label_fragment}'")
    return updated

def patch_hstat(panel: str, label_fragment: str, new_value: str) -> str:
    """
    Finds an hstat containing label_fragment and updates its hstat-val.
    """
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
    return f"""
      <div class="tl-entry" data-fury="{entry['data_fury']}">
        <div class="tl-date"><div class="tl-day">{entry['day']}</div><div class="tl-month">{entry['month']}</div></div>
        <div class="tl-dot" style="background:var(--{'iran' if 'iran' in entry['data_fury'] else 'israel' if 'us-israel' in entry['data_fury'] else 'accent' if 'diplomatic' in entry['data_fury'] else 'jordan'})"></div>
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

def apply_diff(panel: str, diff: dict) -> str:
    changed = False

    # 1. Timestamp
    if "timestamp" in diff:
        new_panel = patch_timestamps(panel, diff["timestamp"])
        if new_panel != panel:
            print(f"    Updated timestamps → {diff['timestamp']}")
            panel = new_panel
            changed = True

    # 2. Stat cards
    stat_label_map = {
        "iran_killed":     "Iranian civilians killed",
        "iran_injured":    "Iranian civilians injured",
        "israel_killed":   "Israeli civilians killed",
        "us_kia":          "US soldiers KIA",
        "us_wounded":      "seriously wounded",
        "targets_struck":  "targets struck",
        "countries_struck":"countries struck",
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

    # 5. Iranian launch bars — append before the closing footnote div
    for bar in diff.get("iranian_launch_bars", []):
        bar_html = build_bar_row(bar, "iran")
        # Insert before the footnote div that follows the Iranian bars section
        insert_anchor = '<div style="font-size:9px;color:var(--muted);margin-top:8px;font-family:\'IBM Plex Mono\''
        panel = panel.replace(insert_anchor, bar_html + "\n      " + insert_anchor, 1)
        print(f"    Added Iranian launch bar: {bar['label']}")
        changed = True

    # 6. Coalition strike bars
    color_map = {"israel": "israel", "us": "us"}
    for bar in diff.get("coalition_strike_bars", []):
        color_var = color_map.get(bar.get("color", "israel"), "israel")
        bar_html = build_bar_row(bar, color_var)
        # Insert before the second footnote div (coalition chart footnote)
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

    timestamp = now.strftime("%B %-d, %Y · %H:%M UTC")
    prompt = build_prompt(panel_html, timestamp)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    print(f"  Calling {MODEL} with web search enabled...")

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract text response
    raw = ""
    for block in response.content:
        if block.type == "text":
            raw = block.text.strip()
            break

    # Strip accidental markdown fences
    raw = re.sub(r"^```json?\n?", "", raw, flags=re.MULTILINE).strip()
    raw = re.sub(r"\n?```\s*$", "", raw, flags=re.MULTILINE).strip()

    print(f"  Raw response ({len(raw)} chars): {raw[:200]}...")

    # Parse JSON
    try:
        diff = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ERROR: Could not parse JSON response: {e}")
        print(f"  Full response: {raw}")
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

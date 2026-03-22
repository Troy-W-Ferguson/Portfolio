IRAN WAR GEOSPATIAL DASHBOARD
==============================
Dashboard file: iran_war_geospatial_dashboard.html
Data file:      iran_war_geospatial_2026.json

OVERVIEW
--------
This folder contains the data powering the Iran War Geospatial Dashboard, an
interactive Leaflet.js map tracking strikes, attacks, and military actions
across the 2026 Iran-US-Israel conflict (Operation Epic Fury / Operation
Roaring Lion), from the opening salvo on 28 February 2026 through the present.

The dashboard is part of the portfolio of Troy W. Ferguson (byline: Troy W.
Ferguson), a Cambridge-based investigative journalist and former Defense
Intelligence Agency senior analyst.

DATA FILE
---------
File: iran_war_geospatial_2026.json

This is the single source of truth for the dashboard. The HTML file fetches
it at page load via a relative path fetch() call. To update the dashboard with
new data, replace this file with a new version -- the HTML requires no changes.

The JSON follows a location-primary schema. Each record represents a distinct
geographic location. Individual strike events are nested under that location's
attacks[] array. Top-level aggregate fields (total_attacks,
aggregate_casualties_killed, etc.) are computed totals across all attacks at
that location.

Key fields used by the dashboard:

  location_id              Unique slug (e.g. IRN-TEHRAN, MARITIME-HORMUZ)
  location_name            Display name for popups and labels
  lat / lon                Coordinates for Leaflet marker placement
  primary_attacker         Used for marker color encoding
  total_attacks            Used for marker size encoding
  aggregate_casualties_*   Displayed in location popup summary
  last_attack_DTG          ISO 8601 timestamp; drives the time slider
  attacks[]                Array of individual strike events; each has:
    DTG                    Timestamp of the attack (drives time filtering)
    descriptor             Plain-language description of the event
    attacker               Actor responsible
    target_category        Classification of target type
    casualties_killed/wounded   Per-event figures where available
    confidence_level       confirmed / reported / unconfirmed
    sources[]              Array of short source keys
  _meta.sources_legend     Maps short source keys to full URLs
  _meta.cumulative_war_stats  War-level aggregate statistics for the stats panel

SOURCING
--------
Every attack entry carries a sources[] array of short keys (e.g. "ALMA-MAR17",
"CNN-MAR22") that resolve to full URLs in _meta.sources_legend. Primary sources
include Al Jazeera daily liveblogs, CNN, NBC, NPR, PBS, CBS, the Alma Research
Center daily conflict reports, Critical Threats / ISW, ACLED's Middle East
Special Issue, Human Rights Watch, Amnesty International, and CENTCOM/IDF
official statements. A small number of entries carry confidence_level:
"reported" where only a single secondary source was available at time of entry.

Iranian casualty aggregates at the location level reflect reported figures from
Iranian state sources (Red Crescent, Health Ministry) and should be read as
attributed claims rather than independently verified counts.

UPDATE WORKFLOW
---------------
1. Run the update process to produce a new timestamped JSON.
2. Rename or copy the output to iran_war_geospatial_2026.json.
3. Place the file in this folder (dashboards/data/).
4. Commit and push to GitHub. GitHub Pages serves the updated file
   automatically. No changes to the HTML are required.

The dashboard HTML fetches the data file at:
  ./data/iran_war_geospatial_2026.json
(relative to the dashboard HTML location at dashboards/)

VERSION HISTORY
---------------
The JSON includes a last_updated field in _meta reflecting the date and time
of the most recent data update (UTC). Check this field to confirm currency.

Current coverage: 28 February 2026 through 22 March 2026.
Current scope:    49 location nodes, 215 individual attack entries.

SCHEMA VERSION
--------------
_meta.schema_version: 1.1

LICENSE / USE
-------------
This dataset was compiled for journalistic and portfolio purposes by Troy W.
Ferguson using open-source reporting. All sourced material remains the property
of its respective publishers. The compiled dataset structure and editorial
judgments are the work of Troy W. Ferguson. If you cite or build on this data,
please credit: Troy W. Ferguson, Iran War Geospatial Dashboard (2026).

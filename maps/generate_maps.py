#!/usr/bin/env python3
"""
Kurdish region static journalist maps
Outputs: maps/kurdistan_map1.png  (regional political)
         maps/kurdistan_map2.png  (operational: groups, bases, oil)

Usage:
    cd /home/user/Portfolio
    python3 maps/generate_maps.py
"""

import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use('Agg')

import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import geopandas as gpd
import requests
from shapely.geometry import Point, Polygon, box, shape

# ─── paths ────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).parent.parent
MAPS_DIR = Path(__file__).parent
NE_CACHE = Path('/tmp/ne_50m')
OUT1     = MAPS_DIR / 'kurdistan_map1.png'
OUT2     = MAPS_DIR / 'kurdistan_map2.png'

# ─── editorial colour palette ─────────────────────────────────────────────────
C = dict(
    bg        = '#f0e6cc',   # parchment
    country   = '#e8ddc0',   # lighter parchment (country fill)
    border    = '#7a6645',   # warm brown border
    iraq_ctx  = '#d8ccb0',   # muted tan for non-Kurdish Iraq govs
    kdp       = '#4a7fb5',   # KDP — Dohuk & Erbil
    puk       = '#7ab0d8',   # PUK — Sulaimaniyah
    krg       = '#4a7fb5',   # unified KRG for map 1
    turkish   = '#c49a3a',   # Turkish Kurdish provinces
    iranian   = '#b85555',   # Iranian Kurdish provinces
    syrian    = '#5a8f5a',   # Syrian Kurdish / Rojava
    pkk       = '#8b4a4a',   # PKK / Qandil zone
    sinjar    = '#7a5a9a',   # Sinjar / YBŞ
    oil       = '#c49a3a',   # oil field marker
    gas       = '#8a8a30',   # gas field marker
    base_act  = '#f5f0e8',   # active US base
    base_old  = '#aaaaaa',   # former US base
    text_dark = '#2a1e0a',
    text_mid  = '#5a4030',
    text_lite = '#8a7458',
)

# ─── Natural Earth country boundaries ─────────────────────────────────────────
def get_countries() -> gpd.GeoDataFrame:
    shp = NE_CACHE / 'ne_50m_admin_0_countries.shp'
    if not shp.exists():
        NE_CACHE.mkdir(parents=True, exist_ok=True)
        urls = [
            'https://naturalearth.s3.amazonaws.com/50m_cultural/ne_50m_admin_0_countries.zip',
            'https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip',
        ]
        downloaded = False
        for url in urls:
            try:
                print(f'  Downloading Natural Earth from {url} ...')
                r = requests.get(url, timeout=60)
                r.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    z.extractall(NE_CACHE)
                downloaded = True
                break
            except Exception as e:
                print(f'  Failed ({e}), trying next mirror...')
        if not downloaded:
            raise RuntimeError('Could not download Natural Earth data from any mirror.')
    return gpd.read_file(shp)


# ─── Kurdish admin data (parsed from article HTML) ────────────────────────────
def load_admin_gdf() -> gpd.GeoDataFrame:
    html = (ROOT / 'articles' / 'kurdistan_explainer.html').read_text(encoding='utf-8')
    m = re.search(r'var ADMIN_DATA = (\{.*?\});\s*\n', html, re.DOTALL)
    if not m:
        raise RuntimeError('ADMIN_DATA not found in articles/kurdistan_explainer.html')
    d = json.loads(m.group(1))
    rows = []
    for f in d['features']:
        p = f['properties']
        rows.append({
            'geometry': shape(f['geometry']),
            'name':     p['_name'],
            'country':  p['_country'],
            'type':     p['_type'],
        })
    return gpd.GeoDataFrame(rows, crs='EPSG:4326')


# ─── shared helpers ───────────────────────────────────────────────────────────
def halo(lw: float = 2.5, fg: str = 'white'):
    return [pe.withStroke(linewidth=lw, foreground=fg)]


def set_frame(ax):
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_edgecolor(C['border'])
        sp.set_linewidth(1.2)


def place_legend(ax, handles, title: str, loc: str = 'lower left'):
    leg = ax.legend(
        handles=handles,
        title=title.upper(),
        title_fontsize=7,
        fontsize=7,
        loc=loc,
        frameon=True,
        facecolor=C['bg'],
        edgecolor=C['border'],
        framealpha=0.93,
        borderpad=0.9,
        labelspacing=0.55,
        handlelength=1.6,
        handleheight=1.1,
    )
    leg.get_title().set_color(C['text_mid'])
    leg.get_title().set_fontweight('bold')
    for t in leg.get_texts():
        t.set_color(C['text_dark'])
    return leg


# ─── MAP 1: Regional Political ────────────────────────────────────────────────
def generate_map1(countries: gpd.GeoDataFrame, admin: gpd.GeoDataFrame) -> None:
    LON_MIN, LON_MAX, LAT_MIN, LAT_MAX = 33.0, 59.0, 27.5, 43.5
    vbox = box(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)

    fig, ax = plt.subplots(figsize=(16, 11))
    fig.patch.set_facecolor(C['bg'])
    ax.set_facecolor(C['bg'])

    # ── country fills ──────────────────────────────────────────────────────────
    clip = countries.clip(vbox)
    clip.plot(ax=ax, facecolor=C['country'], edgecolor=C['border'],
              linewidth=0.9, zorder=1)

    # ── Iraq context governorates (other) ──────────────────────────────────────
    iraq_ctx = admin[admin['type'] == 'iraq-other']
    iraq_ctx.plot(ax=ax, facecolor=C['iraq_ctx'], edgecolor=C['border'],
                  linewidth=0.35, alpha=0.75, zorder=2)

    # ── Kurdish regions ────────────────────────────────────────────────────────
    region_cfg = {
        'krg':             (C['krg'],     '#2a5a8a', 1.8, 0.72),
        'turkish-kurdish': (C['turkish'], '#8a6818', 1.2, 0.65),
        'iranian-kurdish': (C['iranian'], '#8b3030', 1.2, 0.65),
        'syrian-kurdish':  (C['syrian'],  '#3a6e3a', 1.4, 0.68),
    }
    for rtype, (fc, ec, lw, alpha) in region_cfg.items():
        sub = admin[admin['type'] == rtype]
        if not sub.empty:
            sub.plot(ax=ax, facecolor=fc, edgecolor=ec,
                     linewidth=lw, alpha=alpha, zorder=3)

    ax.set_xlim(LON_MIN, LON_MAX)
    ax.set_ylim(LAT_MIN, LAT_MAX)
    set_frame(ax)

    # ── country name labels ────────────────────────────────────────────────────
    country_labels = [
        ('TURKEY',        38.0, 39.8),
        ('IRAN',          53.5, 32.0),
        ('IRAQ',          44.5, 31.5),
        ('SYRIA',         37.5, 34.6),
        ('JORDAN',        37.0, 30.8),
        ('SAUDI\nARABIA', 46.5, 29.5),
        ('KUWAIT',        47.6, 29.2),
        ('ARMENIA',       44.8, 40.3),
        ('AZERBAIJAN',    49.5, 40.5),
        ('GEORGIA',       43.5, 42.1),
        ('LEBANON',       35.7, 33.9),
    ]
    for txt, lon, lat in country_labels:
        if LON_MIN < lon < LON_MAX and LAT_MIN < lat < LAT_MAX:
            ax.text(lon, lat, txt, fontsize=8.5, color=C['text_mid'],
                    ha='center', va='center', fontweight='bold',
                    alpha=0.70, fontstyle='italic', zorder=5,
                    path_effects=halo(2, C['bg']))

    # ── capital cities ─────────────────────────────────────────────────────────
    capitals = [
        ('Ankara',    39.93, 32.86),
        ('Baghdad',   33.34, 44.40),
        ('Tehran',    35.69, 51.39),
        ('Damascus',  33.51, 36.29),
        ('Beirut',    33.89, 35.50),
        ('Amman',     31.96, 35.95),
        # Regional capitals
        ('Erbil',     36.19, 44.01),
        ('Diyarbakır',37.91, 40.23),
    ]
    label_offsets = {
        'Ankara':    (-0.7,  0.35),
        'Baghdad':   ( 0.6,  0.25),
        'Tehran':    ( 0.6,  0.30),
        'Damascus':  (-0.3, -0.40),
        'Beirut':    (-0.5, -0.30),
        'Amman':     ( 0.4, -0.30),
        'Erbil':     ( 0.5,  0.20),
        'Diyarbakır':(-0.3, -0.40),
    }
    for name, lat, lon in capitals:
        if LON_MIN < lon < LON_MAX and LAT_MIN < lat < LAT_MAX:
            ax.plot(lon, lat, marker='*', markersize=11, linestyle='none',
                    color='black', markeredgecolor='white', markeredgewidth=0.7,
                    zorder=9)
            dx, dy = label_offsets.get(name, (0.45, 0.25))
            ax.text(lon + dx, lat + dy, name, fontsize=8,
                    color=C['text_dark'], ha='center', va='center',
                    fontstyle='italic', path_effects=halo(2.5), zorder=10)

    # ── mountain annotations ───────────────────────────────────────────────────
    mountains = [
        ('▲ Qandil\n3,587m',  36.10, 45.80),
        ('▲ Halgurd\n3,607m', 36.82, 44.54),
        ('▲▲ Zagros\nRange',  33.90, 47.80),
    ]
    for label, lat, lon in mountains:
        if LON_MIN < lon < LON_MAX and LAT_MIN < lat < LAT_MAX:
            ax.text(lon, lat, label, fontsize=7, color='#6a5030',
                    ha='center', va='center', fontstyle='italic', alpha=0.85,
                    zorder=7, path_effects=halo(2, C['bg']))

    # ── title ──────────────────────────────────────────────────────────────────
    fig.text(0.02, 0.97, 'KURDISH REGIONS ACROSS FOUR STATES',
             fontsize=19, fontweight='bold', color=C['text_dark'],
             va='top', ha='left')
    fig.text(0.02, 0.935, 'Provincial and administrative extent of Kurdish ethnic presence, c. 2026',
             fontsize=9, color=C['text_mid'], va='top', ha='left', fontstyle='italic')

    # ── legend ─────────────────────────────────────────────────────────────────
    handles = [
        mpatches.Patch(facecolor=C['krg'],     edgecolor='#2a5a8a', linewidth=1.5,
                       label='Kurdistan Region of Iraq (KRG)'),
        mpatches.Patch(facecolor=C['turkish'], edgecolor='#8a6818', linewidth=1.2,
                       label='Kurdish provinces — Turkey'),
        mpatches.Patch(facecolor=C['iranian'], edgecolor='#8b3030', linewidth=1.2,
                       label='Kurdish provinces — Iran'),
        mpatches.Patch(facecolor=C['syrian'],  edgecolor='#3a6e3a', linewidth=1.4,
                       label='Kurdish region — Syria (Rojava)'),
        mlines.Line2D([0], [0], marker='*', linestyle='none',
                      markerfacecolor='black', markeredgecolor='white',
                      markeredgewidth=0.7, markersize=11,
                      label='National / regional capital'),
        mlines.Line2D([0], [0], linestyle='none',
                      marker='$▲$', markerfacecolor='#6a5030',
                      markersize=8, label='Mountain peak / range'),
    ]
    place_legend(ax, handles, 'Kurdish Administrative Regions', 'lower left')

    # ── source ─────────────────────────────────────────────────────────────────
    fig.text(0.99, 0.01,
             'Sources: geoBoundaries CC BY 4.0 · Natural Earth · Kurdish Institute Paris',
             fontsize=6.5, color=C['text_lite'], ha='right', va='bottom')

    fig.subplots_adjust(top=0.92, bottom=0.03, left=0.02, right=0.98)
    fig.savefig(OUT1, dpi=200, bbox_inches='tight', facecolor=C['bg'])
    plt.close(fig)
    print(f'  → Saved {OUT1}')


# ─── MAP 2: Operational ───────────────────────────────────────────────────────
def generate_map2(countries: gpd.GeoDataFrame, admin: gpd.GeoDataFrame) -> None:
    LON_MIN, LON_MAX, LAT_MIN, LAT_MAX = 38.5, 48.5, 33.5, 38.5
    vbox = box(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)

    fig, ax = plt.subplots(figsize=(14, 10))
    fig.patch.set_facecolor(C['bg'])
    ax.set_facecolor(C['bg'])

    # ── country fills ──────────────────────────────────────────────────────────
    clip = countries.clip(vbox)
    clip.plot(ax=ax, facecolor=C['country'], edgecolor=C['border'],
              linewidth=0.9, zorder=1)

    # ── Iraq context (lighter background) ─────────────────────────────────────
    iraq_ctx = admin[admin['type'] == 'iraq-other']
    iraq_ctx.plot(ax=ax, facecolor=C['iraq_ctx'], edgecolor=C['border'],
                  linewidth=0.3, alpha=0.55, zorder=2)

    # ── Iranian Kurdish provinces (dashed border) ──────────────────────────────
    iran_kurd = admin[admin['type'] == 'iranian-kurdish']
    iran_kurd.plot(ax=ax, facecolor=C['iranian'], edgecolor='none', alpha=0.42, zorder=3)
    iran_kurd.boundary.plot(ax=ax, color='#8b3030', linewidth=1.6,
                            linestyle='--', alpha=0.85, zorder=3)

    # ── Syrian Kurdish / Rojava ────────────────────────────────────────────────
    syr_kurd = admin[admin['type'] == 'syrian-kurdish']
    syr_kurd.plot(ax=ax, facecolor=C['syrian'], edgecolor='#3a6e3a',
                  linewidth=1.5, alpha=0.50, zorder=3)

    # ── KDP: Dohuk + Erbil ────────────────────────────────────────────────────
    kdp = admin[(admin['type'] == 'krg') & (admin['name'].isin(['Dohuk', 'Erbil']))]
    kdp.plot(ax=ax, facecolor=C['kdp'], edgecolor='#2a5a8a',
             linewidth=2.0, alpha=0.60, zorder=4)

    # ── PUK: Sulaimaniyah ─────────────────────────────────────────────────────
    puk = admin[(admin['type'] == 'krg') &
                (admin['name'].str.contains('Sulaimaniyah', case=False))]
    puk.plot(ax=ax, facecolor=C['puk'], edgecolor='#4a80aa',
             linewidth=2.0, alpha=0.60, zorder=4)

    # ── PKK / PJAK — Qandil zone (dashed polygon) ─────────────────────────────
    # Coords from HTML: [[lat, lon], ...] → Shapely needs (lon, lat)
    qandil_coords = [
        (45.10, 36.65), (45.55, 36.55), (46.05, 36.30), (46.25, 35.95),
        (45.95, 35.65), (45.50, 35.58), (45.10, 35.72), (44.85, 36.00),
        (44.90, 36.35), (45.10, 36.65),
    ]
    qpoly  = Polygon(qandil_coords)
    qgdf   = gpd.GeoDataFrame(geometry=[qpoly], crs='EPSG:4326')
    qgdf.plot(ax=ax, facecolor=C['pkk'], edgecolor='none', alpha=0.28, zorder=3)
    qgdf.boundary.plot(ax=ax, color='#6a2a2a', linewidth=1.8,
                       linestyle=(0, (4, 3)), alpha=0.90, zorder=3)
    ax.text(45.55, 36.28, 'PKK / PJAK\nQandil Zone', fontsize=7.5,
            color='#6a2a2a', ha='center', va='center',
            fontstyle='italic', path_effects=halo(2.5), zorder=9)

    # ── Sinjar / YBŞ ──────────────────────────────────────────────────────────
    ax.plot(41.87, 36.32, 'o', markersize=10, color=C['sinjar'],
            markeredgecolor='white', markeredgewidth=0.9,
            zorder=8, linestyle='none')
    ax.text(42.05, 36.50, 'Sinjar\n(YBŞ)', fontsize=7,
            color=C['sinjar'], ha='left', va='bottom',
            path_effects=halo(2.5), zorder=10)

    ax.set_xlim(LON_MIN, LON_MAX)
    ax.set_ylim(LAT_MIN, LAT_MAX)
    set_frame(ax)

    # ── city dots & labels ────────────────────────────────────────────────────
    cities = [
        ('Erbil',          36.19, 44.01, ( 0.18,  0.12)),
        ('Sulaimaniyah',   35.56, 45.44, ( 0.18,  0.12)),
        ('Kirkuk',         35.47, 44.39, (-0.18, -0.22)),
        ('Duhok',          36.87, 42.99, (-0.20,  0.10)),
        ('Mosul',          36.34, 43.13, (-0.20,  0.12)),
        ('Diyarbakır',     37.91, 40.23, ( 0.18,  0.10)),
        ('Mahabad',        36.76, 45.72, ( 0.18,  0.10)),
        ('Halabja',        35.18, 45.99, ( 0.18, -0.18)),
    ]
    for name, lat, lon, (dx, dy) in cities:
        if LON_MIN < lon < LON_MAX and LAT_MIN < lat < LAT_MAX:
            ax.plot(lon, lat, 'o', markersize=4.5, color=C['text_dark'],
                    markeredgecolor='white', markeredgewidth=0.7,
                    zorder=8, linestyle='none')
            ax.text(lon + dx, lat + dy, name, fontsize=7,
                    color=C['text_dark'], ha='left' if dx > 0 else 'right',
                    va='bottom' if dy > 0 else 'top',
                    path_effects=halo(2.5), zorder=9)

    # ── US Military Bases ─────────────────────────────────────────────────────
    bases = [
        ('Erbil Air Base',      36.24, 44.00, True),
        ('Al-Harir (Bashur)',   36.63, 44.38, True),
        ('Q-West / Qayyarah',   35.76, 43.12, False),
        ('FOB Warrior / Kirkuk',35.47, 44.39, False),
    ]
    for name, lat, lon, active in bases:
        if LON_MIN < lon < LON_MAX and LAT_MIN < lat < LAT_MAX:
            col = C['base_act'] if active else C['base_old']
            fc  = col if active else 'none'
            ax.plot(lon, lat, marker='*', markersize=16, linestyle='none',
                    markerfacecolor=fc, markeredgecolor=C['border'],
                    markeredgewidth=0.9, zorder=11)
            dy = 0.17 if active else -0.20
            ax.text(lon, lat + dy, name, fontsize=6.5,
                    color=C['text_dark'] if active else C['base_old'],
                    ha='center', va='bottom' if dy > 0 else 'top',
                    fontstyle='normal' if active else 'italic',
                    path_effects=halo(2.5), zorder=12)

    # ── Oil & Gas Fields ──────────────────────────────────────────────────────
    oil_fields = [
        ('Kirkuk',      35.47, 44.39, 'oil'),
        ('Tawke',       37.00, 43.10, 'oil'),
        ('Shaikan',     36.75, 43.50, 'oil'),
        ('Khor Mor',    35.10, 45.30, 'gas'),
        ('Taq Taq',     35.90, 44.60, 'oil'),
        ('Khurmala',    36.05, 44.15, 'oil'),
        ('Bai Hassan',  35.58, 44.20, 'oil'),
        ('Miran',       36.30, 44.80, 'oil'),
    ]
    for name, lat, lon, ftype in oil_fields:
        if LON_MIN < lon < LON_MAX and LAT_MIN < lat < LAT_MAX:
            col = C['oil'] if ftype == 'oil' else C['gas']
            ax.plot(lon, lat, marker='D', markersize=9, linestyle='none',
                    color=col, markeredgecolor=C['border'],
                    markeredgewidth=0.7, zorder=10)
            ax.text(lon + 0.13, lat + 0.13, name, fontsize=6.5,
                    color=col, ha='left', va='bottom',
                    path_effects=halo(2.5), zorder=11)

    # ── title ──────────────────────────────────────────────────────────────────
    fig.text(0.02, 0.97, 'KURDISH GROUPS, BASES & OIL',
             fontsize=17, fontweight='bold', color=C['text_dark'],
             va='top', ha='left')
    fig.text(0.02, 0.935, 'Iraq / Iran border region — faction territories, US military presence, and oil infrastructure, c. 2026',
             fontsize=8.5, color=C['text_mid'], va='top', ha='left', fontstyle='italic')

    # ── legend ────────────────────────────────────────────────────────────────
    handles = [
        mpatches.Patch(facecolor=C['kdp'],     edgecolor='#2a5a8a', linewidth=1.5,
                       label='KDP — Dohuk & Erbil'),
        mpatches.Patch(facecolor=C['puk'],     edgecolor='#4a80aa', linewidth=1.5,
                       label='PUK — Sulaimaniyah'),
        mpatches.Patch(facecolor=C['iranian'], edgecolor='#8b3030', linewidth=1.2,
                       linestyle='--', label='Kurdish provinces — Iran'),
        mpatches.Patch(facecolor=C['syrian'],  edgecolor='#3a6e3a', linewidth=1.2,
                       label='YPG / SDF — Rojava'),
        mpatches.Patch(facecolor=C['pkk'],     edgecolor='#6a2a2a', linewidth=1.2,
                       linestyle='--', label='PKK / PJAK — Qandil zone'),
        mlines.Line2D([0], [0], marker='o', linestyle='none',
                      markerfacecolor=C['sinjar'], markeredgecolor='white',
                      markersize=10, label='Sinjar / YBŞ'),
        mlines.Line2D([0], [0], marker='*', linestyle='none',
                      markerfacecolor=C['base_act'], markeredgecolor=C['border'],
                      markersize=14, label='US base — active'),
        mlines.Line2D([0], [0], marker='*', linestyle='none',
                      markerfacecolor='none', markeredgecolor=C['base_old'],
                      markersize=14, label='US base — former'),
        mlines.Line2D([0], [0], marker='D', linestyle='none',
                      markerfacecolor=C['oil'], markeredgecolor=C['border'],
                      markersize=9, label='Oil field'),
        mlines.Line2D([0], [0], marker='D', linestyle='none',
                      markerfacecolor=C['gas'], markeredgecolor=C['border'],
                      markersize=9, label='Gas field'),
        mlines.Line2D([0], [0], marker='o', linestyle='none',
                      markerfacecolor=C['text_dark'], markeredgecolor='white',
                      markersize=5, label='City'),
    ]
    place_legend(ax, handles, 'Legend', 'lower right')

    # ── source ────────────────────────────────────────────────────────────────
    fig.text(0.99, 0.01,
             'Sources: geoBoundaries CC BY 4.0 · Natural Earth · CENTCOM public data',
             fontsize=6.5, color=C['text_lite'], ha='right', va='bottom')

    fig.subplots_adjust(top=0.92, bottom=0.03, left=0.02, right=0.98)
    fig.savefig(OUT2, dpi=200, bbox_inches='tight', facecolor=C['bg'])
    plt.close(fig)
    print(f'  → Saved {OUT2}')


# ─── main ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('Loading Natural Earth country boundaries...')
    countries = get_countries()

    print('Loading Kurdish admin regions from HTML...')
    admin = load_admin_gdf()
    print(f'  {len(admin)} features loaded')

    print('\nGenerating Map 1: Regional Political Kurdistan...')
    generate_map1(countries, admin)

    print('\nGenerating Map 2: Operational — Groups, Bases & Oil...')
    generate_map2(countries, admin)

    print('\nDone. Both maps saved to maps/')

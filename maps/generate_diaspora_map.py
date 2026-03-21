#!/usr/bin/env python3
"""
Russian emigration diaspora map — static journalist-style Mercator map.
Shows top 7 destination countries (choropleth) + artist hub city markers.

Output: images/russia_diaspora_map.png

Usage:
    cd /home/user/Portfolio
    python3 maps/generate_diaspora_map.py
"""

import io
import os
import sys
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import matplotlib.lines as mlines
import geopandas as gpd
import numpy as np
import requests
from shapely.geometry import Point, box
from pyproj import Transformer

# ─── paths ────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).parent.parent
MAPS_DIR = Path(__file__).parent
NE_CACHE = Path('/tmp/ne_50m')
OUT      = ROOT / 'images' / 'russia_diaspora_map.png'

# ─── editorial colour palette (warm newsprint / NYT-style) ────────────────────
C = dict(
    ocean      = '#A8C8D8',   # muted steel blue ocean
    land_base  = '#EDE6D4',   # warm parchment — neutral countries
    land_gray  = '#D8D0BC',   # slightly cooler for distant regions
    russia     = '#C8BCA8',   # muted tan — origin country
    russia_bd  = '#8A7A60',   # Russia border (warmer)
    border     = '#A09880',   # country borders (warm gray)
    border_hi  = '#786050',   # borders for highlighted countries

    # choropleth gradient: lightest (5%) → darkest (17%)
    dest_5     = '#F5D4A8',   # Israel 5% ~35k
    dest_6     = '#F0B870',   # Germany 6% ~40k
    dest_9     = '#E8944A',   # Serbia 9% ~60k
    dest_13    = '#D46828',   # Armenia 13% ~85k
    dest_15    = '#BC4415',   # Turkey & Kazakhstan 15%
    dest_17    = '#961005',   # Georgia 17% ~110k

    city_dot   = '#1A1A2E',   # artist hub dot
    russia_dot = '#6B0000',   # Russia arrow / label
    text_dark  = '#1A1A1A',
    text_mid   = '#4A4040',
    text_lite  = '#787060',
    text_white = '#FAF7F0',
    accent     = '#8B0000',
)

# ─── emigration data ──────────────────────────────────────────────────────────
# Source: The Bell (~650k confirmed non-returnees), ZOiS Berlin, national data
DESTINATIONS = [
    # (NaturalEarth ADMIN name, pct, approx_count, color_key, label_offset_deg_x, label_offset_deg_y)
    # offsets spread deliberately into open areas with long leader lines
    ('Georgia',             17, '~110k', 'dest_17', -14,   +5  ),  # west into Black Sea
    ('Turkey',              15, '~100k', 'dest_15', +2,   +11  ),  # north, above Black Sea
    ('Kazakhstan',          15, '~95k',  'dest_15', +7,    +2  ),
    ('Armenia',             13, '~85k',  'dest_13', +18,   -3  ),  # far east, into Caspian
    ('Republic of Serbia',   9, '~60k',  'dest_9',  -7,   +7   ),  # northwest into central Europe
    ('Germany',              6, '~40k',  'dest_6',   0,    +2  ),
    ('Israel',               5, '~35k',  'dest_5',  +13,   -8  ),  # far right+south into Arabia
]

# ─── artist hub cities (lon, lat) ─────────────────────────────────────────────
CITIES = [
    ('Tbilisi',       44.83,  41.69,  'right'),
    ('Berlin',        13.40,  52.52,  'right'),
    ('Los Angeles', -118.24,  34.05,  'left' ),
    ('London',        -0.13,  51.51,  'left' ),
    ('Belgrade',      20.46,  44.82,  'right'),
    ('Yerevan',       44.51,  40.18,  'left' ),
    ('Istanbul',      28.97,  41.01,  'right'),
]

# ─── Natural Earth download (same pattern as generate_maps.py) ────────────────
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
                r = requests.get(url, timeout=120)
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


def halo(lw=2.5, fg='white'):
    return [pe.withStroke(linewidth=lw, foreground=fg)]


def lonlat_to_mercator(lon, lat):
    """Convert WGS84 lon/lat to Web Mercator (EPSG:3857) x, y."""
    transformer = Transformer.from_crs('EPSG:4326', 'EPSG:3857', always_xy=True)
    x, y = transformer.transform(lon, lat)
    return x, y


def generate_map(countries: gpd.GeoDataFrame) -> None:
    # ── reproject to Web Mercator ──────────────────────────────────────────────
    world_merc = countries.to_crs('EPSG:3857')

    # Mercator extent: clip ~80°N/S to avoid infinity at poles
    # lon -175..175, lat -70..80  → meters
    xmin, ymin = lonlat_to_mercator(-175, -68)
    xmax, ymax = lonlat_to_mercator( 175,  80)

    # Build destination lookup
    dest_map = {row[0]: row for row in DESTINATIONS}

    fig, ax = plt.subplots(figsize=(20, 11))
    fig.patch.set_facecolor(C['ocean'])
    ax.set_facecolor(C['ocean'])

    # ── 1. Base land layer — all countries neutral ─────────────────────────────
    world_merc.plot(ax=ax,
                    facecolor=C['land_base'],
                    edgecolor=C['border'],
                    linewidth=0.4,
                    zorder=2)

    # ── 2. Russia — slightly muted (origin) ───────────────────────────────────
    russia = world_merc[world_merc['ADMIN'] == 'Russia']
    russia.plot(ax=ax,
                facecolor=C['russia'],
                edgecolor=C['russia_bd'],
                linewidth=0.5,
                zorder=3)

    # ── 3. Destination countries — choropleth ─────────────────────────────────
    for name, pct, count, color_key, dx, dy in DESTINATIONS:
        gdf = world_merc[world_merc['ADMIN'] == name]
        if gdf.empty:
            print(f'  WARNING: country not found: {name}')
            continue
        gdf.plot(ax=ax,
                 facecolor=C[color_key],
                 edgecolor=C['border_hi'],
                 linewidth=0.7,
                 zorder=4)

    # ── 4. Country labels (name + pct + count) ────────────────────────────────
    for name, pct, count, color_key, dx, dy in DESTINATIONS:
        gdf = world_merc[world_merc['ADMIN'] == name]
        if gdf.empty:
            continue
        centroid = gdf.geometry.centroid.iloc[0]
        cx, cy = centroid.x, centroid.y

        # Mercator degrees-to-meters offset (rough: 1 deg lat ≈ 111km = 111000m)
        ox = dx * 111_000 * np.cos(np.radians(30))
        oy = dy * 111_000

        label_x = cx + ox
        label_y = cy + oy

        # Display name (strip "Republic of" prefix for labels)
        display_name = name.replace('Republic of ', '')

        # All small/offset countries use annotate with arrow; large countries use plain text
        needs_arrow = name in ('Georgia', 'Armenia', 'Israel', 'Republic of Serbia', 'Turkey')

        if needs_arrow:
            ax.annotate(
                f'{display_name.upper()}\n{pct}%  ({count})',
                xy=(cx, cy),
                xytext=(label_x, label_y),
                fontsize=7,
                fontfamily='sans-serif',
                fontweight='bold',
                color=C['text_dark'],
                ha='center',
                va='center',
                arrowprops=dict(arrowstyle='-', color=C['text_mid'],
                                lw=0.8, shrinkA=2, shrinkB=2),
                zorder=8,
                path_effects=halo(2.5, C['text_white']),
            )
        else:
            ax.text(
                label_x, label_y,
                f'{display_name.upper()}\n{pct}%  ({count})',
                fontsize=7.5,
                fontfamily='sans-serif',
                fontweight='bold',
                color=C['text_dark'],
                ha='center',
                va='center',
                zorder=8,
                path_effects=halo(2.5, C['text_white']),
            )

    # ── 5. Russia label ───────────────────────────────────────────────────────
    russia_gdf = world_merc[world_merc['ADMIN'] == 'Russia']
    if not russia_gdf.empty:
        # Place label near western Russia (more readable)
        rx, ry = lonlat_to_mercator(55, 60)
        ax.text(rx, ry, 'RUSSIA\n(origin)',
                fontsize=7,
                fontfamily='sans-serif',
                fontstyle='italic',
                color=C['russia_dot'],
                ha='center',
                va='center',
                zorder=8,
                path_effects=halo(2.5, C['text_white']),
                )

    # ── 6. Artist hub cities ──────────────────────────────────────────────────
    for city_name, lon, lat, ha_side in CITIES:
        mx, my = lonlat_to_mercator(lon, lat)

        # Dot
        ax.plot(mx, my,
                marker='o',
                markersize=5,
                markerfacecolor=C['city_dot'],
                markeredgecolor='white',
                markeredgewidth=0.8,
                zorder=10)

        # Label offset
        pad_x = 180_000 if ha_side == 'right' else -180_000
        ax.text(mx + pad_x, my,
                city_name,
                fontsize=6,
                fontfamily='sans-serif',
                fontweight='bold',
                color=C['city_dot'],
                ha=ha_side,
                va='center',
                zorder=10,
                path_effects=halo(2.0, C['text_white']),
                )

    # ── 7. Title block (upper-left inset) ────────────────────────────────────
    title_x = xmin + (xmax - xmin) * 0.01
    title_y = ymax - (ymax - ymin) * 0.04

    ax.text(title_x, title_y,
            'WHERE RUSSIANS WENT',
            fontsize=16,
            fontfamily='sans-serif',
            fontweight='bold',
            color=C['text_dark'],
            va='top',
            zorder=12,
            path_effects=halo(3, C['text_white']),
            )
    ax.text(title_x, title_y - (ymax - ymin) * 0.045,
            'Top destinations for Russian emigrants, 2022–2025',
            fontsize=8.5,
            fontfamily='sans-serif',
            fontstyle='italic',
            color=C['text_mid'],
            va='top',
            zorder=12,
            path_effects=halo(2.5, C['text_white']),
            )
    ax.text(title_x, title_y - (ymax - ymin) * 0.082,
            '~650,000 confirmed non-returnees  ·  Source: The Bell / ZOiS Berlin',
            fontsize=7,
            fontfamily='sans-serif',
            color=C['text_lite'],
            va='top',
            zorder=12,
            path_effects=halo(2, C['text_white']),
            )

    # ── 8. Legend ─────────────────────────────────────────────────────────────
    legend_patches = [
        mpatches.Patch(facecolor=C['russia'],   edgecolor=C['border'], label='Russia — origin'),
        mpatches.Patch(facecolor=C['dest_17'],  edgecolor=C['border_hi'], label='17%  ~110k emigrants'),
        mpatches.Patch(facecolor=C['dest_15'],  edgecolor=C['border_hi'], label='15%  ~95–100k'),
        mpatches.Patch(facecolor=C['dest_13'],  edgecolor=C['border_hi'], label='13%  ~85k'),
        mpatches.Patch(facecolor=C['dest_9'],   edgecolor=C['border_hi'], label=' 9%  ~60k'),
        mpatches.Patch(facecolor=C['dest_6'],   edgecolor=C['border_hi'], label=' 6%  ~40k'),
        mpatches.Patch(facecolor=C['dest_5'],   edgecolor=C['border_hi'], label=' 5%  ~35k'),
    ]
    city_handle = mlines.Line2D([], [],
                                marker='o', markersize=5,
                                markerfacecolor=C['city_dot'],
                                markeredgecolor='white',
                                markeredgewidth=0.8,
                                linestyle='None',
                                label='Artist hub city')

    leg = ax.legend(
        handles=legend_patches + [city_handle],
        title='SHARE OF ~650K EMIGRANTS',
        title_fontsize=6.5,
        fontsize=7,
        loc='lower left',
        frameon=True,
        facecolor=C['land_base'],
        edgecolor=C['border'],
        framealpha=0.92,
        borderpad=0.9,
        labelspacing=0.5,
        handlelength=1.4,
        handleheight=1.1,
    )
    leg.get_title().set_color(C['text_mid'])
    leg.get_title().set_fontweight('bold')
    for t in leg.get_texts():
        t.set_color(C['text_dark'])

    # ── 9. Map extent & frame ─────────────────────────────────────────────────
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_edgecolor(C['border'])
        sp.set_linewidth(1.2)

    # ── 10. Graticule lines (subtle lat/lon grid) ────────────────────────────
    for lon_line in range(-150, 181, 30):
        lx, _ = lonlat_to_mercator(lon_line, 0)
        ax.axvline(lx, color='white', linewidth=0.3, alpha=0.5, zorder=1)
    for lat_line in range(-60, 81, 30):
        _, ly = lonlat_to_mercator(0, lat_line)
        ax.axhline(ly, color='white', linewidth=0.3, alpha=0.5, zorder=1)

    # ── 11. Source note at bottom ────────────────────────────────────────────
    fig.text(0.5, 0.01,
             'Sources: The Bell (2024); ZOiS Berlin Report 4/2024; national immigration services. '
             'Percentages are estimates; total emigration 650k–900k depending on methodology.',
             ha='center',
             fontsize=6.5,
             fontstyle='italic',
             color=C['text_lite'],
             )

    plt.tight_layout(pad=0.3)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150, bbox_inches='tight',
                facecolor=C['ocean'], edgecolor='none')
    plt.close(fig)
    print(f'  Saved: {OUT}')
    print(f'  Size:  {OUT.stat().st_size // 1024} KB')


def main():
    print('Generating Russian diaspora map...')
    print('  Loading Natural Earth country boundaries...')
    countries = get_countries()
    print(f'  Loaded {len(countries)} countries.')
    generate_map(countries)
    print('Done.')


if __name__ == '__main__':
    main()

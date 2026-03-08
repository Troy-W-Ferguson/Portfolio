#!/usr/bin/env python3
"""
KURDISTAN ADMIN BOUNDARIES — Data Extraction Script
====================================================

INSTRUCTIONS FOR TREY:

1. Download these 4 simplified GeoJSON files from geoBoundaries:
   
   Iraq ADM1:
   https://www.geoboundaries.org/api/current/gbOpen/IRQ/ADM1/
   (Click the link, find "gjDownloadURL" in the JSON response, open THAT url to get the .geojson)
   
   OR go directly to:
   https://github.com/wmgeolab/geoBoundaries/tree/main/releaseData/gbOpen/IRQ/ADM1
   and download the simplified geojson.
   
   Turkey ADM1:
   https://www.geoboundaries.org/api/current/gbOpen/TUR/ADM1/
   
   Iran ADM1:
   https://www.geoboundaries.org/api/current/gbOpen/IRN/ADM1/
   
   Syria ADM1:
   https://www.geoboundaries.org/api/current/gbOpen/SYR/ADM1/

   Save them as:
   - irq_adm1.geojson
   - tur_adm1.geojson
   - irn_adm1.geojson
   - syr_adm1.geojson

2. Put them in the same folder as this script.

3. Run: python3 build_kurdistan_geojson.py

4. It produces: kurdistan_admin_boundaries.geojson
   
5. Upload that file to your GitHub repo (e.g. in a /data/ folder).

6. Update the GEOJSON_URL in the HTML to point to:
   https://yourusername.github.io/your-repo/data/kurdistan_admin_boundaries.geojson

The script extracts ONLY the Kurdish-majority admin units and tags each with
country, type (krg/kurdish-majority), and color coding.
"""

import json
import sys
import os

# Kurdish-majority admin units by country
# Following Britannica's definition + Encyclopaedia of Islam
KURDISH_UNITS = {
    'IRQ': {
        'names': [
            'Arbil', 'Erbil', 'Irbil',
            'Sulaymaniyah', 'As-Sulaymaniyah', 'Sulaimaniya',
            'Dahuk', 'Duhok', 'Dihok', 'Dohuk',
            'Halabja',
        ],
        'color': '#5ba3e8',
        'type': 'krg',
        'label': 'Kurdistan Region of Iraq (KRG)',
    },
    'TUR': {
        'names': [
            'Diyarbakir', 'Diyarbakır',
            'Batman',
            'Siirt',
            'Sirnak', 'Şırnak',
            'Hakkari', 'Hakkâri',
            'Van',
            'Mus', 'Muş',
            'Bitlis',
            'Bingol', 'Bingöl',
            'Tunceli',
            'Elazig', 'Elazığ',
            'Mardin',
            'Sanliurfa', 'Şanlıurfa',
            'Agri', 'Ağrı',
            'Kars',
            'Igdir', 'Iğdır',
            'Adiyaman', 'Adıyaman',
            'Malatya',
        ],
        'color': '#d4a843',
        'type': 'turkish-kurdish',
        'label': 'Northern Kurdistan (Turkey)',
    },
    'IRN': {
        'names': [
            'Kordestan', 'Kurdistan', 'Kurdistān',
            'Kermanshah', 'Kermānshāh',
            'Ilam', 'Īlām',
            'West Azerbaijan', 'West Azarbaijan', 'Āz̄arbāyjān-e Gharbī',
        ],
        'color': '#cc5555',
        'type': 'iranian-kurdish',
        'label': 'Eastern Kurdistan (Iran)',
    },
    'SYR': {
        'names': [
            'Al-Hasakah', 'Al-Hasakeh', 'Hasakah', 'Al Hasakah',
        ],
        'color': '#55aa55',
        'type': 'syrian-kurdish',
        'label': 'Western Kurdistan / Rojava (Syria)',
    },
}

def name_matches(feature_name, target_names):
    """Check if a feature name matches any target name (case-insensitive, partial match)."""
    if not feature_name:
        return False
    fn = feature_name.lower().strip()
    for tn in target_names:
        if tn.lower() in fn or fn in tn.lower():
            return True
    return False

def extract_kurdish_features(geojson_path, country_code):
    """Extract Kurdish-majority features from a country's ADM1 GeoJSON."""
    config = KURDISH_UNITS[country_code]
    
    with open(geojson_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    features = []
    all_names = []
    
    for feat in data.get('features', []):
        props = feat.get('properties', {})
        # Try common property name fields
        name = (props.get('shapeName') or props.get('NAME_1') or 
                props.get('name') or props.get('ADM1_EN') or 
                props.get('admin1Name') or '')
        
        all_names.append(name)
        
        if name_matches(name, config['names']):
            # Add our metadata
            feat['properties']['_country'] = country_code
            feat['properties']['_type'] = config['type']
            feat['properties']['_color'] = config['color']
            feat['properties']['_label'] = config['label']
            feat['properties']['_name'] = name
            features.append(feat)
            print(f"  ✓ {country_code}: {name}")
    
    print(f"  Found {len(features)}/{len(all_names)} Kurdish-majority units in {country_code}")
    if len(features) == 0:
        print(f"  WARNING: No matches found! Available names: {all_names[:10]}")
    
    return features

def simplify_coordinates(coords, tolerance=0.005):
    """
    Simple Douglas-Peucker-like simplification to reduce file size.
    Keeps every Nth point based on tolerance.
    """
    if len(coords) <= 20:
        return coords
    
    # Keep roughly 1 point per tolerance degrees
    simplified = [coords[0]]
    for i in range(1, len(coords)):
        dx = coords[i][0] - simplified[-1][0]
        dy = coords[i][1] - simplified[-1][1]
        if (dx*dx + dy*dy) > tolerance*tolerance:
            simplified.append(coords[i])
    
    # Always keep the last point to close the polygon
    if simplified[-1] != coords[-1]:
        simplified.append(coords[-1])
    
    return simplified

def simplify_geometry(geometry, tolerance=0.005):
    """Simplify a GeoJSON geometry to reduce file size."""
    if geometry['type'] == 'Polygon':
        geometry['coordinates'] = [
            simplify_coordinates(ring, tolerance) 
            for ring in geometry['coordinates']
        ]
    elif geometry['type'] == 'MultiPolygon':
        geometry['coordinates'] = [
            [simplify_coordinates(ring, tolerance) for ring in polygon]
            for polygon in geometry['coordinates']
        ]
    return geometry

def main():
    files = {
        'IRQ': 'irq_adm1.geojson',
        'TUR': 'tur_adm1.geojson',
        'IRN': 'irn_adm1.geojson',
        'SYR': 'syr_adm1.geojson',
    }
    
    all_features = []
    
    for country_code, filename in files.items():
        if not os.path.exists(filename):
            print(f"⚠ {filename} not found — skipping {country_code}")
            continue
        
        print(f"\nProcessing {country_code} from {filename}...")
        features = extract_kurdish_features(filename, country_code)
        
        # Simplify geometries to reduce file size
        for feat in features:
            feat['geometry'] = simplify_geometry(feat['geometry'], tolerance=0.008)
        
        all_features.extend(features)
    
    if not all_features:
        print("\n✗ No features extracted! Check that the GeoJSON files are in the same directory.")
        sys.exit(1)
    
    # Build combined GeoJSON
    combined = {
        "type": "FeatureCollection",
        "properties": {
            "name": "Kurdistan Administrative Boundaries",
            "description": "Kurdish-majority administrative units across Iraq, Turkey, Iran, and Syria",
            "source": "geoBoundaries (CC BY 4.0, William & Mary geoLab)",
            "methodology": "Following Encyclopaedia Britannica and Encyclopaedia of Islam definitions",
            "generated": "2026-03-07",
        },
        "features": all_features
    }
    
    output_path = 'kurdistan_admin_boundaries.geojson'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, ensure_ascii=False)
    
    size_kb = os.path.getsize(output_path) / 1024
    print(f"\n✓ Combined GeoJSON saved: {output_path}")
    print(f"  {len(all_features)} features, {size_kb:.0f} KB")
    print(f"\n  Upload this file to your GitHub repo and update the URL in the HTML.")

if __name__ == '__main__':
    main()

"""Generate base.json + empty businesses.json for a new World Cup host city.

The schema follows existing cities (data/cities/dallas/base.json etc.):
  - 14 nodes with legacy IDs (dfw_airport, downtown_dallas, texas_live, etc.)
    These IDs are preserved across all cities so the simulator code stays generic.
  - 20 edges connecting nodes (computed from lat/lng + travel-time multiplier)
  - 10 zones, each anchored to a node

Usage:
    python scripts/generate_city_base.py atlanta
    python scripts/generate_city_base.py --all
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CITIES_DIR = ROOT / "data" / "cities"


# ---------------------------------------------------------------------------
# Per-city config — 14 nodes + city info
# Coordinates are real (Mercedes-Benz Stadium, Lincoln Financial Field, etc.)
# ---------------------------------------------------------------------------
CITY_BASES = {
    "atlanta": {
        "city": {
            "city_id": "atlanta",
            "name": "Atlanta",
            "venue_name": "Mercedes-Benz Stadium",
            "venue_capacity": 71000,
            "country": "USA",
            "timezone": "America/New_York",
            "default_map_center": [-84.388, 33.755],
            "default_map_zoom": 11.0,
        },
        "nodes": {
            # legacy_id: (lat, lng, label)
            "dfw_airport":         (33.6407, -84.4277, "Hartsfield-Jackson Atlanta International Airport"),
            "grapevine_junction":  (33.6800, -84.4200, "I-75/I-85 South Gateway"),
            "las_colinas":         (33.8487, -84.3733, "Buckhead Hotel District"),
            "irving_gateway":      (33.7700, -84.3850, "Midtown Connector"),
            "design_district":     (33.7831, -84.3831, "Midtown Atlanta"),
            "downtown_dallas":     (33.7588, -84.3902, "Downtown Atlanta"),
            "uptown":              (33.7920, -84.3705, "Old Fourth Ward"),
            "deep_ellum":          (33.7621, -84.3504, "Inman Park / Little Five Points"),
            "arlington_north":     (33.7595, -84.3970, "Castleberry Hill"),
            "stadium":             (33.7553, -84.4006, "Mercedes-Benz Stadium"),
            "texas_live":          (33.7568, -84.3968, "Centennial Olympic Park District"),
            "arlington_hotels":    (33.7615, -84.3935, "Downtown Stadium Hotels"),
            "local_neighborhoods": (33.7390, -84.4180, "West End Neighborhoods"),
            "fanzone":             (33.7600, -84.3935, "Centennial Olympic Park Fan Zone"),
        },
        "zone_names": {
            "stadium_zone":         "Mercedes-Benz Stadium Bowl",
            "fanzone_zone":         "Atlanta Fan Zone",
            "texas_live_zone":      "Centennial Olympic Park District",
            "arlington_hotels_zone": "Downtown Stadium Hotels",
            "local_zone":           "West End Neighborhoods",
            "las_colinas_zone":     "Buckhead Hotel District",
            "downtown_zone":        "Downtown Atlanta",
            "uptown_zone":          "Old Fourth Ward",
            "deep_ellum_zone":      "Inman Park / Little Five Points",
            "airport_zone":         "Hartsfield-Jackson ATL Airport",
        },
    },
    "philadelphia": {
        "city": {
            "city_id": "philadelphia",
            "name": "Philadelphia",
            "venue_name": "Lincoln Financial Field",
            "venue_capacity": 67594,
            "country": "USA",
            "timezone": "America/New_York",
            "default_map_center": [-75.165, 39.953],
            "default_map_zoom": 11.0,
        },
        "nodes": {
            "dfw_airport":         (39.8744, -75.2424, "Philadelphia International Airport"),
            "grapevine_junction":  (39.8810, -75.1984, "I-95 South Gateway"),
            "las_colinas":         (39.9526, -75.1652, "Center City Hotel District"),
            "irving_gateway":      (39.9240, -75.1750, "Avenue of the Arts Connector"),
            "design_district":     (39.9622, -75.1731, "Rittenhouse Square / Arts District"),
            "downtown_dallas":     (39.9526, -75.1652, "Center City Philadelphia"),
            "uptown":              (39.9569, -75.1474, "Old City"),
            "deep_ellum":          (39.9737, -75.1410, "Northern Liberties / Fishtown"),
            "arlington_north":     (39.9100, -75.1700, "Stadium District North"),
            "stadium":             (39.9008, -75.1675, "Lincoln Financial Field"),
            "texas_live":          (39.9080, -75.1690, "Stadium Entertainment Plaza"),
            "arlington_hotels":    (39.9050, -75.1620, "Stadium Hotel Cluster"),
            "local_neighborhoods": (39.9320, -75.1820, "South Philadelphia Neighborhoods"),
            "fanzone":             (39.9095, -75.1715, "Philadelphia Fan Zone"),
        },
        "zone_names": {
            "stadium_zone":         "Lincoln Financial Field Bowl",
            "fanzone_zone":         "Philadelphia Fan Zone",
            "texas_live_zone":      "Stadium Entertainment Plaza",
            "arlington_hotels_zone": "Stadium Hotel Cluster",
            "local_zone":           "South Philadelphia Neighborhoods",
            "las_colinas_zone":     "Center City Hotel District",
            "downtown_zone":        "Center City Philadelphia",
            "uptown_zone":          "Old City",
            "deep_ellum_zone":      "Northern Liberties / Fishtown",
            "airport_zone":         "Philadelphia International Airport",
        },
    },
    "seattle": {
        "city": {
            "city_id": "seattle",
            "name": "Seattle",
            "venue_name": "Lumen Field",
            "venue_capacity": 68740,
            "country": "USA",
            "timezone": "America/Los_Angeles",
            "default_map_center": [-122.3321, 47.6062],
            "default_map_zoom": 11.0,
        },
        "nodes": {
            "dfw_airport":         (47.4502, -122.3088, "Seattle-Tacoma International Airport"),
            "grapevine_junction":  (47.5300, -122.3050, "I-5 South Gateway"),
            "las_colinas":         (47.6232, -122.3563, "Belltown / Queen Anne Hotels"),
            "irving_gateway":      (47.6035, -122.3300, "Pioneer Square Connector"),
            "design_district":     (47.6080, -122.3400, "Pike Place / Waterfront"),
            "downtown_dallas":     (47.6062, -122.3321, "Downtown Seattle"),
            "uptown":              (47.6155, -122.3460, "Belltown"),
            "deep_ellum":          (47.6206, -122.3128, "Capitol Hill"),
            "arlington_north":     (47.5995, -122.3320, "Stadium District North"),
            "stadium":             (47.5952, -122.3316, "Lumen Field"),
            "texas_live":          (47.5970, -122.3320, "Pioneer Square Entertainment"),
            "arlington_hotels":    (47.6010, -122.3340, "Stadium Hotel Cluster"),
            "local_neighborhoods": (47.5710, -122.3290, "SoDo / Beacon Hill"),
            "fanzone":             (47.5985, -122.3325, "Seattle Fan Zone"),
        },
        "zone_names": {
            "stadium_zone":         "Lumen Field Bowl",
            "fanzone_zone":         "Seattle Fan Zone",
            "texas_live_zone":      "Pioneer Square Entertainment",
            "arlington_hotels_zone": "Stadium Hotel Cluster",
            "local_zone":           "SoDo / Beacon Hill",
            "las_colinas_zone":     "Belltown / Queen Anne Hotels",
            "downtown_zone":        "Downtown Seattle",
            "uptown_zone":          "Belltown",
            "deep_ellum_zone":      "Capitol Hill",
            "airport_zone":         "Seattle-Tacoma International Airport",
        },
    },
    "vancouver": {
        "city": {
            "city_id": "vancouver",
            "name": "Vancouver",
            "venue_name": "BC Place",
            "venue_capacity": 54500,
            "country": "Canada",
            "timezone": "America/Vancouver",
            "default_map_center": [-123.1207, 49.2827],
            "default_map_zoom": 11.0,
        },
        "nodes": {
            "dfw_airport":         (49.1947, -123.1792, "Vancouver International Airport (YVR)"),
            "grapevine_junction":  (49.2200, -123.1500, "Granville Bridge Gateway"),
            "las_colinas":         (49.2870, -123.1340, "West End / Coal Harbour Hotels"),
            "irving_gateway":      (49.2780, -123.1180, "Yaletown Connector"),
            "design_district":     (49.2730, -123.1240, "False Creek / Yaletown"),
            "downtown_dallas":     (49.2827, -123.1207, "Downtown Vancouver"),
            "uptown":              (49.2750, -123.1230, "Yaletown"),
            "deep_ellum":          (49.2820, -123.1010, "Gastown / Chinatown"),
            "arlington_north":     (49.2790, -123.1160, "Stadium District North"),
            "stadium":             (49.2767, -123.1119, "BC Place"),
            "texas_live":          (49.2780, -123.1130, "Stadium Entertainment District"),
            "arlington_hotels":    (49.2770, -123.1145, "Stadium Hotel Cluster"),
            "local_neighborhoods": (49.2670, -123.1135, "Mount Pleasant Neighborhoods"),
            "fanzone":             (49.2780, -123.1145, "Vancouver Fan Zone"),
        },
        "zone_names": {
            "stadium_zone":         "BC Place Bowl",
            "fanzone_zone":         "Vancouver Fan Zone",
            "texas_live_zone":      "Stadium Entertainment District",
            "arlington_hotels_zone": "Stadium Hotel Cluster",
            "local_zone":           "Mount Pleasant Neighborhoods",
            "las_colinas_zone":     "West End / Coal Harbour Hotels",
            "downtown_zone":        "Downtown Vancouver",
            "uptown_zone":          "Yaletown",
            "deep_ellum_zone":      "Gastown / Chinatown",
            "airport_zone":         "Vancouver International Airport (YVR)",
        },
    },
    "guadalajara": {
        "city": {
            "city_id": "guadalajara",
            "name": "Guadalajara",
            "venue_name": "Estadio Akron",
            "venue_capacity": 49850,
            "country": "Mexico",
            "timezone": "America/Mexico_City",
            "default_map_center": [-103.3496, 20.6597],
            "default_map_zoom": 11.0,
        },
        "nodes": {
            "dfw_airport":         (20.5218, -103.3107, "Aeropuerto Internacional de Guadalajara (GDL)"),
            "grapevine_junction":  (20.5800, -103.3500, "Periférico Sur Gateway"),
            "las_colinas":         (20.6770, -103.4060, "Zapopan Hotel District"),
            "irving_gateway":      (20.6700, -103.3650, "Avenida Vallarta Connector"),
            "design_district":     (20.6730, -103.3760, "Providencia / Chapultepec"),
            "downtown_dallas":     (20.6736, -103.3440, "Centro Histórico Guadalajara"),
            "uptown":              (20.6705, -103.3835, "Chapultepec Nightlife"),
            "deep_ellum":          (20.6780, -103.3500, "Tlaquepaque / Andador"),
            "arlington_north":     (20.6810, -103.4530, "Stadium District North"),
            "stadium":             (20.6817, -103.4625, "Estadio Akron"),
            "texas_live":          (20.6800, -103.4580, "Estadio Entertainment Plaza"),
            "arlington_hotels":    (20.6790, -103.4540, "Stadium Hotel Cluster"),
            "local_neighborhoods": (20.6480, -103.3370, "Tlaquepaque Neighborhoods"),
            "fanzone":             (20.6810, -103.4570, "Guadalajara Fan Zone"),
        },
        "zone_names": {
            "stadium_zone":         "Estadio Akron Bowl",
            "fanzone_zone":         "Guadalajara Fan Zone",
            "texas_live_zone":      "Estadio Entertainment Plaza",
            "arlington_hotels_zone": "Stadium Hotel Cluster",
            "local_zone":           "Tlaquepaque Neighborhoods",
            "las_colinas_zone":     "Zapopan Hotel District",
            "downtown_zone":        "Centro Histórico Guadalajara",
            "uptown_zone":          "Chapultepec Nightlife",
            "deep_ellum_zone":      "Tlaquepaque / Andador",
            "airport_zone":         "Guadalajara International Airport (GDL)",
        },
    },
}


# ---------------------------------------------------------------------------
# Edge template (same connectivity for every city, distances computed per-city)
# ---------------------------------------------------------------------------
EDGE_TEMPLATE = [
    ("dfw_grapevine",            "dfw_airport",         "grapevine_junction",  "highway",  8200),
    ("grapevine_las_colinas",    "grapevine_junction",  "las_colinas",         "highway",  7800),
    ("las_colinas_irving",       "las_colinas",         "irving_gateway",      "highway",  7600),
    ("irving_design",            "irving_gateway",      "design_district",     "arterial", 8900),
    ("design_downtown",          "design_district",     "downtown_dallas",     "arterial", 5400),
    ("downtown_uptown",          "downtown_dallas",     "uptown",              "arterial", 3200),
    ("downtown_deep_ellum",      "downtown_dallas",     "deep_ellum",          "arterial", 2800),
    ("downtown_stadium",         "downtown_dallas",     "stadium",             "highway",  9600),
    ("irving_stadium",           "irving_gateway",      "stadium",             "highway",  9300),
    ("arlington_north_stadium",  "arlington_north",     "stadium",             "arterial", 3400),
    ("texas_live_stadium",       "texas_live",          "stadium",             "local",    1900),
    ("arlington_hotels_stadium", "arlington_hotels",    "stadium",             "local",    2200),
    ("local_stadium",            "local_neighborhoods", "stadium",             "arterial", 3100),
    ("texas_live_fanzone",       "texas_live",          "fanzone",             "local",    1600),
    ("local_hotels",             "local_neighborhoods", "arlington_hotels",    "arterial", 2600),
    ("texas_live_arlington_north", "texas_live",        "arlington_north",     "local",    2400),
    ("fanzone_arlington_hotels", "fanzone",             "arlington_hotels",    "arterial", 2100),
    ("las_colinas_downtown",     "las_colinas",         "downtown_dallas",     "highway",  7000),
    ("design_uptown",            "design_district",     "uptown",              "arterial", 2500),
    ("design_stadium",           "design_district",     "stadium",             "highway",  6100),
]


# ---------------------------------------------------------------------------
# Zone template (same per city, names override per city)
# ---------------------------------------------------------------------------
ZONE_TEMPLATE = [
    # (id, kind, node_id, radius_m, focus_color)
    ("stadium_zone",         "stadium",       "stadium",             350,  "#F97316"),
    ("fanzone_zone",         "fanzone",       "fanzone",             450,  "#F4B942"),
    ("texas_live_zone",      "bar_cluster",   "texas_live",          600,  "#F43F5E"),
    ("arlington_hotels_zone", "hotel_cluster", "arlington_hotels",   700,  "#22C55E"),
    ("local_zone",           "residential",   "local_neighborhoods", 850,  "#64748B"),
    ("las_colinas_zone",     "hotel_cluster", "las_colinas",         780,  "#0EA5E9"),
    ("downtown_zone",        "hotel_cluster", "downtown_dallas",     950,  "#14B8A6"),
    ("uptown_zone",          "bar_cluster",   "uptown",              700,  "#8B5CF6"),
    ("deep_ellum_zone",      "bar_cluster",   "deep_ellum",          650,  "#EF4444"),
    ("airport_zone",         "transport",     "dfw_airport",         1100, "#3B82F6"),
]


# ---------------------------------------------------------------------------
# Geometry / road heuristics
# ---------------------------------------------------------------------------
def haversine_km(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    r = 6371.0
    p1 = math.radians(a_lat)
    p2 = math.radians(b_lat)
    dphi = math.radians(b_lat - a_lat)
    dl = math.radians(b_lng - a_lng)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def estimate_travel_minutes(distance_km: float, kind: str) -> int:
    """Rough travel time accounting for road type. Adds urban time for short hops."""
    speeds = {"highway": 55.0, "arterial": 30.0, "local": 22.0}  # km/h with traffic
    speed = speeds.get(kind, 30.0)
    minutes = (distance_km / speed) * 60.0
    # baseline overhead for stops/turns
    minutes += 1.5 if kind == "local" else 2.0
    return max(2, round(minutes))


def road_label(source: str, target: str, kind: str) -> str:
    """Generic placeholder road name; user can edit later if needed."""
    pretty = {
        "highway": "Inter-District Highway",
        "arterial": "Arterial Connector",
        "local": "Local Connector",
    }
    return pretty.get(kind, "Connector")


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def build_base(city_cfg: dict) -> dict:
    nodes_data = city_cfg["nodes"]
    nodes_out = []
    for node_id, (lat, lng, label) in nodes_data.items():
        nodes_out.append({"id": node_id, "label": label, "lat": lat, "lng": lng})

    edges_out = []
    for edge_id, source, target, kind, capacity in EDGE_TEMPLATE:
        s_lat, s_lng, _ = nodes_data[source]
        t_lat, t_lng, _ = nodes_data[target]
        dist_km = round(haversine_km(s_lat, s_lng, t_lat, t_lng), 1)
        travel = estimate_travel_minutes(dist_km, kind)
        edges_out.append({
            "id": edge_id,
            "source": source,
            "target": target,
            "road_name": road_label(source, target, kind),
            "capacity": capacity,
            "base_travel_minutes": travel,
            "distance_km": dist_km,
            "kind": kind,
            "bidirectional": True,
        })

    zones_out = []
    zone_names = city_cfg["zone_names"]
    for zone_id, kind, node_id, radius, color in ZONE_TEMPLATE:
        n_lat, n_lng, _ = nodes_data[node_id]
        zones_out.append({
            "id": zone_id,
            "name": zone_names[zone_id],
            "kind": kind,
            "node_id": node_id,
            "center": [n_lng, n_lat],
            "radius_m": radius,
            "focus_color": color,
        })

    return {
        "city": city_cfg["city"],
        "nodes": nodes_out,
        "edges": edges_out,
        "zones": zones_out,
        "provenance": {
            "seed_graph": "auto-generated host-city road simulation graph (legacy node IDs preserved)",
            "businesses": "to be enriched via Google Places + Hunter pipeline",
            "weather": "baseline match weather profile with city-local kickoff timing",
            "places_enrichment": "live Google Places overlay",
            "llm_recommendations": "heuristic by default, optionally upgraded through Anthropic",
        },
    }


def write_city(city_id: str) -> None:
    if city_id not in CITY_BASES:
        raise SystemExit(f"No config for city '{city_id}'. Available: {list(CITY_BASES)}")
    cfg = CITY_BASES[city_id]
    base = build_base(cfg)
    target_dir = CITIES_DIR / city_id
    target_dir.mkdir(parents=True, exist_ok=True)
    base_path = target_dir / "base.json"
    biz_path = target_dir / "businesses.json"

    with base_path.open("w", encoding="utf-8") as fh:
        json.dump(base, fh, indent=2, ensure_ascii=False)

    if not biz_path.exists():
        with biz_path.open("w", encoding="utf-8") as fh:
            json.dump({"businesses": []}, fh, indent=2, ensure_ascii=False)

    # Also create empty special_venues.json + edge_paths.json placeholders if missing
    for placeholder, default in [
        ("special_venues.json", {"special_venues": []}),
        ("edge_paths.json", {"paths": {}}),
    ]:
        p = target_dir / placeholder
        if not p.exists():
            with p.open("w", encoding="utf-8") as fh:
                json.dump(default, fh, indent=2, ensure_ascii=False)

    print(f"Wrote {base_path}  (nodes={len(base['nodes'])}, edges={len(base['edges'])}, zones={len(base['zones'])})", flush=True)
    print(f"Wrote {biz_path}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("city", nargs="?", help="City id to generate (e.g. atlanta)")
    parser.add_argument("--all", action="store_true", help="Generate all 5 missing cities")
    args = parser.parse_args()

    if args.all:
        for city_id in CITY_BASES:
            write_city(city_id)
    elif args.city:
        write_city(args.city)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

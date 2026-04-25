"""Enrich city businesses.json with Google Places + Hunter.io and export mailing list CSV.

Pipeline (in order, each step is its own flag):
    --enrich-seeded     Fill address/phone/website for seeded businesses (Google Places)
    (default)           Search Google Places for new businesses per zone
    --rescrape-emails   W1 + W2 email scraping (own site + Facebook fallback)
    --hunter-fill       Hunter Search API for businesses still without email
    --hunter-verify     Hunter Verification API for all emails
    --export-only       Skip everything, just write the CSV (chain filter applied)

Usage examples:
    python scripts/enrich_businesses.py --city dallas --enrich-seeded
    python scripts/enrich_businesses.py --city dallas
    python scripts/enrich_businesses.py --city dallas --rescrape-emails
    python scripts/enrich_businesses.py --city dallas --hunter-fill
    python scripts/enrich_businesses.py --city dallas --hunter-verify
    python scripts/enrich_businesses.py --city dallas --export-only
"""
from __future__ import annotations

import argparse
import csv
import functools
import html
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Always flush prints — fixes buffering when stdout is piped to a file (run_in_background)
print = functools.partial(print, flush=True)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CITIES_DIR = DATA_DIR / "cities"
MAILING_DIR = DATA_DIR / "mailing_lists"
RAW_DIR = DATA_DIR / "raw"
BLOCKLIST_PATH = DATA_DIR / "chain_blocklist.json"
HUNTER_CACHE_PATH = RAW_DIR / "hunter_cache.json"

load_dotenv(ROOT / ".env", encoding="utf-8-sig")


def _read_env_var(name: str) -> str:
    value = os.getenv(name, "")
    if value:
        return value
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


GOOGLE_API_KEY = _read_env_var("GOOGLE_MAPS_API_KEY")
HUNTER_API_KEY = _read_env_var("HUNTER_API_KEY")

PLACES_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.internationalPhoneNumber,places.nationalPhoneNumber,"
    "places.websiteUri,places.rating,places.userRatingCount,"
    "places.priceLevel,places.types,places.location,"
    "places.regularOpeningHours"
)

HUNTER_DOMAIN_SEARCH_URL = "https://api.hunter.io/v2/domain-search"
HUNTER_VERIFIER_URL = "https://api.hunter.io/v2/email-verifier"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
EMAIL_SKIP_PREFIXES = (
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "wordpress", "example", "your", "name@", "user@",
    "sentry", "wixpress", "webmaster@rciis", "classified@",
    "support@squarespace", "team@squarespace", "press@",
    "media@", "career", "jobs@", "hr@",
)
EMAIL_SKIP_DOMAINS = (
    "sentry.io", "wixpress.com", "example.com",
    "domain.com", "yourdomain.com", "godaddy.com",
    "wordpress.com", "wix.com", "squarespace.com",
    "rciis.com", "dallasobserver.com", "yelp.com",
    "tripadvisor.com", "facebook.com", "instagram.com",
    "twitter.com", "youtube.com", "google.com",
    "schema.org", "w3.org", "sentry.wixpress.com",
    "linkedin.com", "pinterest.com", "tiktok.com",
)

# Subpages we'll crawl for emails (W1)
SCRAPE_PATHS = (
    "", "/contact", "/contact-us", "/contacts",
    "/about", "/about-us",
    "/reservations", "/private-events", "/events",
    "/book", "/booking", "/info", "/footer",
    "/locations", "/our-team",
)


# ---------------------------------------------------------------------------
# Per-city zone configurations
# ---------------------------------------------------------------------------
CITY_CONFIGS: dict[str, dict[str, Any]] = {
    "dallas": {
        "country": "USA",
        "zones": {
            "texas_live_zone": {
                "node_id": "texas_live",
                "queries": [
                    ("sports bar Arlington Texas", ["bar"]),
                    ("bar restaurant Arlington Texas", ["bar", "restaurant"]),
                    ("pub Arlington Texas", ["bar"]),
                ],
                "search_radius_m": 1500,
                "default_type": "sports_bar",
            },
            "uptown_zone": {
                "node_id": "uptown",
                "queries": [
                    ("cocktail bar Uptown Dallas", ["bar"]),
                    ("wine bar Uptown Dallas", ["bar"]),
                    ("gastropub Uptown Dallas", ["bar", "restaurant"]),
                    ("neighborhood bar Uptown Dallas", ["bar"]),
                ],
                "search_radius_m": 1800,
                "default_type": "cocktail_bar",
            },
            "deep_ellum_zone": {
                "node_id": "deep_ellum",
                "queries": [
                    ("bar Deep Ellum Dallas", ["bar"]),
                    ("live music venue Deep Ellum Dallas", ["bar"]),
                    ("craft beer Deep Ellum Dallas", ["bar"]),
                    ("pub Deep Ellum Dallas", ["bar", "restaurant"]),
                ],
                "search_radius_m": 1500,
                "default_type": "sports_bar",
            },
            "downtown_zone": {
                "node_id": "downtown_dallas",
                "queries": [
                    ("boutique hotel Downtown Dallas", ["lodging"]),
                    ("independent hotel Downtown Dallas", ["lodging"]),
                    ("bar restaurant Downtown Dallas", ["bar", "restaurant"]),
                    ("rooftop bar Downtown Dallas", ["bar"]),
                ],
                "search_radius_m": 2200,
                "default_type": "sports_bar",
            },
            "arlington_hotels_zone": {
                "node_id": "arlington_hotels",
                "queries": [
                    ("boutique hotel Arlington Texas", ["lodging"]),
                    ("inn Arlington Texas", ["lodging"]),
                    ("bed and breakfast Arlington Texas", ["lodging"]),
                ],
                "search_radius_m": 2000,
                "default_type": "hotel",
            },
            "las_colinas_zone": {
                "node_id": "las_colinas",
                "queries": [
                    ("boutique hotel Las Colinas Irving", ["lodging"]),
                    ("inn Las Colinas Irving", ["lodging"]),
                    ("bar restaurant Las Colinas", ["bar", "restaurant"]),
                ],
                "search_radius_m": 2200,
                "default_type": "hotel",
            },
        },
    },
    "houston": {
        "country": "USA",
        "zones": {
            "texas_live_zone": {  # Stadium Entertainment District (NRG)
                "node_id": "texas_live",
                "queries": [
                    ("sports bar near NRG Stadium Houston", ["bar"]),
                    ("bar restaurant near NRG Park Houston", ["bar", "restaurant"]),
                    ("pub Houston Medical Center", ["bar"]),
                ],
                "search_radius_m": 1500,
                "default_type": "sports_bar",
            },
            "arlington_hotels_zone": {  # Stadium Hotel Cluster
                "node_id": "arlington_hotels",
                "queries": [
                    ("boutique hotel near NRG Stadium Houston", ["lodging"]),
                    ("inn Houston Medical Center", ["lodging"]),
                ],
                "search_radius_m": 2000,
                "default_type": "hotel",
            },
            "las_colinas_zone": {  # Galleria Hotel District
                "node_id": "las_colinas",
                "queries": [
                    ("boutique hotel Galleria Houston", ["lodging"]),
                    ("inn Uptown Houston Galleria", ["lodging"]),
                    ("bar restaurant Galleria Houston", ["bar", "restaurant"]),
                ],
                "search_radius_m": 2200,
                "default_type": "hotel",
            },
            "downtown_zone": {  # Downtown Houston
                "node_id": "downtown_dallas",  # legacy node id name in base.json
                "queries": [
                    ("boutique hotel Downtown Houston", ["lodging"]),
                    ("independent hotel Downtown Houston", ["lodging"]),
                    ("rooftop bar Downtown Houston", ["bar"]),
                    ("bar restaurant Downtown Houston", ["bar", "restaurant"]),
                ],
                "search_radius_m": 2200,
                "default_type": "sports_bar",
            },
            "uptown_zone": {  # Midtown Houston (bar cluster despite "uptown" name)
                "node_id": "uptown",
                "queries": [
                    ("cocktail bar Midtown Houston", ["bar"]),
                    ("wine bar Midtown Houston", ["bar"]),
                    ("gastropub Midtown Houston", ["bar", "restaurant"]),
                    ("neighborhood bar Midtown Houston", ["bar"]),
                ],
                "search_radius_m": 1800,
                "default_type": "cocktail_bar",
            },
            "deep_ellum_zone": {  # EaDo (East Downtown)
                "node_id": "deep_ellum",
                "queries": [
                    ("bar EaDo Houston", ["bar"]),
                    ("live music venue EaDo Houston", ["bar"]),
                    ("craft beer EaDo Houston", ["bar"]),
                    ("pub EaDo Houston", ["bar", "restaurant"]),
                ],
                "search_radius_m": 1500,
                "default_type": "sports_bar",
            },
        },
    },
    "kansas-city": {
        "country": "USA",
        "zones": {
            "texas_live_zone": {  # Truman Sports District
                "node_id": "texas_live",
                "queries": [
                    ("sports bar near Arrowhead Stadium Kansas City", ["bar"]),
                    ("bar restaurant near Kauffman Stadium", ["bar", "restaurant"]),
                    ("pub Kansas City Sports Complex", ["bar"]),
                ],
                "search_radius_m": 2000,
                "default_type": "sports_bar",
            },
            "arlington_hotels_zone": {  # Stadium Hotel Cluster
                "node_id": "arlington_hotels",
                "queries": [
                    ("hotel near Arrowhead Stadium Kansas City", ["lodging"]),
                    ("inn Kansas City Sports Complex", ["lodging"]),
                ],
                "search_radius_m": 2200,
                "default_type": "hotel",
            },
            "las_colinas_zone": {  # Country Club Plaza Hotels
                "node_id": "las_colinas",
                "queries": [
                    ("boutique hotel Country Club Plaza Kansas City", ["lodging"]),
                    ("inn Plaza Kansas City", ["lodging"]),
                    ("bar restaurant Country Club Plaza Kansas City", ["bar", "restaurant"]),
                ],
                "search_radius_m": 1800,
                "default_type": "hotel",
            },
            "downtown_zone": {  # Downtown Kansas City
                "node_id": "downtown_dallas",
                "queries": [
                    ("boutique hotel Downtown Kansas City", ["lodging"]),
                    ("independent hotel Downtown Kansas City", ["lodging"]),
                    ("rooftop bar Downtown Kansas City", ["bar"]),
                    ("bar restaurant Downtown Kansas City", ["bar", "restaurant"]),
                ],
                "search_radius_m": 2200,
                "default_type": "sports_bar",
            },
            "uptown_zone": {  # Power & Light District
                "node_id": "uptown",
                "queries": [
                    ("bar Power and Light District Kansas City", ["bar"]),
                    ("cocktail bar Power and Light Kansas City", ["bar"]),
                    ("gastropub Crossroads Kansas City", ["bar", "restaurant"]),
                ],
                "search_radius_m": 1500,
                "default_type": "sports_bar",
            },
            "deep_ellum_zone": {  # Westport
                "node_id": "deep_ellum",
                "queries": [
                    ("bar Westport Kansas City", ["bar"]),
                    ("live music venue Westport Kansas City", ["bar"]),
                    ("pub Westport Kansas City", ["bar", "restaurant"]),
                    ("neighborhood bar Westport", ["bar"]),
                ],
                "search_radius_m": 1500,
                "default_type": "sports_bar",
            },
        },
    },
    "monterrey": {
        "country": "Mexico",
        "zones": {
            "texas_live_zone": {  # Guadalupe Match District (Estadio BBVA)
                "node_id": "texas_live",
                "queries": [
                    ("sports bar Guadalupe Monterrey", ["bar"]),
                    ("bar restaurante Guadalupe Monterrey", ["bar", "restaurant"]),
                    ("cantina Guadalupe Monterrey", ["bar"]),
                ],
                "search_radius_m": 2000,
                "default_type": "sports_bar",
            },
            "arlington_hotels_zone": {  # Guadalupe Hotel Cluster
                "node_id": "arlington_hotels",
                "queries": [
                    ("hotel boutique Guadalupe Monterrey", ["lodging"]),
                    ("hotel independiente Guadalupe Nuevo León", ["lodging"]),
                ],
                "search_radius_m": 2000,
                "default_type": "hotel",
            },
            "las_colinas_zone": {  # San Pedro Hotel District
                "node_id": "las_colinas",
                "queries": [
                    ("hotel boutique San Pedro Garza García", ["lodging"]),
                    ("hotel independiente San Pedro Monterrey", ["lodging"]),
                    ("bar restaurante San Pedro Garza García", ["bar", "restaurant"]),
                ],
                "search_radius_m": 2200,
                "default_type": "hotel",
            },
            "downtown_zone": {  # Centro Monterrey
                "node_id": "downtown_dallas",
                "queries": [
                    ("hotel boutique Centro Monterrey", ["lodging"]),
                    ("hotel independiente Centro Monterrey", ["lodging"]),
                    ("bar restaurante Centro Monterrey", ["bar", "restaurant"]),
                    ("rooftop bar Centro Monterrey", ["bar"]),
                ],
                "search_radius_m": 2200,
                "default_type": "sports_bar",
            },
            "uptown_zone": {  # San Pedro Nightlife
                "node_id": "uptown",
                "queries": [
                    ("cocktail bar San Pedro Garza García", ["bar"]),
                    ("wine bar San Pedro Monterrey", ["bar"]),
                    ("bar San Pedro Monterrey nightlife", ["bar"]),
                    ("gastropub San Pedro Monterrey", ["bar", "restaurant"]),
                ],
                "search_radius_m": 1800,
                "default_type": "cocktail_bar",
            },
            "deep_ellum_zone": {  # Barrio Antiguo
                "node_id": "deep_ellum",
                "queries": [
                    ("bar Barrio Antiguo Monterrey", ["bar"]),
                    ("live music Barrio Antiguo Monterrey", ["bar"]),
                    ("cantina Barrio Antiguo Monterrey", ["bar", "restaurant"]),
                    ("pub Barrio Antiguo Monterrey", ["bar"]),
                ],
                "search_radius_m": 1500,
                "default_type": "sports_bar",
            },
        },
    },
    "atlanta": {
        "country": "USA",
        "zones": {
            "texas_live_zone": {  # Centennial Olympic Park District
                "node_id": "texas_live",
                "queries": [
                    ("sports bar Centennial Olympic Park Atlanta", ["bar"]),
                    ("bar restaurant Centennial Park Atlanta", ["bar", "restaurant"]),
                    ("rooftop bar Atlanta downtown", ["bar"]),
                ],
                "search_radius_m": 1800,
                "default_type": "sports_bar",
            },
            "arlington_hotels_zone": {  # Downtown Stadium Hotels
                "node_id": "arlington_hotels",
                "queries": [
                    ("boutique hotel Downtown Atlanta near Mercedes-Benz Stadium", ["lodging"]),
                    ("inn Downtown Atlanta", ["lodging"]),
                ],
                "search_radius_m": 2000,
                "default_type": "hotel",
            },
            "las_colinas_zone": {  # Buckhead Hotel District
                "node_id": "las_colinas",
                "queries": [
                    ("boutique hotel Buckhead Atlanta", ["lodging"]),
                    ("inn Buckhead Atlanta", ["lodging"]),
                    ("bar restaurant Buckhead Atlanta", ["bar", "restaurant"]),
                ],
                "search_radius_m": 2200,
                "default_type": "hotel",
            },
            "downtown_zone": {  # Downtown Atlanta
                "node_id": "downtown_dallas",
                "queries": [
                    ("boutique hotel Downtown Atlanta", ["lodging"]),
                    ("independent hotel Downtown Atlanta", ["lodging"]),
                    ("bar restaurant Downtown Atlanta", ["bar", "restaurant"]),
                ],
                "search_radius_m": 2200,
                "default_type": "sports_bar",
            },
            "uptown_zone": {  # Old Fourth Ward / Krog Street
                "node_id": "uptown",
                "queries": [
                    ("cocktail bar Old Fourth Ward Atlanta", ["bar"]),
                    ("wine bar Old Fourth Ward Atlanta", ["bar"]),
                    ("gastropub Old Fourth Ward Atlanta", ["bar", "restaurant"]),
                    ("Krog Street Market bar Atlanta", ["bar"]),
                ],
                "search_radius_m": 1800,
                "default_type": "cocktail_bar",
            },
            "deep_ellum_zone": {  # Inman Park / Little Five Points
                "node_id": "deep_ellum",
                "queries": [
                    ("bar Little Five Points Atlanta", ["bar"]),
                    ("live music venue Inman Park Atlanta", ["bar"]),
                    ("craft beer Inman Park Atlanta", ["bar"]),
                    ("pub Little Five Points Atlanta", ["bar", "restaurant"]),
                ],
                "search_radius_m": 1500,
                "default_type": "sports_bar",
            },
        },
    },
    "philadelphia": {
        "country": "USA",
        "zones": {
            "texas_live_zone": {  # Stadium Entertainment Plaza
                "node_id": "texas_live",
                "queries": [
                    ("sports bar near Lincoln Financial Field Philadelphia", ["bar"]),
                    ("bar restaurant Stadium District Philadelphia", ["bar", "restaurant"]),
                    ("pub South Philadelphia stadium", ["bar"]),
                ],
                "search_radius_m": 2000,
                "default_type": "sports_bar",
            },
            "arlington_hotels_zone": {  # Stadium Hotel Cluster
                "node_id": "arlington_hotels",
                "queries": [
                    ("hotel near Lincoln Financial Field Philadelphia", ["lodging"]),
                    ("inn South Philadelphia stadium", ["lodging"]),
                ],
                "search_radius_m": 2200,
                "default_type": "hotel",
            },
            "las_colinas_zone": {  # Center City Hotel District
                "node_id": "las_colinas",
                "queries": [
                    ("boutique hotel Center City Philadelphia", ["lodging"]),
                    ("independent hotel Rittenhouse Philadelphia", ["lodging"]),
                    ("bar restaurant Rittenhouse Philadelphia", ["bar", "restaurant"]),
                ],
                "search_radius_m": 2000,
                "default_type": "hotel",
            },
            "downtown_zone": {  # Center City Philadelphia
                "node_id": "downtown_dallas",
                "queries": [
                    ("boutique hotel Center City Philadelphia", ["lodging"]),
                    ("rooftop bar Center City Philadelphia", ["bar"]),
                    ("bar restaurant Center City Philadelphia", ["bar", "restaurant"]),
                ],
                "search_radius_m": 2200,
                "default_type": "sports_bar",
            },
            "uptown_zone": {  # Old City
                "node_id": "uptown",
                "queries": [
                    ("cocktail bar Old City Philadelphia", ["bar"]),
                    ("wine bar Old City Philadelphia", ["bar"]),
                    ("gastropub Old City Philadelphia", ["bar", "restaurant"]),
                    ("neighborhood bar Old City Philadelphia", ["bar"]),
                ],
                "search_radius_m": 1500,
                "default_type": "cocktail_bar",
            },
            "deep_ellum_zone": {  # Northern Liberties / Fishtown
                "node_id": "deep_ellum",
                "queries": [
                    ("bar Fishtown Philadelphia", ["bar"]),
                    ("live music venue Northern Liberties Philadelphia", ["bar"]),
                    ("craft beer Fishtown Philadelphia", ["bar"]),
                    ("pub Northern Liberties Philadelphia", ["bar", "restaurant"]),
                ],
                "search_radius_m": 1800,
                "default_type": "sports_bar",
            },
        },
    },
    "seattle": {
        "country": "USA",
        "zones": {
            "texas_live_zone": {  # Pioneer Square Entertainment
                "node_id": "texas_live",
                "queries": [
                    ("sports bar Pioneer Square Seattle", ["bar"]),
                    ("bar restaurant near Lumen Field Seattle", ["bar", "restaurant"]),
                    ("pub Pioneer Square Seattle", ["bar"]),
                ],
                "search_radius_m": 1500,
                "default_type": "sports_bar",
            },
            "arlington_hotels_zone": {  # Stadium Hotel Cluster
                "node_id": "arlington_hotels",
                "queries": [
                    ("hotel near Lumen Field Seattle", ["lodging"]),
                    ("inn Pioneer Square Seattle", ["lodging"]),
                ],
                "search_radius_m": 1800,
                "default_type": "hotel",
            },
            "las_colinas_zone": {  # Belltown / Queen Anne Hotels
                "node_id": "las_colinas",
                "queries": [
                    ("boutique hotel Belltown Seattle", ["lodging"]),
                    ("boutique hotel Queen Anne Seattle", ["lodging"]),
                    ("bar restaurant Belltown Seattle", ["bar", "restaurant"]),
                ],
                "search_radius_m": 1800,
                "default_type": "hotel",
            },
            "downtown_zone": {  # Downtown Seattle
                "node_id": "downtown_dallas",
                "queries": [
                    ("boutique hotel Downtown Seattle", ["lodging"]),
                    ("independent hotel Downtown Seattle", ["lodging"]),
                    ("rooftop bar Downtown Seattle", ["bar"]),
                ],
                "search_radius_m": 2200,
                "default_type": "sports_bar",
            },
            "uptown_zone": {  # Belltown
                "node_id": "uptown",
                "queries": [
                    ("cocktail bar Belltown Seattle", ["bar"]),
                    ("wine bar Belltown Seattle", ["bar"]),
                    ("gastropub Belltown Seattle", ["bar", "restaurant"]),
                ],
                "search_radius_m": 1500,
                "default_type": "cocktail_bar",
            },
            "deep_ellum_zone": {  # Capitol Hill
                "node_id": "deep_ellum",
                "queries": [
                    ("bar Capitol Hill Seattle", ["bar"]),
                    ("live music venue Capitol Hill Seattle", ["bar"]),
                    ("craft beer Capitol Hill Seattle", ["bar"]),
                    ("pub Capitol Hill Seattle", ["bar", "restaurant"]),
                ],
                "search_radius_m": 1500,
                "default_type": "sports_bar",
            },
        },
    },
    "vancouver": {
        "country": "Canada",
        "zones": {
            "texas_live_zone": {  # Stadium Entertainment District (around BC Place)
                "node_id": "texas_live",
                "queries": [
                    ("sports bar near BC Place Vancouver", ["bar"]),
                    ("bar restaurant near Rogers Arena Vancouver", ["bar", "restaurant"]),
                    ("pub Yaletown Vancouver", ["bar"]),
                ],
                "search_radius_m": 1500,
                "default_type": "sports_bar",
            },
            "arlington_hotels_zone": {  # Stadium Hotel Cluster
                "node_id": "arlington_hotels",
                "queries": [
                    ("hotel near BC Place Vancouver", ["lodging"]),
                    ("inn Yaletown Vancouver", ["lodging"]),
                ],
                "search_radius_m": 1800,
                "default_type": "hotel",
            },
            "las_colinas_zone": {  # West End / Coal Harbour
                "node_id": "las_colinas",
                "queries": [
                    ("boutique hotel Coal Harbour Vancouver", ["lodging"]),
                    ("boutique hotel West End Vancouver", ["lodging"]),
                    ("bar restaurant Coal Harbour Vancouver", ["bar", "restaurant"]),
                ],
                "search_radius_m": 1800,
                "default_type": "hotel",
            },
            "downtown_zone": {  # Downtown Vancouver
                "node_id": "downtown_dallas",
                "queries": [
                    ("boutique hotel Downtown Vancouver", ["lodging"]),
                    ("independent hotel Downtown Vancouver", ["lodging"]),
                    ("rooftop bar Downtown Vancouver", ["bar"]),
                ],
                "search_radius_m": 2200,
                "default_type": "sports_bar",
            },
            "uptown_zone": {  # Yaletown
                "node_id": "uptown",
                "queries": [
                    ("cocktail bar Yaletown Vancouver", ["bar"]),
                    ("wine bar Yaletown Vancouver", ["bar"]),
                    ("gastropub Yaletown Vancouver", ["bar", "restaurant"]),
                ],
                "search_radius_m": 1500,
                "default_type": "cocktail_bar",
            },
            "deep_ellum_zone": {  # Gastown / Chinatown
                "node_id": "deep_ellum",
                "queries": [
                    ("bar Gastown Vancouver", ["bar"]),
                    ("live music venue Gastown Vancouver", ["bar"]),
                    ("craft beer Gastown Vancouver", ["bar"]),
                    ("pub Gastown Vancouver", ["bar", "restaurant"]),
                ],
                "search_radius_m": 1500,
                "default_type": "sports_bar",
            },
        },
    },
    "guadalajara": {
        "country": "Mexico",
        "zones": {
            "texas_live_zone": {  # Estadio Entertainment Plaza
                "node_id": "texas_live",
                "queries": [
                    ("sports bar Estadio Akron Guadalajara", ["bar"]),
                    ("bar restaurante Zapopan Guadalajara", ["bar", "restaurant"]),
                    ("cantina Zapopan Jalisco", ["bar"]),
                ],
                "search_radius_m": 2000,
                "default_type": "sports_bar",
            },
            "arlington_hotels_zone": {  # Stadium Hotel Cluster
                "node_id": "arlington_hotels",
                "queries": [
                    ("hotel boutique Estadio Akron Guadalajara", ["lodging"]),
                    ("hotel independiente Zapopan Guadalajara", ["lodging"]),
                ],
                "search_radius_m": 2200,
                "default_type": "hotel",
            },
            "las_colinas_zone": {  # Zapopan Hotel District
                "node_id": "las_colinas",
                "queries": [
                    ("hotel boutique Zapopan Guadalajara", ["lodging"]),
                    ("hotel independiente Providencia Guadalajara", ["lodging"]),
                    ("bar restaurante Providencia Guadalajara", ["bar", "restaurant"]),
                ],
                "search_radius_m": 2000,
                "default_type": "hotel",
            },
            "downtown_zone": {  # Centro Histórico
                "node_id": "downtown_dallas",
                "queries": [
                    ("hotel boutique Centro Histórico Guadalajara", ["lodging"]),
                    ("hotel independiente Centro Guadalajara", ["lodging"]),
                    ("bar restaurante Centro Guadalajara", ["bar", "restaurant"]),
                    ("cantina Centro Guadalajara", ["bar"]),
                ],
                "search_radius_m": 2200,
                "default_type": "sports_bar",
            },
            "uptown_zone": {  # Chapultepec Nightlife
                "node_id": "uptown",
                "queries": [
                    ("cocktail bar Chapultepec Guadalajara", ["bar"]),
                    ("wine bar Chapultepec Guadalajara", ["bar"]),
                    ("bar Avenida Chapultepec Guadalajara", ["bar"]),
                    ("gastropub Chapultepec Guadalajara", ["bar", "restaurant"]),
                ],
                "search_radius_m": 1800,
                "default_type": "cocktail_bar",
            },
            "deep_ellum_zone": {  # Tlaquepaque / Andador
                "node_id": "deep_ellum",
                "queries": [
                    ("bar Tlaquepaque Guadalajara", ["bar"]),
                    ("live music Tlaquepaque Guadalajara", ["bar"]),
                    ("cantina Tlaquepaque Jalisco", ["bar", "restaurant"]),
                ],
                "search_radius_m": 1800,
                "default_type": "sports_bar",
            },
        },
    },
}


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------
def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def load_hunter_cache() -> dict[str, Any]:
    if HUNTER_CACHE_PATH.exists():
        return load_json(HUNTER_CACHE_PATH)
    return {"domain_search": {}, "verify": {}}


def save_hunter_cache(cache: dict[str, Any]) -> None:
    dump_json(HUNTER_CACHE_PATH, cache)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")[:60]


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def is_chain(name: str, blocklist: dict[str, list[str]]) -> str | None:
    n = name.lower()
    for category, brands in blocklist.items():
        for brand in brands:
            if brand in n:
                return f"{category}:{brand}"
    return None


def map_price_level(value: str | None) -> int:
    mapping = {
        "PRICE_LEVEL_FREE": 0,
        "PRICE_LEVEL_INEXPENSIVE": 1,
        "PRICE_LEVEL_MODERATE": 2,
        "PRICE_LEVEL_EXPENSIVE": 3,
        "PRICE_LEVEL_VERY_EXPENSIVE": 4,
    }
    return mapping.get(value or "", 2)


def hours_summary(payload: dict[str, Any] | None, fallback: str = "11:00-02:00") -> str:
    if not payload:
        return fallback
    weekday = payload.get("weekdayDescriptions") or []
    if weekday:
        return weekday[0]
    return fallback


def infer_business_type(google_types: list[str], default_type: str) -> str:
    types = set(google_types or [])
    if "lodging" in types or "hotel" in types:
        if "bar" in types or "restaurant" in types:
            return "hotel_bar"
        return "hotel"
    if "night_club" in types or "bar" in types:
        if "restaurant" in types or "meal_takeaway" in types or "food" in types:
            return "sports_bar"
        if "cocktail_lounge" in types:
            return "cocktail_bar"
        return default_type or "sports_bar"
    if "restaurant" in types:
        return "sports_bar"
    return default_type or "sports_bar"


def estimate_capacity(business_type: str) -> int:
    return {
        "sports_bar": 700,
        "cocktail_bar": 350,
        "hotel": 600,
        "hotel_bar": 450,
        "restaurant": 400,
    }.get(business_type, 500)


def is_valid_email(email: str, website_domain: str = "") -> bool:
    e = email.lower().strip()
    if "{" in e or "}" in e or "\\" in e or "$" in e:
        return False
    if any(e.startswith(p) for p in EMAIL_SKIP_PREFIXES):
        return False
    if any(d in e for d in EMAIL_SKIP_DOMAINS):
        return False
    if e.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")):
        return False
    if website_domain:
        email_domain = e.split("@", 1)[1] if "@" in e else ""
        if email_domain and website_domain not in email_domain and email_domain not in website_domain:
            return False
    return True


def extract_root_domain(url: str) -> str:
    if not url:
        return ""
    m = re.match(r"https?://([^/]+)", url)
    if not m:
        return ""
    host = m.group(1).lower()
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


# ---------------------------------------------------------------------------
# Google Places search
# ---------------------------------------------------------------------------
def search_places_text(
    client: httpx.Client,
    query: str,
    center_lat: float,
    center_lng: float,
    radius_m: float,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    if not GOOGLE_API_KEY:
        raise SystemExit("GOOGLE_MAPS_API_KEY missing in .env")
    headers = {
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
        "Content-Type": "application/json",
    }
    body = {
        "textQuery": query,
        "maxResultCount": max_results,
        "locationBias": {
            "circle": {
                "center": {"latitude": center_lat, "longitude": center_lng},
                "radius": radius_m,
            }
        },
    }
    resp = client.post(PLACES_TEXT_URL, headers=headers, json=body, timeout=20)
    if not resp.is_success:
        print(f"  ! Places API error {resp.status_code}: {resp.text[:200]}")
        return []
    return resp.json().get("places", [])


def lookup_place_by_name(
    client: httpx.Client,
    name: str,
    lat: float,
    lng: float,
    radius_m: float = 3500.0,
) -> dict[str, Any] | None:
    """Look up a single specific place by name + location bias."""
    results = search_places_text(client, name, lat, lng, radius_m, max_results=1)
    return results[0] if results else None


# ---------------------------------------------------------------------------
# Email scraping — W1 (own website, expanded)
# ---------------------------------------------------------------------------
def _decode_entities(text: str) -> str:
    decoded = html.unescape(text)
    # custom entities sometimes used
    decoded = decoded.replace("&commat;", "@")
    decoded = decoded.replace("&#64;", "@")
    return decoded


def _deobfuscate(text: str) -> str:
    """Replace common email obfuscation tricks with @ and . — supports email [at] domain [dot] com."""
    t = text
    # [at], (at), {at} → @
    t = re.sub(r"\s*[\[\(\{]\s*at\s*[\]\)\}]\s*", "@", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+at\s+(?=[a-zA-Z0-9])", "@", t)
    # [dot], (dot) → .
    t = re.sub(r"\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*", ".", t, flags=re.IGNORECASE)
    return t


def _extract_emails_from_html(text: str, website_domain: str) -> list[str]:
    """Extract all valid emails from raw HTML. Decodes entities + obfuscation patterns."""
    found: list[str] = []
    decoded = _decode_entities(text)

    # 1. mailto: links (most reliable)
    for m in re.findall(r'mailto:([^"\'?\s>&]+)', decoded, re.IGNORECASE):
        if is_valid_email(m, website_domain):
            found.append(m.lower().strip())

    # 2. plain regex on decoded HTML
    for m in EMAIL_REGEX.findall(decoded):
        if is_valid_email(m, website_domain):
            found.append(m.lower().strip())

    # 3. JSON-LD blocks
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>',
                            decoded, re.IGNORECASE | re.DOTALL):
        for m in EMAIL_REGEX.findall(block):
            if is_valid_email(m, website_domain):
                found.append(m.lower().strip())

    # 4. de-obfuscated (slow path — only on failure to avoid false positives)
    if not found:
        deobf = _deobfuscate(decoded)
        for m in EMAIL_REGEX.findall(deobf):
            if is_valid_email(m, website_domain):
                found.append(m.lower().strip())

    # dedupe preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for e in found:
        if e not in seen:
            seen.add(e)
            deduped.append(e)
    return deduped


def _pick_best_email(emails: list[str]) -> str:
    """Pick highest-priority email from candidates. Owner/manager > events > sales > info > rest."""
    priority = ("owner@", "manager@", "events@", "booking@", "reservations@",
                "sales@", "marketing@", "general@", "hello@", "info@", "contact@")
    for prefix in priority:
        for e in emails:
            if e.startswith(prefix):
                return e
    return emails[0] if emails else ""


def scrape_email_w1(client: httpx.Client, website: str, timeout: float = 4.0) -> tuple[str, list[str]]:
    """W1: scrape own site across many subpages. Returns (best_email, all_emails_found)."""
    if not website:
        return "", []
    try:
        domain = extract_root_domain(website)
        base = website.rstrip("/")
    except Exception:
        return "", []
    all_emails: list[str] = []
    facebook_links: list[str] = []  # collected for W2

    for path in SCRAPE_PATHS:
        url = base + path if path else base
        try:
            resp = client.get(
                url,
                timeout=timeout,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            )
            if not resp.is_success:
                continue
            text = resp.text
            emails = _extract_emails_from_html(text, domain)
            all_emails.extend(e for e in emails if e not in all_emails)
            for fb in re.findall(r'facebook\.com/([a-zA-Z0-9.\-_]+)', text):
                if fb.lower() not in {"sharer", "share", "tr", "plugins", "dialog", "events"}:
                    if fb not in facebook_links:
                        facebook_links.append(fb)
            if len(all_emails) >= 5:
                break
        except Exception:
            continue
        time.sleep(0.2)

    return _pick_best_email(all_emails), facebook_links


# ---------------------------------------------------------------------------
# Email scraping — W2 (Facebook About fallback)
# ---------------------------------------------------------------------------
def scrape_email_facebook(client: httpx.Client, fb_handle: str, website_domain: str = "", timeout: float = 5.0) -> str:
    """W2: scrape Facebook page About/Contact section for email."""
    candidate_urls = [
        f"https://www.facebook.com/{fb_handle}/about_contact_and_basic_info",
        f"https://m.facebook.com/{fb_handle}/about/",
    ]
    found: list[str] = []
    for url in candidate_urls:
        try:
            resp = client.get(
                url,
                timeout=timeout,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept-Language": "en-US,en;q=0.9",
                },
                follow_redirects=True,
            )
            if not resp.is_success:
                continue
            text = resp.text
            decoded = _decode_entities(text)
            for m in EMAIL_REGEX.findall(decoded):
                e = m.lower().strip()
                if is_valid_email(e, ""):
                    if e not in found:
                        found.append(e)
            if found:
                break
        except Exception:
            continue
        time.sleep(0.3)

    if website_domain:
        matching = [e for e in found if "@" in e and website_domain in e.split("@", 1)[1]]
        if matching:
            return _pick_best_email(matching)
    return _pick_best_email(found) if found else ""


# ---------------------------------------------------------------------------
# Hunter.io API
# ---------------------------------------------------------------------------
def hunter_domain_search(client: httpx.Client, domain: str, cache: dict[str, Any]) -> dict[str, Any]:
    """Hunter Domain Search (1 credit per call). Returns email candidates for a domain."""
    if not HUNTER_API_KEY:
        raise SystemExit("HUNTER_API_KEY missing in .env")
    if domain in cache["domain_search"]:
        return cache["domain_search"][domain]
    try:
        resp = client.get(
            HUNTER_DOMAIN_SEARCH_URL,
            params={"domain": domain, "api_key": HUNTER_API_KEY, "limit": 10},
            timeout=15,
        )
        if resp.status_code == 429:
            print(f"    ! Hunter rate limit, sleeping 30s...")
            time.sleep(30)
            resp = client.get(
                HUNTER_DOMAIN_SEARCH_URL,
                params={"domain": domain, "api_key": HUNTER_API_KEY, "limit": 10},
                timeout=15,
            )
        data = resp.json() if resp.is_success else {"errors": [{"id": resp.status_code, "details": resp.text[:200]}]}
    except Exception as exc:
        data = {"errors": [{"id": "exception", "details": str(exc)}]}
    cache["domain_search"][domain] = data
    save_hunter_cache(cache)
    return data


def hunter_pick_email(domain_search_data: dict[str, Any]) -> tuple[str, int, str]:
    """From Hunter Domain Search response, pick best email.

    Returns (email, confidence, verification_status). The status comes from
    Hunter's bundled verification (saves a separate verify credit).
    """
    payload = domain_search_data.get("data") or {}
    emails = payload.get("emails") or []
    if not emails:
        return "", 0, ""

    role_priority = {
        "owner": 100, "ceo": 95, "founder": 95,
        "manager": 90, "director": 85, "events": 80,
        "marketing": 70, "sales": 70, "booking": 75,
        "reservations": 75, "contact": 50, "info": 50, "hello": 50,
    }

    def score(item: dict[str, Any]) -> int:
        email = (item.get("value") or "").lower()
        confidence = item.get("confidence") or 0
        verification = item.get("verification") or {}
        v_status = (verification.get("status") or "").lower()
        # personal emails (with first/last name) score highest
        type_bonus = 30 if (item.get("type") == "personal") else 0
        # already-valid emails get a strong bonus (saves verify credits later)
        verified_bonus = 50 if v_status == "valid" else (-30 if v_status == "invalid" else 0)
        local = email.split("@", 1)[0] if "@" in email else ""
        role_bonus = 0
        for keyword, weight in role_priority.items():
            if keyword in local:
                role_bonus = max(role_bonus, weight)
        return confidence + role_bonus + type_bonus + verified_bonus

    best = max(emails, key=score)
    email = (best.get("value") or "").lower().strip()
    confidence = best.get("confidence") or 0
    verification = best.get("verification") or {}
    status = (verification.get("status") or "").lower()
    return email, confidence, status


def hunter_verify(client: httpx.Client, email: str, cache: dict[str, Any]) -> dict[str, Any]:
    """Hunter Email Verifier (1 verification credit per call)."""
    if not HUNTER_API_KEY:
        raise SystemExit("HUNTER_API_KEY missing in .env")
    if email in cache["verify"]:
        return cache["verify"][email]
    try:
        resp = client.get(
            HUNTER_VERIFIER_URL,
            params={"email": email, "api_key": HUNTER_API_KEY},
            timeout=15,
        )
        if resp.status_code == 429:
            print(f"    ! Hunter rate limit, sleeping 30s...")
            time.sleep(30)
            resp = client.get(
                HUNTER_VERIFIER_URL,
                params={"email": email, "api_key": HUNTER_API_KEY},
                timeout=15,
            )
        data = resp.json() if resp.is_success else {"errors": [{"id": resp.status_code, "details": resp.text[:200]}]}
    except Exception as exc:
        data = {"errors": [{"id": "exception", "details": str(exc)}]}
    cache["verify"][email] = data
    save_hunter_cache(cache)
    return data


# ---------------------------------------------------------------------------
# Pipeline: enrich seeded businesses (fill address/phone/website)
# ---------------------------------------------------------------------------
def enrich_seeded(city_id: str) -> None:
    cfg = CITY_CONFIGS.get(city_id)
    if not cfg:
        raise SystemExit(f"No config for city '{city_id}'")
    biz_path = CITIES_DIR / city_id / "businesses.json"
    payload = load_json(biz_path)
    seeded = [b for b in payload["businesses"] if b.get("source") == "seeded_real"]
    print(f"Enriching {len(seeded)} seeded businesses with Google Places data...")

    updated = 0
    with httpx.Client() as client:
        for i, b in enumerate(seeded, 1):
            place = lookup_place_by_name(
                client, b["name"], b["lat"], b["lng"], radius_m=3500.0,
            )
            if not place:
                continue
            address = place.get("formattedAddress", "").strip()
            phone = (place.get("internationalPhoneNumber")
                     or place.get("nationalPhoneNumber") or "").strip()
            website = (place.get("websiteUri") or "").strip()
            review_count = place.get("userRatingCount", 0) or 0
            google_types = place.get("types", []) or []

            changed = False
            if address and not b.get("address"):
                b["address"] = address
                changed = True
            if phone and not b.get("phone"):
                b["phone"] = phone
                changed = True
            if website and not b.get("website"):
                b["website"] = website
                changed = True
            if review_count and not b.get("review_count"):
                b["review_count"] = review_count
                changed = True
            if google_types and not b.get("google_types"):
                b["google_types"] = google_types
                changed = True
            # ensure email field exists
            if "email" not in b:
                b["email"] = ""
                changed = True
            if changed:
                updated += 1
            if i % 5 == 0:
                print(f"  progress: {i}/{len(seeded)} (updated: {updated})")
            time.sleep(0.4)

    dump_json(biz_path, payload)
    print(f"\nDone: {updated}/{len(seeded)} seeded businesses updated with Places data.")


# ---------------------------------------------------------------------------
# Pipeline: full enrichment (search Places + scrape emails)
# ---------------------------------------------------------------------------
def enrich_city(city_id: str, scrape_emails: bool = True) -> None:
    cfg = CITY_CONFIGS.get(city_id)
    if not cfg:
        raise SystemExit(f"No config for city '{city_id}'")

    city_dir = CITIES_DIR / city_id
    base = load_json(city_dir / "base.json")
    biz_path = city_dir / "businesses.json"
    biz_payload = load_json(biz_path)
    existing = biz_payload["businesses"]

    zones_by_id = {z["id"]: z for z in base["zones"]}
    blocklist = load_json(BLOCKLIST_PATH)

    existing_names = {b["name"].lower().strip() for b in existing}
    existing_coords = [(b["lat"], b["lng"]) for b in existing]

    new_businesses: list[dict[str, Any]] = []
    seen_place_ids: set[str] = set()
    seen_addresses: set[str] = set()

    stats = {"queried": 0, "raw_results": 0, "chain_filtered": 0, "duplicates": 0, "added": 0}

    with httpx.Client() as client:
        for zone_id, zone_cfg in cfg["zones"].items():
            zone = zones_by_id.get(zone_id)
            if not zone:
                print(f"  ! Zone {zone_id} not in base.json, skipping")
                continue
            center_lng, center_lat = zone["center"]
            radius = zone_cfg.get("search_radius_m", max(zone["radius_m"] * 2, 1500))

            print(f"\nZone: {zone_id} ({zone['name']})")
            for query, _types in zone_cfg["queries"]:
                stats["queried"] += 1
                print(f"  query: {query!r}")
                results = search_places_text(
                    client, query, center_lat, center_lng, radius, max_results=20
                )
                stats["raw_results"] += len(results)
                print(f"    -> {len(results)} results")

                for place in results:
                    place_id = place.get("id", "")
                    if place_id and place_id in seen_place_ids:
                        stats["duplicates"] += 1
                        continue
                    seen_place_ids.add(place_id)

                    name = (place.get("displayName") or {}).get("text", "").strip()
                    if not name:
                        continue
                    address = place.get("formattedAddress", "").strip()

                    if is_chain(name, blocklist):
                        stats["chain_filtered"] += 1
                        continue

                    if name.lower().strip() in existing_names:
                        stats["duplicates"] += 1
                        continue
                    if address and address in seen_addresses:
                        stats["duplicates"] += 1
                        continue
                    seen_addresses.add(address)

                    loc = place.get("location") or {}
                    lat = loc.get("latitude")
                    lng = loc.get("longitude")
                    if lat is None or lng is None:
                        continue

                    too_close = False
                    for elat, elng in existing_coords:
                        if haversine_m(lat, lng, elat, elng) < 50:
                            too_close = True
                            break
                    if too_close:
                        stats["duplicates"] += 1
                        continue

                    google_types = place.get("types", []) or []
                    btype = infer_business_type(google_types, zone_cfg.get("default_type", "sports_bar"))

                    phone = place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber") or ""
                    website = place.get("websiteUri", "") or ""

                    biz = {
                        "id": f"biz_{slugify(name)}",
                        "name": name,
                        "type": btype,
                        "zone_id": zone_id,
                        "node_id": zone_cfg["node_id"],
                        "lat": round(lat, 6),
                        "lng": round(lng, 6),
                        "rating": place.get("rating", 0) or 0,
                        "price_level": map_price_level(place.get("priceLevel")),
                        "capacity_estimate": estimate_capacity(btype),
                        "hours": hours_summary(place.get("regularOpeningHours")),
                        "source": "google_places_enriched",
                        "signature_item": "",
                        "phone": phone,
                        "website": website,
                        "address": address,
                        "review_count": place.get("userRatingCount", 0) or 0,
                        "google_types": google_types,
                        "email": "",
                        "email_status": "unverified",
                        "email_source": "",
                        "email_confidence": 0,
                    }
                    new_businesses.append(biz)
                    existing_coords.append((lat, lng))
                    existing_names.add(name.lower().strip())
                    stats["added"] += 1

                time.sleep(0.5)

        if scrape_emails and new_businesses:
            print(f"\nScraping emails for {len(new_businesses)} new businesses (W1)...")
            scraped = 0
            for i, biz in enumerate(new_businesses, 1):
                if not biz["website"]:
                    continue
                email, fb_links = scrape_email_w1(client, biz["website"])
                if email:
                    biz["email"] = email
                    biz["email_source"] = "scraped_website"
                    scraped += 1
                if fb_links:
                    biz["facebook_handles"] = fb_links[:3]
                if i % 10 == 0:
                    print(f"  progress: {i}/{len(new_businesses)} (emails: {scraped})")
                time.sleep(0.5)
            print(f"  done W1: {scraped}/{len(new_businesses)} emails scraped")

    merged = list(existing) + new_businesses
    biz_payload["businesses"] = merged
    dump_json(biz_path, biz_payload)

    print(f"\n=== {city_id} enrichment summary ===")
    print(f"  Existing businesses:    {len(existing)}")
    print(f"  Queries run:            {stats['queried']}")
    print(f"  Raw Google results:     {stats['raw_results']}")
    print(f"  Chains filtered:        {stats['chain_filtered']}")
    print(f"  Duplicates filtered:    {stats['duplicates']}")
    print(f"  New businesses added:   {stats['added']}")
    print(f"  Total now:              {len(merged)}")
    print(f"  Saved: {biz_path}")


# ---------------------------------------------------------------------------
# Pipeline: re-scrape emails (W1 + W2)
# ---------------------------------------------------------------------------
def _safe_dump(path: Path, payload: Any, max_retries: int = 3) -> bool:
    """Dump JSON with retry on PermissionError (OneDrive sync, file locks)."""
    for attempt in range(max_retries):
        try:
            dump_json(path, payload)
            return True
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            print(f"    ! PermissionError saving {path.name} after {max_retries} retries, skipping save")
            return False
        except Exception as exc:
            print(f"    ! Save failed: {exc}")
            return False
    return False


def rescrape_emails(city_id: str) -> None:
    """Re-run W1 (own website, expanded) + W2 (Facebook fallback) for all businesses.

    Saves incrementally every 20 businesses so progress survives interruptions.
    """
    biz_path = CITIES_DIR / city_id / "businesses.json"
    payload = load_json(biz_path)
    targets = [b for b in payload["businesses"] if b.get("website")]
    print(f"Re-scraping emails for {len(targets)} businesses with websites...")
    print(f"  W1 (own website)...")

    w1_found = 0
    w2_found = 0
    cleared = 0
    fb_candidates: list[tuple[dict[str, Any], list[str]]] = []

    with httpx.Client() as client:
        # W1 pass
        for i, b in enumerate(targets, 1):
            try:
                old = b.get("email", "")
                website = b.get("website", "")
                new_email, fb_links = scrape_email_w1(client, website, timeout=4.0)
                domain = extract_root_domain(website)
                old_invalid = old and not is_valid_email(old, domain)

                if new_email:
                    b["email"] = new_email
                    b["email_source"] = "scraped_website"
                    b["email_status"] = "unverified"
                    w1_found += 1
                elif old_invalid:
                    b["email"] = ""
                    b["email_source"] = ""
                    b["email_status"] = "unverified"
                    cleared += 1
                else:
                    # ensure new fields exist even if no change
                    b.setdefault("email_source", "" if not old else "scraped_website")
                    b.setdefault("email_status", "unverified")

                if not b.get("email") and fb_links:
                    fb_candidates.append((b, fb_links))
                    if "facebook_handles" not in b:
                        b["facebook_handles"] = fb_links[:3]
            except Exception as exc:
                print(f"    ! W1 error on '{b.get('name', '?')}': {exc}")

            if i % 20 == 0:
                print(f"    progress: {i}/{len(targets)} (W1 found: {w1_found}, cleared: {cleared}) — saving...")
                _safe_dump(biz_path, payload)
            time.sleep(0.3)
        print(f"  W1 done: {w1_found} emails found, {cleared} bad ones cleared")
        _safe_dump(biz_path, payload)

        # W2 pass — Facebook fallback for businesses without email
        if fb_candidates:
            print(f"  W2 (Facebook About) for {len(fb_candidates)} businesses without email...")
            for i, (b, fb_links) in enumerate(fb_candidates, 1):
                try:
                    if b.get("email"):
                        continue
                    domain = extract_root_domain(b.get("website", ""))
                    for handle in fb_links[:2]:
                        email = scrape_email_facebook(client, handle, domain, timeout=5.0)
                        if email:
                            b["email"] = email
                            b["email_source"] = "scraped_facebook"
                            b["email_status"] = "unverified"
                            w2_found += 1
                            break
                except Exception as exc:
                    print(f"    ! W2 error on '{b.get('name', '?')}': {exc}")

                if i % 10 == 0:
                    print(f"    progress: {i}/{len(fb_candidates)} (W2 found: {w2_found}) — saving...")
                    _safe_dump(biz_path, payload)
                time.sleep(0.4)
            print(f"  W2 done: {w2_found} additional emails found")

    _safe_dump(biz_path, payload)
    total_emails = sum(1 for b in payload["businesses"] if b.get("email"))
    print(f"\nTotal emails after W1+W2: {total_emails}")


# ---------------------------------------------------------------------------
# Pipeline: Hunter fill + verify
# ---------------------------------------------------------------------------
def hunter_fill(city_id: str) -> None:
    """For businesses without email, query Hunter Domain Search by website domain."""
    if not HUNTER_API_KEY:
        raise SystemExit("HUNTER_API_KEY missing in .env — buy Hunter Bulk and set it")

    biz_path = CITIES_DIR / city_id / "businesses.json"
    payload = load_json(biz_path)
    cache = load_hunter_cache()

    targets = [b for b in payload["businesses"]
               if not b.get("email") and b.get("website")]
    print(f"Hunter fill: {len(targets)} businesses without email but with website...")

    found = 0
    skipped_no_domain = 0
    failed = 0
    with httpx.Client() as client:
        for i, b in enumerate(targets, 1):
            domain = extract_root_domain(b["website"])
            if not domain:
                skipped_no_domain += 1
                continue
            data = hunter_domain_search(client, domain, cache)
            if "errors" in data:
                failed += 1
                if i <= 3 or i % 25 == 0:
                    err = data["errors"][0] if data["errors"] else {}
                    print(f"    ! Hunter error for {domain}: {err}")
                continue
            email, confidence, verification_status = hunter_pick_email(data)
            if email:
                b["email"] = email
                b["email_source"] = "hunter_search"
                # Use Hunter's bundled verification if available — saves a verify credit
                b["email_status"] = verification_status if verification_status else "unverified"
                b["email_confidence"] = confidence
                found += 1
            if i % 10 == 0:
                print(f"  progress: {i}/{len(targets)} (found: {found}, failed: {failed}) — saving...")
                _safe_dump(biz_path, payload)
            time.sleep(0.3)

    dump_json(biz_path, payload)
    print(f"\nHunter fill done: {found} new emails, {failed} failed, {skipped_no_domain} no domain")
    print(f"  cached lookups: {len(cache['domain_search'])}")


def hunter_verify_all(city_id: str) -> None:
    """Verify all emails via Hunter Verifier."""
    if not HUNTER_API_KEY:
        raise SystemExit("HUNTER_API_KEY missing in .env")

    biz_path = CITIES_DIR / city_id / "businesses.json"
    payload = load_json(biz_path)
    cache = load_hunter_cache()

    targets = [b for b in payload["businesses"]
               if b.get("email") and b.get("email_status") in ("", "unverified", None)]
    print(f"Hunter verify: {len(targets)} unverified emails...")

    valid = 0
    invalid = 0
    risky = 0
    failed = 0
    with httpx.Client() as client:
        for i, b in enumerate(targets, 1):
            email = b["email"]
            data = hunter_verify(client, email, cache)
            if "errors" in data:
                failed += 1
                continue
            verify_data = data.get("data") or {}
            status = verify_data.get("status", "unknown")  # valid, invalid, accept_all, webmail, disposable, unknown
            score = verify_data.get("score", 0)
            b["email_status"] = status
            if not b.get("email_confidence"):
                b["email_confidence"] = score
            if status == "valid":
                valid += 1
            elif status == "invalid":
                invalid += 1
            else:
                risky += 1
            if i % 20 == 0:
                print(f"  progress: {i}/{len(targets)} (valid: {valid}, invalid: {invalid}, risky: {risky}) — saving...")
                _safe_dump(biz_path, payload)
            time.sleep(0.3)

    _safe_dump(biz_path, payload)
    print(f"\nHunter verify done:")
    print(f"  valid:   {valid}")
    print(f"  invalid: {invalid}")
    print(f"  risky:   {risky} (accept_all/webmail/disposable/unknown)")
    print(f"  failed:  {failed}")


# ---------------------------------------------------------------------------
# CSV export (with chain filter)
# ---------------------------------------------------------------------------
def export_mailing_list(city_id: str, include_chains: bool = False) -> None:
    cfg = CITY_CONFIGS.get(city_id)
    if not cfg:
        raise SystemExit(f"No config for city '{city_id}'")
    city_dir = CITIES_DIR / city_id
    base = load_json(city_dir / "base.json")
    biz = load_json(city_dir / "businesses.json")["businesses"]
    blocklist = load_json(BLOCKLIST_PATH)
    city_name = base["city"]["name"]
    country = cfg.get("country", base["city"].get("country", ""))

    MAILING_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MAILING_DIR / f"{city_id}_mailing_list.csv"

    rows_written = 0
    chains_skipped = 0
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "Name", "Business_Type", "Address", "City", "Country",
            "Phone", "Website", "Email", "Email_Status", "Email_Source",
            "Email_Confidence", "Google_Rating", "Review_Count", "Source", "Zone",
        ])
        for b in biz:
            if not include_chains and is_chain(b.get("name", ""), blocklist):
                chains_skipped += 1
                continue
            writer.writerow([
                b.get("name", ""),
                b.get("type", ""),
                b.get("address", ""),
                city_name,
                country,
                b.get("phone", ""),
                b.get("website", ""),
                b.get("email", ""),
                b.get("email_status", ""),
                b.get("email_source", ""),
                b.get("email_confidence", ""),
                b.get("rating", ""),
                b.get("review_count", ""),
                b.get("source", ""),
                b.get("zone_id", ""),
            ])
            rows_written += 1

    print(f"\nCSV: {out_path}  ({rows_written} rows, {chains_skipped} chains skipped)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich businesses + mailing list pipeline")
    parser.add_argument("--city", required=True, help="City id (e.g. dallas)")
    parser.add_argument("--enrich-seeded", action="store_true",
                        help="Fill missing address/phone/website on seeded businesses (Google Places)")
    parser.add_argument("--no-scrape", action="store_true",
                        help="During default Places search, skip W1 email scraping")
    parser.add_argument("--rescrape-emails", action="store_true",
                        help="Re-run W1 (own site) + W2 (Facebook) email scraping")
    parser.add_argument("--hunter-fill", action="store_true",
                        help="Hunter Search API: fill emails for businesses without one")
    parser.add_argument("--hunter-verify", action="store_true",
                        help="Hunter Verifier API: verify all unverified emails")
    parser.add_argument("--export-only", action="store_true",
                        help="Skip everything; just export the CSV")
    parser.add_argument("--include-chains", action="store_true",
                        help="Include chain businesses in the CSV mailing list")
    args = parser.parse_args()

    # exclusive operation modes
    if args.enrich_seeded:
        enrich_seeded(args.city)
    elif args.rescrape_emails:
        rescrape_emails(args.city)
    elif args.hunter_fill:
        hunter_fill(args.city)
    elif args.hunter_verify:
        hunter_verify_all(args.city)
    elif not args.export_only:
        enrich_city(args.city, scrape_emails=not args.no_scrape)

    export_mailing_list(args.city, include_chains=args.include_chains)


if __name__ == "__main__":
    main()

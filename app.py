from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests
import math
import time
import os
import re

app = FastAPI(title="RoadSoS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
GOOGLE_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
GOOGLE_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"

HEADERS = {"User-Agent": "RoadSoS/1.0 hackathon app"}

CACHE = {}
CACHE_TTL_SECONDS = 300
RESULT_LIMIT = 10


def haversine(lat1, lon1, lat2, lon2):
    r = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )

    return round(r * 2 * math.asin(math.sqrt(a)), 2)


SERVICE_MAP = {
    "police": [("amenity", "police")],
    "fire": [("amenity", "fire_station")],
    "hospital": [("amenity", "hospital"), ("healthcare", "hospital")],
    "clinic": [("amenity", "clinic"), ("amenity", "doctors"), ("healthcare", "clinic")],
    "medical": [("amenity", "pharmacy"), ("healthcare", "pharmacy"), ("shop", "chemist")],
    "ambulance": [("emergency", "ambulance_station"), ("amenity", "hospital")],
    "fuel": [("amenity", "fuel")],
    "tow": [("shop", "car_repair"), ("shop", "car")],
    "puncture": [("shop", "tyres"), ("shop", "car_repair")],
}

GOOGLE_SERVICE_MAP = {
    "police": {"types": ["police"], "queries": ["police station near me"]},
    "fire": {"types": ["fire_station"], "queries": ["fire station near me"]},
    "hospital": {"types": ["hospital"], "queries": ["hospital near me"]},
    "clinic": {"types": ["doctor"], "queries": ["clinic near me doctor"]},
    "medical": {"types": ["pharmacy"], "queries": ["medical store pharmacy near me"]},
    "ambulance": {"types": ["hospital"], "queries": ["ambulance service near me"]},
    "fuel": {"types": ["gas_station"], "queries": ["petrol pump fuel station near me"]},
    "tow": {"types": ["car_repair"], "queries": ["tow service towing service vehicle breakdown near me"]},
    "puncture": {"types": ["car_repair"], "queries": ["puncture repair tyre repair near me"]},
}

FALLBACK_SERVICES = {
    "puncture": ["tow", "fuel"],
    "tow": ["puncture", "fuel"],
    "ambulance": ["hospital"],
    "clinic": ["medical", "hospital"],
    "medical": ["clinic"],
    "fire": ["police"],
}

SERVICE_KEYWORDS = {
    "police": ["police"],
    "fire": ["fire"],
    "hospital": ["hospital"],
    "clinic": ["clinic", "doctor"],
    "medical": ["medical", "pharmacy", "chemist"],
    "ambulance": ["ambulance", "hospital"],
    "fuel": ["fuel", "petrol", "diesel", "gas station", "filling station"],
    "tow": ["tow", "towing", "recovery", "garage", "service", "repair", "motors"],
    "puncture": ["puncture", "tyre", "tire", "wheel", "repair", "garage", "service", "motors"],
}

LOCAL_SERVICES = [
    {
        "name": "Prime Hospital",
        "service": "hospital",
        "phone": "+917599676555",
        "latitude": 29.229275205235847,
        "longitude": 78.97449285508725,
        "verified": True,
        "available_24x7": True,
        "address": "Local verified hospital",
        "category": "private",
    },
    {
        "name": "Civil Hospital / L D Bhatt Government Hospital",
        "service": "hospital",
        "phone": "+918750202962",
        "latitude": 29.219086,
        "longitude": 78.964223,
        "verified": True,
        "available_24x7": True,
        "address": "Kashipur local verified hospital",
        "category": "government",
    },
    {
        "name": "Joshi Hospital",
        "service": "hospital",
        "phone": "+919410112882",
        "latitude": 29.203525,
        "longitude": 78.964908,
        "verified": True,
        "available_24x7": True,
        "address": "Local verified hospital",
        "category": "private",
    },
    {
        "name": "Global Hospital",
        "service": "hospital",
        "phone": "+917298511512",
        "latitude": 29.201841,
        "longitude": 78.973241,
        "verified": True,
        "available_24x7": True,
        "address": "Local verified hospital",
        "category": "private",
    },
    {
        "name": "Kashipur Police Station",
        "service": "police",
        "phone": "+915947274015",
        "latitude": 29.210899,
        "longitude": 78.960522,
        "verified": True,
        "available_24x7": True,
        "address": "Kashipur Police Station",
        "category": "government",
    },
    {
        "name": "ITI Police Station Kashipur",
        "service": "police",
        "phone": None,
        "latitude": 29.189834,
        "longitude": 78.993651,
        "verified": True,
        "available_24x7": True,
        "address": "ITI Police Station, Kashipur",
        "category": "government",
    },
    {
        "name": "Fire Brigade Kashipur",
        "service": "fire",
        "phone": "101",
        "latitude": 29.200283,
        "longitude": 78.976203,
        "verified": True,
        "available_24x7": True,
        "address": "Kashipur Fire Brigade",
        "category": "government",
    },
    {
        "name": "HP Petrol Pump",
        "service": "fuel",
        "phone": None,
        "latitude": 29.262252,
        "longitude": 79.008288,
        "verified": True,
        "available_24x7": False,
        "address": "Local verified fuel station",
        "category": "fuel",
    },
    {
        "name": "Shiv Sai Filling Station",
        "service": "fuel",
        "phone": None,
        "latitude": 29.259182,
        "longitude": 79.002979,
        "verified": True,
        "available_24x7": False,
        "address": "Local verified fuel station",
        "category": "fuel",
    },
    {
        "name": "Indian Oil Petrol Pump",
        "service": "fuel",
        "phone": None,
        "latitude": 29.213025,
        "longitude": 78.962563,
        "verified": True,
        "available_24x7": False,
        "address": "Local verified fuel station",
        "category": "fuel",
    },
    {
        "name": "Shri Shanti Swaroop Filling Station",
        "service": "fuel",
        "phone": None,
        "latitude": 29.275267,
        "longitude": 79.019568,
        "verified": True,
        "available_24x7": False,
        "address": "Local verified fuel station",
        "category": "fuel",
    },
    {
        "name": "Kukku Tyre House",
        "service": "puncture",
        "phone": "+919927065928",
        "latitude": 29.203191,
        "longitude": 78.946690,
        "verified": True,
        "available_24x7": False,
        "address": "Local verified tyre and puncture repair",
        "category": "puncture",
    },
    {
        "name": "Kukku Tyre House",
        "service": "tow",
        "phone": "+919927065928",
        "latitude": 29.203191,
        "longitude": 78.946690,
        "verified": True,
        "available_24x7": False,
        "address": "Local verified tyre and towing help",
        "category": "vehicle_service",
    },
    {
        "name": "Om Motors Maruti Suzuki Service Centre",
        "service": "puncture",
        "phone": None,
        "latitude": 29.208082,
        "longitude": 78.987767,
        "verified": True,
        "available_24x7": False,
        "address": "Local verified vehicle and puncture support",
        "category": "vehicle_service",
    },
    {
        "name": "Om Motors Maruti Suzuki Service Centre",
        "service": "tow",
        "phone": None,
        "latitude": 29.208082,
        "longitude": 78.987767,
        "verified": True,
        "available_24x7": False,
        "address": "Local verified vehicle service centre",
        "category": "vehicle_service",
    },
    {
        "name": "Bindal Hyundai",
        "service": "puncture",
        "phone": "+917948058623",
        "latitude": 29.178235,
        "longitude": 79.014666,
        "verified": True,
        "available_24x7": False,
        "address": "Local verified Hyundai service and puncture support",
        "category": "vehicle_service",
    },
    {
        "name": "Bindal Hyundai",
        "service": "tow",
        "phone": "+917948058623",
        "latitude": 29.178235,
        "longitude": 79.014666,
        "verified": True,
        "available_24x7": False,
        "address": "Local verified Hyundai service centre",
        "category": "vehicle_service",
    },
]


def dedupe_and_sort(results):
    seen = set()
    unique = []

    for item in results:
        key = (
            item["name"].lower(),
            round(item["latitude"], 4),
            round(item["longitude"], 4),
            item.get("service"),
        )

        if key not in seen:
            seen.add(key)
            unique.append(item)

    return sorted(unique, key=lambda x: x["distance_km"])


def limit_with_verified_priority(results, result_limit):
    sorted_results = dedupe_and_sort(results)
    verified_local = [
        item for item in sorted_results
        if item.get("verified") and item.get("source") in ("local", "local_verified")
    ]
    other_results = [
        item for item in sorted_results
        if not (item.get("verified") and item.get("source") in ("local", "local_verified"))
    ]
    return (verified_local + other_results)[:result_limit]


def is_relevant_google_place(place, service):
    config = GOOGLE_SERVICE_MAP.get(service, {})
    accepted_types = set(config.get("types", []))
    place_types = set(place.get("types", []))

    if accepted_types.intersection(place_types):
        return True

    display_name = place.get("displayName", {})
    name = display_name.get("text", "").lower()
    address = place.get("formattedAddress", "").lower()
    searchable_text = f"{name} {address}"

    return any(keyword in searchable_text for keyword in SERVICE_KEYWORDS.get(service, []))


def get_local_services(lat, lon, service, max_radius_km):
    results = []

    for item in LOCAL_SERVICES:
        if item.get("service") != service:
            continue

        distance = haversine(lat, lon, float(item["latitude"]), float(item["longitude"]))

        if distance <= max_radius_km:
            results.append({
                "name": item["name"],
                "service": service,
                "latitude": float(item["latitude"]),
                "longitude": float(item["longitude"]),
                "distance_km": distance,
                "eta_minutes": max(1, int((distance / 40) * 60)),
                "phone": item.get("phone"),
                "verified": item.get("verified", True),
                "available_24x7": item.get("available_24x7", False),
                "source": "local",
                "address": item.get("address"),
                "category": item.get("category"),
            })

    return results


def build_overpass_query(lat, lon, service, radius):
    query_parts = []

    for key, value in SERVICE_MAP[service]:
        query_parts.append(f'node["{key}"="{value}"](around:{radius},{lat},{lon});')
        query_parts.append(f'way["{key}"="{value}"](around:{radius},{lat},{lon});')
        query_parts.append(f'relation["{key}"="{value}"](around:{radius},{lat},{lon});')

    return f"""
    [out:json][timeout:6];
    (
      {"".join(query_parts)}
    );
    out center tags;
    """


def get_osm_services(lat, lon, service, radius):
    cache_key = f"osm:{round(lat, 3)}:{round(lon, 3)}:{service}:{radius}"
    now = time.time()

    if cache_key in CACHE:
        cached_time, cached_data = CACHE[cache_key]
        if now - cached_time < CACHE_TTL_SECONDS:
            return cached_data

    response = requests.post(
        OVERPASS_URL,
        data={"data": build_overpass_query(lat, lon, service, radius)},
        headers=HEADERS,
        timeout=6,
    )
    response.raise_for_status()

    data = response.json()
    results = []

    for item in data.get("elements", []):
        tags = item.get("tags", {})
        item_lat = item.get("lat")
        item_lon = item.get("lon")

        if item_lat is None or item_lon is None:
            center = item.get("center", {})
            item_lat = center.get("lat")
            item_lon = center.get("lon")

        if item_lat is None or item_lon is None:
            continue

        name = tags.get("name") or tags.get("operator") or tags.get("brand") or service.title()
        phone = tags.get("phone") or tags.get("contact:phone") or tags.get("mobile")
        distance = haversine(lat, lon, float(item_lat), float(item_lon))

        results.append({
            "name": name,
            "service": service,
            "latitude": float(item_lat),
            "longitude": float(item_lon),
            "distance_km": distance,
            "eta_minutes": max(1, int((distance / 40) * 60)),
            "phone": phone,
            "verified": False,
            "available_24x7": False,
            "source": "openstreetmap",
            "address": None,
        })

    CACHE[cache_key] = (now, results)
    return results


def parse_google_places(data, lat, lon, service):
    results = []

    for place in data.get("places", []):
        if not is_relevant_google_place(place, service):
            continue

        location = place.get("location", {})
        item_lat = location.get("latitude")
        item_lon = location.get("longitude")

        if item_lat is None or item_lon is None:
            continue

        display_name = place.get("displayName", {})
        name = display_name.get("text") or service.title()
        distance = haversine(lat, lon, float(item_lat), float(item_lon))

        results.append({
            "name": name,
            "service": service,
            "latitude": float(item_lat),
            "longitude": float(item_lon),
            "distance_km": distance,
            "eta_minutes": max(1, int((distance / 40) * 60)),
            "phone": None,
            "verified": False,
            "available_24x7": False,
            "source": "google_places",
            "address": place.get("formattedAddress"),
            "google_maps_url": place.get("googleMapsUri"),
            "types": place.get("types", []),
        })

    return results


def get_google_places(lat, lon, service, radius):
    if not GOOGLE_API_KEY:
        return []

    config = GOOGLE_SERVICE_MAP.get(service)
    if not config:
        return []

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": (
            "places.displayName,"
            "places.location,"
            "places.formattedAddress,"
            "places.googleMapsUri,"
            "places.types"
        ),
    }

    all_results = []

    for place_type in config["types"]:
        payload = {
            "includedTypes": [place_type],
            "maxResultCount": 10,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lon},
                    "radius": float(radius),
                }
            },
        }

        try:
            response = requests.post(GOOGLE_NEARBY_URL, json=payload, headers=headers, timeout=6)
            if response.status_code == 200:
                all_results.extend(parse_google_places(response.json(), lat, lon, service))
            else:
                print("Google Nearby error:", response.status_code, response.text)
        except requests.RequestException as err:
            print("Google Nearby timeout/error:", err)

    for query in config["queries"]:
        payload = {
            "textQuery": query,
            "maxResultCount": 10,
            "locationBias": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lon},
                    "radius": float(radius),
                }
            },
        }

        try:
            response = requests.post(GOOGLE_TEXT_URL, json=payload, headers=headers, timeout=6)
            if response.status_code == 200:
                all_results.extend(parse_google_places(response.json(), lat, lon, service))
            else:
                print("Google Text error:", response.status_code, response.text)
        except requests.RequestException as err:
            print("Google Text timeout/error:", err)

    return dedupe_and_sort(all_results)


def search_service(lat, lon, service, search_radii, result_limit=RESULT_LIMIT):
    collected_results = []
    used_radius = None
    google_used = False

    for radius in search_radii:
        local_results = get_local_services(lat, lon, service, radius / 1000)

        try:
            osm_results = get_osm_services(lat, lon, service, radius)
        except requests.RequestException as err:
            print("OSM error:", err)
            osm_results = []

        google_results = get_google_places(lat, lon, service, radius)
        if google_results:
            google_used = True

        collected_results = limit_with_verified_priority(
            collected_results + local_results + osm_results + google_results,
            result_limit,
        )

        used_radius = radius

        if len(collected_results) >= result_limit:
            break

    return limit_with_verified_priority(collected_results, result_limit), used_radius, google_used


def normalize_emergency_text(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text)


def infer_service_from_text(text):
    original_text = text
    text = normalize_emergency_text(text)

    rules = [
        {
            "service": "fire",
            "keywords": [
                "fire", "smoke", "burning", "burn", "blast", "explosion",
                "cylinder blast", "aag", "aag lagi",
            ],
            "message": "Fire emergency detected. Searching nearest fire station.",
        },
        {
            "service": "hospital",
            "keywords": [
                "accident", "crash", "collision", "hit", "injury", "injured",
                "bleeding", "blood", "unconscious", "fainted", "sick", "pain",
                "heart", "stroke", "fracture", "medical emergency", "emergency medical",
                "behosh", "chot", "khoon", "tabiyat", "hurt",
            ],
            "message": "Accident or medical emergency detected. Searching nearest hospital.",
        },
        {
            "service": "puncture",
            "keywords": [
                "puncture", "puncher", "pancher", "panchar", "flat tyre",
                "flat tire", "tyre puncture", "tire puncture", "wheel puncture",
                "tyre burst", "tire burst", "flat wheel",
            ],
            "message": "Tyre puncture detected. Searching nearest puncture repair.",
        },
        {
            "service": "tow",
            "keywords": [
                "tow", "towing", "breakdown", "engine failure", "vehicle stopped",
                "car stopped", "car broke", "vehicle broke", "not starting",
                "won t start", "cannot start", "engine problem", "car stuck",
                "vehicle stuck", "gaadi band", "gadi band",
            ],
            "message": "Vehicle breakdown detected. Searching nearest tow service.",
        },
        {
            "service": "fuel",
            "keywords": [
                "fuel", "petrol", "diesel", "gas", "empty tank", "no petrol",
                "out of fuel", "no diesel", "petrol khatam", "fuel khatam",
            ],
            "message": "Fuel request detected. Searching nearest fuel station.",
        },
        {
            "service": "police",
            "keywords": [
                "police", "robbery", "crime", "unsafe", "threat", "fight",
                "harassment", "stolen", "stole", "theft", "snatched",
                "snatching", "bike stolen", "bike theft", "vehicle stolen",
                "car stolen", "stole my car", "vehicle theft", "car theft",
                "robbed", "rob", "loot", "looted", "chor", "chori",
                "chori ho gayi", "someone took my", "somebody took my",
                "bike chori", "car chori", "phone chori",
            ],
            "message": "Safety emergency detected. Searching nearest police station.",
        },
        {
            "service": "medical",
            "keywords": ["medicine", "pharmacy", "tablet", "medical store", "drug", "chemist"],
            "message": "Medicine request detected. Searching nearest medical store.",
        },
        {
            "service": "clinic",
            "keywords": ["clinic", "doctor", "checkup", "check up"],
            "message": "Doctor request detected. Searching nearest clinic.",
        },
    ]

    for rule in rules:
        if any(keyword in text for keyword in rule["keywords"]):
            return {
                "input": original_text,
                "service": rule["service"],
                "message": rule["message"],
            }

    return {
        "input": original_text,
        "service": "hospital",
        "message": "Emergency type unclear. Searching nearest hospital by default.",
    }


@app.get("/")
def home():
    return {
        "message": "RoadSoS API running",
        "test": "/assist?lat=29.21&lon=78.96&service=hospital",
    }


@app.get("/debug-google")
def debug_google():
    return {
        "google_key_loaded": bool(GOOGLE_API_KEY),
        "key_preview": GOOGLE_API_KEY[:6] + "..." if GOOGLE_API_KEY else None,
    }


@app.get("/ai-assist")
def ai_assist(text: str):
    return infer_service_from_text(text)


@app.get("/assist")
def assist(
    lat: float,
    lon: float,
    service: str = Query(...),
    allow_fallback: bool = Query(False),
    limit: int = Query(RESULT_LIMIT, ge=1, le=20),
):
    service = service.lower().strip()

    if service not in SERVICE_MAP:
        return {
            "error": "Service not supported",
            "supported_services": list(SERVICE_MAP.keys()),
        }

    search_radii = [10000, 25000, 50000, 100000]

    final_results, used_radius, google_fallback_used = search_service(
        lat,
        lon,
        service,
        search_radii,
        result_limit=limit,
    )

    fallback_used = False
    fallback_service = None

    if allow_fallback and not final_results and service in FALLBACK_SERVICES:
        for alt_service in FALLBACK_SERVICES[service]:
            alt_results, alt_radius, alt_google = search_service(
                lat,
                lon,
                alt_service,
                search_radii,
                result_limit=limit,
            )

            if alt_results:
                final_results = alt_results
                used_radius = alt_radius
                google_fallback_used = alt_google
                fallback_used = True
                fallback_service = alt_service
                break

    if not final_results:
        return {
            "service": service,
            "count": 0,
            "radius_used_meters": used_radius,
            "google_fallback_used": google_fallback_used,
            "fallback_used": fallback_used,
            "fallback_service": fallback_service,
            "results": [],
            "message": "No nearby service found",
        }

    return {
        "service": service,
        "count": len(final_results),
        "radius_used_meters": used_radius,
        "google_fallback_used": google_fallback_used,
        "fallback_used": fallback_used,
        "fallback_service": fallback_service,
        "results": final_results,
    }

# #backend:pip install fastapi uvicorn requests
# uvicorn app:app --reload --host 127.0.0.1 --port 8000
# frontend:python -m http.server 8080
#browser:http://127.0.0.1:8080/index.html

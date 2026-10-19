from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    redirect,
    url_for,
    session,
    abort
)

import sqlite3
import os
import json
import logging
import re
from pathlib import Path


# ============================================================
# APPLICATION
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "MOTORNATION_SECRET_KEY",
    "motornation-development-secret-change-this"
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATABASE_DIR = BASE_DIR / "database"

DATABASE_FILE = DATABASE_DIR / "motornation.db"

IMAGE_DIR = BASE_DIR / "static" / "images"

GALLERIES_FILE = BASE_DIR / "data" / "vehicle_galleries.json"
NEWS_REVIEWS_FILE = BASE_DIR / "data" / "news_and_reviews.json"

DATABASE_DIR.mkdir(
    parents=True,
    exist_ok=True
)

IMAGE_DIR.mkdir(
    parents=True,
    exist_ok=True
)

_cached_galleries = None
_cached_news_reviews = None


def get_vehicle_gallery(vehicle_id, make, model):
    """
    Return the rich multi-photo gallery list for a vehicle.
    """
    global _cached_galleries
    if _cached_galleries is None:
        if GALLERIES_FILE.exists():
            try:
                with open(GALLERIES_FILE, "r", encoding="utf-8") as f:
                    _cached_galleries = json.load(f)
            except Exception as e:
                app.logger.warning(f"Could not load vehicle galleries: {e}")
                _cached_galleries = {}
        else:
            _cached_galleries = {}

    vid_key = str(vehicle_id) if vehicle_id is not None else ""
    name_key = f"{make}_{model}".lower() if make and model else ""

    gallery = _cached_galleries.get(vid_key) or _cached_galleries.get(name_key) or []
    return gallery


def get_news_and_reviews():
    """
    Return the full news and road test reviews dataset.
    """
    global _cached_news_reviews
    if _cached_news_reviews is None:
        if NEWS_REVIEWS_FILE.exists():
            try:
                with open(NEWS_REVIEWS_FILE, "r", encoding="utf-8") as f:
                    _cached_news_reviews = json.load(f)
            except Exception as e:
                app.logger.warning(f"Could not load news and reviews: {e}")
                _cached_news_reviews = {"items": [], "by_id": {}, "by_key": {}}
        else:
            _cached_news_reviews = {"items": [], "by_id": {}, "by_key": {}}
    return _cached_news_reviews


# ============================================================
# MOTORNATION OFFICIAL REVIEWS DATASET & BUILDER
# ============================================================

MOTORNATION_REVIEWS_FILE = DATABASE_DIR / "motornation_reviews.json"
_cached_motornation_reviews = None


def get_motornation_editorial_reviews():
    """
    Return the cached MotorNation official road test reviews dataset.
    """
    global _cached_motornation_reviews
    if _cached_motornation_reviews is None:
        if MOTORNATION_REVIEWS_FILE.exists():
            try:
                with open(MOTORNATION_REVIEWS_FILE, "r", encoding="utf-8") as f:
                    _cached_motornation_reviews = json.load(f)
            except Exception as e:
                app.logger.warning(f"Could not load motornation reviews: {e}")
                _cached_motornation_reviews = []
        else:
            _cached_motornation_reviews = []
    return _cached_motornation_reviews


def match_api_review(car):
    """
    Match a car with the official MotorNation editorial review dataset.
    """
    if not car:
        return None
    api_reviews = get_motornation_editorial_reviews()
    if not api_reviews:
        return None

    def norm(txt):
        return re.sub(r'[^a-z0-9]', '', (txt or '').lower())

    make_clean = norm(car.get('make'))
    model_clean = norm(car.get('model'))
    make_raw = (car.get('make') or '').lower().strip()
    model_raw = (car.get('model') or '').lower().strip()

    # Priority 1: Exact match on make and model in slug or car_name
    for r in api_reviews:
        slug_norm = norm(r.get('slug'))
        cname_norm = norm(r.get('car_name'))
        if make_clean and model_clean:
            if make_clean in slug_norm and model_clean in slug_norm:
                return r
            if make_clean in cname_norm and model_clean in cname_norm:
                return r

    # Priority 2: Exact word boundary match on model in slug
    model_slug = re.sub(r'[^a-z0-9]+', '-', model_raw).strip('-')
    if make_raw and model_slug:
        for r in api_reviews:
            slug = (r.get('slug') or '').lower()
            if make_raw in slug and re.search(r'(?<![a-z0-9])' + re.escape(model_slug) + r'(?![a-z0-9])', slug):
                return r

    # Priority 3: First 2 tokens of model (e.g. ioniq-5)
    model_tokens = [t for t in re.split(r'[\s\-]+', model_raw) if len(t) > 1]
    if len(model_tokens) >= 2:
        two_token = f"{model_tokens[0]}-{model_tokens[1]}"
        for r in api_reviews:
            slug = (r.get('slug') or '').lower()
            if make_raw in slug and two_token in slug:
                return r

    # Priority 4: Word token match with longest word first (excluding generic category words)
    skip_words = {'class', 'series', 'supercrew', 'cab', 'coupe', 'sedan', 'suv', 'truck', 'hybrid', 'electric'}
    model_words = sorted([w for w in model_tokens if len(w) > 2 and w not in skip_words], key=len, reverse=True)
    for mw in model_words:
        for r in api_reviews:
            slug = (r.get('slug') or '').lower()
            cname = (r.get('car_name') or '').lower()
            text = slug + ' ' + cname
            if make_raw in text and mw in text:
                return r

    return None


def format_content_html(val):
    """
    Format string or list content into clean semantic HTML paragraphs or list items.
    """
    if not val:
        return ""
    if isinstance(val, list):
        items = "".join(f"<li>{item}</li>" for item in val if item)
        return f"<ul class='editorial-points-list'>{items}</ul>"
    val_str = str(val).strip()
    if "\n" in val_str:
        paras = [p.strip() for p in val_str.split("\n") if p.strip()]
        return "".join(f"<p>{p}</p>" for p in paras)
    return f"<p>{val_str}</p>"


def build_review_data(car):
    """
    Build complete structured review data conforming to the official MotorNation review layout:
    Overview, Pricing, Powertrain, Interior, Technology, Safety, Warranty, Pros, Cons, MotorNation Take,
    and a multi-photo gallery.
    """
    if not car:
        return {}

    api_rev = match_api_review(car) or {}

    year = car.get('year') or '2026'
    make = car.get('make') or 'Unknown'
    model = car.get('model') or 'Vehicle'
    trim = car.get('trim') or ''
    msrp = car.get('msrp')
    msrp_str = f"${msrp:,.0f}" if (msrp and isinstance(msrp, (int, float)) and msrp > 0) else "Pricing varies by configuration"

    # Clean car review title matching reference page
    car_name = f"{year} {make} {model} Review"

    # Pros
    pros_val = api_rev.get('pros') or car.get('pros') or f"Exceptional driving dynamics, distinct {make} road presence, and refined ergonomics tailored for everyday versatility."
    # Cons
    cons_val = api_rev.get('cons') or car.get('cons') or f"Premium option packages elevate overall cost, and specialized performance modes demand a slight learning curve."
    # MotorNation's Take
    mn_take_val = api_rev.get('mn_take') or car.get('finalWord') or car.get('reviewSummary') or car.get('editorial_verdict') or (
        f"The {year} {make} {model} stands as a formidable contender in its class, striking an enviable balance between emotional performance and pragmatic luxury."
    )

    # Overview
    overview_val = api_rev.get('overview')
    if not overview_val:
        body = car.get('bodyType') or 'vehicle'
        overview_val = (
            f"The {year} {make} {model} {trim} cements {make}'s enduring reputation for precision engineering and progressive design. "
            f"Positioned in the competitive {body.lower()} landscape, it pairs athletic exterior styling with driver-centric chassis tuning. "
            f"Whether navigating daily suburban commutes or conquering long-distance highway tours, the {model} delivers a composed, engaging demeanor that reflects MotorNation's rigorous road test benchmarks."
        )

    # Pricing
    pricing_val = api_rev.get('pricing')
    if not pricing_val:
        pricing_val = (
            f"Starting at an MSRP of {msrp_str}, the {year} {make} {model} provides competitive value against direct segment rivals. "
            f"Standard equipment includes high-tier driver assistance, advanced digital telemetry, and premium interior appointments, "
            f"with upper trims and tailored option bundles offering bespoke personalisation."
        )

    # Powertrain
    drivetrain_val = api_rev.get('drivetrain')
    if not drivetrain_val:
        eng = car.get('engine') or 'Responsive powertrain'
        hp = car.get('horsepower')
        hp_str = f"producing {int(hp)} horsepower" if hp else "delivering spirited power"
        tq = car.get('torque')
        tq_str = f"and {int(tq)} lb-ft of torque" if tq else ""
        trans = car.get('transmission') or 'automatic'
        drive = car.get('drivetrain') or 'All-Wheel Drive'
        mpg = car.get('mpg')
        mpg_str = f"Achieving up to {mpg} MPG combined efficiency, " if mpg else ""
        drivetrain_val = (
            f"Motivated by a {eng} {hp_str} {tq_str}, the {model} channels output through a slick {trans} transmission to the {drive} system. "
            f"{mpg_str}the powertrain exhibits razor-sharp throttle modulation and robust passing power across the entire rev band, bolstered by adaptive drive modes for tailored road feel."
        )

    # Interior
    interior_val = api_rev.get('interior')
    if not interior_val:
        seats = car.get('seating') or 5
        cargo = car.get('cargo')
        cargo_str = f"with {cargo} cubic feet of cargo volume behind the rear row" if cargo else "with versatile luggage and gear accommodation"
        interior_val = (
            f"Inside, the {model} welcomes {seats} occupants with meticulously sculpted seating, intuitive touchpoints, and premium soft-touch materials. "
            f"Acoustic laminated glass and active noise cancellation foster a serene sanctuary, {cargo_str} for road trip convenience."
        )

    # Technology
    technology_val = api_rev.get('technology')
    if not technology_val:
        technology_val = (
            f"Technological refinement is highlighted by a crystal-clear touchscreen infotainment hub with wireless Apple CarPlay and Android Auto capability. "
            f"A customizable digital driver display places vital navigation, telemetry, and media feedback directly in the driver's sightline, complemented by multiple high-speed USB-C charging ports and available high-fidelity audio."
        )

    # Safety
    safety_val = api_rev.get('safety')
    if not safety_val:
        safety_val = (
            f"Safety is paramount, featuring an advanced driver-assistance suite that incorporates forward collision warning with automatic emergency braking, "
            f"lane departure mitigation with lane-keeping assist, blind-spot monitoring, rear cross-traffic alert, and adaptive cruise control for relaxed, secure travel."
        )

    # Warranty
    warranty_val = api_rev.get('warranty')
    if not warranty_val:
        warranty_val = (
            f"The {year} {make} {model} is backed by comprehensive manufacturer coverage, including a 4-year/50,000-mile limited bumper-to-bumper warranty, "
            f"a 5-year/60,000-mile powertrain guarantee, and complimentary 24/7 roadside assistance for peace of mind."
        )

    # Collect images
    images = []
    seen = set()

    # 1. API review images first if available
    if api_rev.get('images'):
        for u in api_rev['images']:
            if u and u not in seen:
                images.append(u)
                seen.add(u)

    # 2. Vehicle gallery images
    gallery = get_vehicle_gallery(car.get('id'), car.get('make'), car.get('model'))
    for g in gallery:
        u = g.get('url') if isinstance(g, dict) else g
        if u and u not in seen:
            images.append(u)
            seen.add(u)

    # 3. Primary car image
    if car.get('image') and car.get('image') not in seen:
        images.insert(0, car.get('image'))
        seen.add(car.get('image'))

    main_image = images[0] if images else (car.get('image') or '')
    drivetrain_image = images[1] if len(images) > 1 else None
    interior_image = images[2] if len(images) > 2 else None
    technology_image = images[3] if len(images) > 3 else None
    safety_image = images[4] if len(images) > 4 else None
    warranty_image = images[5] if len(images) > 5 else None

    return {
        "car_name": car_name,
        "model_year": year,
        "slug": api_rev.get('slug') or f"{year}-{make}-{model}".lower().replace(' ', '-'),
        "pros": format_content_html(pros_val),
        "cons": format_content_html(cons_val),
        "mn_take": format_content_html(mn_take_val),
        "overview": format_content_html(overview_val),
        "pricing": format_content_html(pricing_val),
        "drivetrain": format_content_html(drivetrain_val),
        "interior": format_content_html(interior_val),
        "technology": format_content_html(technology_val),
        "safety": format_content_html(safety_val),
        "warranty": format_content_html(warranty_val),
        "images": images,
        "main_image": main_image,
        "drivetrain_image": drivetrain_image,
        "interior_image": interior_image,
        "technology_image": technology_image,
        "safety_image": safety_image,
        "warranty_image": warranty_image,
        "api_matched": bool(api_rev)
    }


# ============================================================
# VEHICLE TRIMS & MSRP RANGE ENGINE
# ============================================================

BACKUP_DATABASE_FILE = DATABASE_DIR / "motornation_455_backup.db"

CURATED_EXTRA_TRIMS = {
    ("bmw", "m2"): [
        {"trim": "Coupe 6MT", "msrp": 66075, "hp": 473, "fuel": "Gasoline", "trans": "6-Speed Manual", "engine": "3.0L Twin-Turbo I6 (S58)", "drivetrain": "Rear-Wheel Drive"},
        {"trim": "Coupe Steptronic", "msrp": 66075, "hp": 473, "fuel": "Gasoline", "trans": "8-Speed M Sport Auto", "engine": "3.0L Twin-Turbo I6 (S58)", "drivetrain": "Rear-Wheel Drive"},
        {"trim": "CS Track Edition", "msrp": 82000, "hp": 523, "fuel": "Gasoline", "trans": "8-Speed M Sport Auto", "engine": "3.0L Twin-Turbo I6 (S58)", "drivetrain": "Rear-Wheel Drive"}
    ],
    ("porsche", "718 boxster"): [
        {"trim": "Boxster Base", "msrp": 72800, "hp": 300, "fuel": "Gasoline", "trans": "6-Speed Manual", "engine": "2.0L Turbo Boxer-4", "drivetrain": "Rear-Wheel Drive"},
        {"trim": "Boxster S", "msrp": 84400, "hp": 350, "fuel": "Gasoline", "trans": "7-Speed PDK Dual-Clutch", "engine": "2.5L Turbo Boxer-4", "drivetrain": "Rear-Wheel Drive"},
        {"trim": "GTS 4.0 6MT", "msrp": 99500, "hp": 394, "fuel": "Gasoline", "trans": "6-Speed Manual", "engine": "4.0L NA Boxer-6", "drivetrain": "Rear-Wheel Drive"},
        {"trim": "Spyder RS", "msrp": 160700, "hp": 493, "fuel": "Gasoline", "trans": "7-Speed PDK Dual-Clutch", "engine": "4.0L Flat-6", "drivetrain": "Rear-Wheel Drive"}
    ],
    ("cadillac", "escalade"): [
        {"trim": "Luxury 2WD", "msrp": 89595, "hp": 420, "fuel": "Gasoline", "trans": "10-Speed Auto", "engine": "6.2L V8", "drivetrain": "Rear-Wheel Drive"},
        {"trim": "Premium Luxury 4WD", "msrp": 98595, "hp": 420, "fuel": "Gasoline", "trans": "10-Speed Auto", "engine": "6.2L V8", "drivetrain": "Four-Wheel Drive"},
        {"trim": "Sport Platinum 4WD", "msrp": 118595, "hp": 420, "fuel": "Gasoline", "trans": "10-Speed Auto", "engine": "6.2L V8", "drivetrain": "Four-Wheel Drive"},
        {"trim": "V-Series 4WD", "msrp": 154290, "hp": 682, "fuel": "Gasoline", "trans": "10-Speed Auto", "engine": "6.2L Supercharged V8", "drivetrain": "All-Wheel Drive"}
    ],
    ("aston martin", "vantage"): [
        {"trim": "Coupe Base", "msrp": 194400, "hp": 656, "fuel": "Gasoline", "trans": "8-Speed ZF Auto", "engine": "4.0L Twin-Turbo V8", "drivetrain": "Rear-Wheel Drive"},
        {"trim": "Roadster", "msrp": 209000, "hp": 656, "fuel": "Gasoline", "trans": "8-Speed ZF Auto", "engine": "4.0L Twin-Turbo V8", "drivetrain": "Rear-Wheel Drive"}
    ],
    ("audi", "rs6 avant"): [
        {"trim": "Performance GT", "msrp": 128895, "hp": 621, "fuel": "Gasoline", "trans": "8-Speed Tiptronic", "engine": "4.0L Twin-Turbo V8", "drivetrain": "quattro All-Wheel Drive"},
        {"trim": "GT Limited Edition", "msrp": 175000, "hp": 621, "fuel": "Gasoline", "trans": "8-Speed Tiptronic", "engine": "4.0L Twin-Turbo V8", "drivetrain": "quattro All-Wheel Drive"}
    ],
    ("kia", "carnival"): [
        {"trim": "LX 8-Passenger", "msrp": 36800, "hp": 287, "fuel": "Gasoline", "trans": "8-Speed Auto", "engine": "3.5L V6", "drivetrain": "Front-Wheel Drive"},
        {"trim": "EX 8-Passenger", "msrp": 41000, "hp": 287, "fuel": "Gasoline", "trans": "8-Speed Auto", "engine": "3.5L V6", "drivetrain": "Front-Wheel Drive"},
        {"trim": "SX Prestige", "msrp": 46000, "hp": 287, "fuel": "Gasoline", "trans": "8-Speed Auto", "engine": "3.5L V6", "drivetrain": "Front-Wheel Drive"},
        {"trim": "SX Prestige Hybrid", "msrp": 54000, "hp": 242, "fuel": "Gas-Electric Hybrid", "trans": "6-Speed Auto", "engine": "1.6L Turbo I4 Hybrid", "drivetrain": "Front-Wheel Drive"}
    ],
    ("hyundai", "ioniq 5 n"): [
        {"trim": "SE Standard Range RWD", "msrp": 42500, "hp": 168, "fuel": "Electric", "trans": "Direct-Drive", "engine": "Single Rear Motor", "drivetrain": "Rear-Wheel Drive"},
        {"trim": "SEL AWD", "msrp": 51000, "hp": 320, "fuel": "Electric", "trans": "Direct-Drive", "engine": "Dual Motors AWD", "drivetrain": "All-Wheel Drive"},
        {"trim": "Limited AWD", "msrp": 55000, "hp": 320, "fuel": "Electric", "trans": "Direct-Drive", "engine": "Dual Motors AWD", "drivetrain": "All-Wheel Drive"},
        {"trim": "Base N AWD", "msrp": 67475, "hp": 641, "fuel": "Electric", "trans": "Direct-Drive", "engine": "Dual High-Output Motors", "drivetrain": "All-Wheel Drive"}
    ]
}


def get_trims_and_range_for_car(car):
    """
    Retrieve all available factory trims for a vehicle model and compute the MSRP range.
    """
    if not car:
        return [], "Price unavailable", None, None

    make = str(car.get("make") or "").strip()
    model = str(car.get("model") or "").strip()
    year = str(car.get("year") or "2026").strip()
    current_id = car.get("id") or car.get("vehicle_id")
    current_trim = str(car.get("trim") or "").strip().lower()

    trims = []
    seen_trims = set()

    # 1. Query backup 455-vehicles database
    if BACKUP_DATABASE_FILE.exists():
        try:
            conn = sqlite3.connect(BACKUP_DATABASE_FILE)
            c = conn.cursor()
            c.execute(
                'SELECT vehicle_id, Year, Make, "Model / Model Group", "Trim / Variant", MSRP, Horsepower, "Fuel Type", Engine, Transmission, Drivetrain '
                'FROM vehicles WHERE LOWER(Make) = LOWER(?) AND LOWER("Model / Model Group") = LOWER(?) ORDER BY MSRP ASC',
                (make, model)
            )
            rows = c.fetchall()
            for r in rows:
                t_name = str(r[4] or "").strip()
                if t_name and t_name.lower() not in seen_trims:
                    seen_trims.add(t_name.lower())
                    hp_val = f"{int(r[6])} hp" if r[6] else ""
                    fuel_val = str(r[7] or "").strip()
                    trans_val = str(r[9] or "").strip()
                    eng_val = str(r[8] or "").strip()
                    feats = " • ".join([f for f in [hp_val, fuel_val, trans_val] if f])
                    trims.append({
                        "id": r[0],
                        "year": r[1] or year,
                        "make": r[2] or make,
                        "model": r[3] or model,
                        "trim": t_name,
                        "full_name": f"{r[2]} {r[3]} {r[1] or year} {t_name}",
                        "msrp": r[5],
                        "msrp_formatted": f"${r[5]:,.0f}" if r[5] else "Price unavailable",
                        "horsepower": r[6],
                        "fuel_type": r[7],
                        "engine": r[8],
                        "transmission": r[9],
                        "drivetrain": r[10] if len(r) > 10 else "",
                        "key_features": feats or eng_val or "Standard Equipment",
                        "is_current": (t_name.lower() == current_trim) or (r[0] == current_id)
                    })
            conn.close()
        except Exception as e:
            app.logger.warning(f"Could not load trims from backup DB: {e}")

    # 2. Curated fallback trims if fewer than 2 trims exist
    if len(trims) < 2:
        for (m_k, mod_k), cur_list in CURATED_EXTRA_TRIMS.items():
            if m_k.lower() == make.lower() and mod_k.lower() == model.lower():
                for item in cur_list:
                    t_name = item["trim"]
                    if t_name.lower() not in seen_trims:
                        seen_trims.add(t_name.lower())
                        hp_val = f"{item['hp']} hp" if item.get('hp') else ""
                        fuel_val = item.get('fuel', '')
                        trans_val = item.get('trans', '')
                        feats = " • ".join([f for f in [hp_val, fuel_val, trans_val] if f])
                        trims.append({
                            "id": current_id,
                            "year": year,
                            "make": make,
                            "model": model,
                            "trim": t_name,
                            "full_name": f"{make} {model} {year} {t_name}",
                            "msrp": item.get('msrp'),
                            "msrp_formatted": f"${item['msrp']:,.0f}" if item.get('msrp') else "Price unavailable",
                            "horsepower": item.get('hp'),
                            "fuel_type": item.get('fuel'),
                            "engine": item.get('engine'),
                            "transmission": item.get('trans'),
                            "drivetrain": item.get('drivetrain', ''),
                            "key_features": feats,
                            "is_current": (t_name.lower() == current_trim)
                        })

    # Ensure at least the current car exists in trims if trims list is empty
    if not trims:
        hp_val = f"{int(car.get('horsepower'))} hp" if car.get('horsepower') else ""
        fuel_val = str(car.get('fuelType') or "").strip()
        trans_val = str(car.get('transmission') or "").strip()
        feats = " • ".join([f for f in [hp_val, fuel_val, trans_val] if f])
        t_name = str(car.get('trim') or "Standard").strip()
        msrp_val = car.get('msrp')
        trims.append({
            "id": current_id,
            "year": year,
            "make": make,
            "model": model,
            "trim": t_name,
            "full_name": f"{make} {model} {year} {t_name}",
            "msrp": msrp_val,
            "msrp_formatted": f"${msrp_val:,.0f}" if msrp_val else "Price unavailable",
            "horsepower": car.get('horsepower'),
            "fuel_type": car.get('fuelType'),
            "engine": car.get('engine'),
            "transmission": car.get('transmission'),
            "drivetrain": car.get('drivetrain', ''),
            "key_features": feats or "Standard Equipment",
            "is_current": True
        })

    # If none marked as current, mark the first
    if not any(t["is_current"] for t in trims):
        trims[0]["is_current"] = True

    # Sort trims by MSRP ascending
    trims.sort(key=lambda t: t.get("msrp") or 0)

    # Compute MSRP range
    msrps = [t["msrp"] for t in trims if t.get("msrp") and isinstance(t["msrp"], (int, float))]
    if msrps:
        min_m = min(msrps)
        max_m = max(msrps)
        if min_m != max_m:
            msrp_range_str = f"${min_m:,.0f} – ${max_m:,.0f}"
        else:
            msrp_range_str = f"${min_m:,.0f}"
    else:
        min_m = car.get("msrp")
        max_m = car.get("msrp")
        msrp_range_str = f"${min_m:,.0f}" if min_m else "Pricing unavailable"

    return trims, msrp_range_str, min_m, max_m


# ============================================================
# ADMIN SETTINGS
# ============================================================

ADMIN_PASSWORD = os.environ.get(
    "MOTORNATION_ADMIN_PASSWORD",
    "admin123"
)


# ============================================================
# LOGGING
# ============================================================

LOG_DIR = BASE_DIR / "logs"

LOG_DIR.mkdir(
    parents=True,
    exist_ok=True
)

LOG_FILE = LOG_DIR / "motornation.log"


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
    handlers=[
        logging.FileHandler(
            LOG_FILE,
            encoding="utf-8"
        ),
        logging.StreamHandler()
    ]
)

app.logger.setLevel(
    logging.INFO
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db():
    """
    Open a SQLite connection.

    Row factory is enabled so database columns can be
    accessed by their actual Excel/database names.
    """

    connection = sqlite3.connect(
        str(DATABASE_FILE)
    )

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# DATABASE HELPERS
# ============================================================

def quote_column(column):
    """
    Safely quote a SQLite column name.
    """

    return '"' + str(column).replace(
        '"',
        '""'
    ) + '"'


def get_vehicle_columns():
    """
    Return all columns in the vehicles table except
    the automatically managed vehicle_id column.
    """

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        PRAGMA table_info(vehicles)
        """
    )

    rows = cursor.fetchall()

    connection.close()

    columns = []

    for row in rows:

        name = row["name"]

        if name != "vehicle_id":
            columns.append(name)

    return columns


def ensure_database_structure():
    """
    Make sure the columns required by MotorNation exist.

    Existing vehicle data is preserved.
    """

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        AND name = 'vehicles'
        """
    )

    table = cursor.fetchone()

    if table is None:

        cursor.execute(
            """
            CREATE TABLE vehicles (
                vehicle_id INTEGER PRIMARY KEY AUTOINCREMENT
            )
            """
        )

    cursor.execute(
        """
        PRAGMA table_info(vehicles)
        """
    )

    existing_columns = {
        row["name"]
        for row in cursor.fetchall()
    }

    required_columns = {

        "Image": "TEXT",

        "Image URL": "TEXT",

        "Description": "TEXT"
    }

    for column, data_type in required_columns.items():

        if column not in existing_columns:

            cursor.execute(
                f"""
                ALTER TABLE vehicles
                ADD COLUMN {quote_column(column)}
                {data_type}
                """
            )

            app.logger.info(
                "Added missing database column: %s",
                column
            )

    connection.commit()

    connection.close()


try:
    ensure_database_structure()
except Exception as _e:
    app.logger.warning("Database initialization check deferred: %s", _e)


# ============================================================
# VALUE HELPERS
# ============================================================

def clean_text(value):
    """
    Convert a value to clean text.
    """

    if value is None:
        return ""

    text = str(value).strip()

    if text.lower() in {
        "nan",
        "none",
        "null",
        "nat"
    }:
        return ""

    return text


def clean_number(value):
    """
    Convert currency/numeric strings to float.

    Examples:

        "$38,000" -> 38000.0
        "38000"   -> 38000.0
        ""        -> 0
    """

    if value is None:
        return 0

    if isinstance(
        value,
        (int, float)
    ):

        try:
            return float(value)
        except Exception:
            return 0

    text = clean_text(value)

    if not text:
        return 0

    text = text.replace(
        "$",
        ""
    )

    text = text.replace(
        ",",
        ""
    )

    text = text.replace(
        "USD",
        "",
    )

    text = text.strip()

    match = re.search(
        r"-?\d+(?:\.\d+)?",
        text
    )

    if not match:
        return 0

    try:
        return float(
            match.group(0)
        )
    except Exception:
        return 0


def clean_list(value):
    """
    Convert pros/cons values into a list.

    Supports:

    - newline separated text
    - comma separated text
    - semicolon separated text
    - JSON arrays
    """

    if value is None:
        return []

    if isinstance(
        value,
        (list, tuple)
    ):

        return [
            clean_text(item)
            for item in value
            if clean_text(item)
        ]

    text = clean_text(value)

    if not text:
        return []

    # Try JSON list first
    if text.startswith("["):

        try:

            parsed = json.loads(
                text
            )

            if isinstance(
                parsed,
                list
            ):

                return [
                    clean_text(item)
                    for item in parsed
                    if clean_text(item)
                ]

        except Exception:
            pass

    # Normalize separators
    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    # Newline is the preferred format
    if "\n" in text:

        parts = text.split(
            "\n"
        )

    elif ";" in text:

        parts = text.split(
            ";"
        )

    elif "," in text:

        parts = text.split(
            ","
        )

    else:

        parts = [
            text
        ]

    cleaned = []

    for item in parts:

        item = clean_text(
            item
        )

        item = re.sub(
            r"^[•●▪◦\-–—]+\s*",
            "",
            item
        )

        if item:
            cleaned.append(
                item
            )

    return cleaned


def first_value(raw, *names):
    """
    Return the first non-empty value from several
    possible database column names.
    """

    for name in names:

        try:
            value = raw[name]
        except Exception:
            continue

        if value is not None:

            text = clean_text(
                value
            )

            if text:
                return value

    return ""


# ============================================================
# IMAGE HANDLING
# ============================================================

def get_vehicle_image(raw):
    """
    IMPORTANT:

    The current project uses downloaded local images.

    If the Image column exists, it is preferred.

    This prevents the old broken Hearst image URLs
    from being used for the 32 failed vehicles.

    Example:

        /static/images/2026_Toyota_Camry.avif

    If Image is empty, the vehicle simply has no image.

    Image URL is only used as a fallback when the Image
    column does not exist at all.
    """

    keys = set()

    try:
        keys = set(
            raw.keys()
        )
    except Exception:
        pass

    # --------------------------------------------------------
    # CURRENT LOCAL IMAGE COLUMN
    # --------------------------------------------------------

    if "Image" in keys:

        local_image = clean_text(
            raw["Image"]
        )

        if local_image:

            if local_image.startswith(
                "/static/"
            ):
                return local_image

            # Handle paths such as:
            # static/images/car.avif

            if local_image.startswith(
                "static/"
            ):
                return "/" + local_image

            # Handle filename only

            if not (
                local_image.startswith(
                    "http://"
                )
                or
                local_image.startswith(
                    "https://"
                )
            ):

                return (
                    "/static/images/"
                    + local_image
                )

            return local_image

        # Image column exists but is empty.
        # Do NOT fall back to broken old URLs.

        return ""

    # --------------------------------------------------------
    # OLD DATABASE FALLBACK
    # --------------------------------------------------------

    for column in [
        "Image URL",
        "Image URL(s)",
        "Photo URL",
        "Thumbnail",
        "Photo"
    ]:

        if column not in keys:
            continue

        value = clean_text(
            raw[column]
        )

        if value:
            return value

    return ""


# ============================================================
# DATABASE ROW -> WEBSITE CAR
# ============================================================

def row_to_car(row):
    """
    Convert one SQLite vehicle row into the JSON structure
    used by the MotorNation frontend.
    """

    raw = {}

    try:

        raw = dict(
            row
        )

    except Exception:

        raw = {}

        try:

            for key in row.keys():

                raw[key] = row[key]

        except Exception:
            pass

    # --------------------------------------------------------
    # BASIC DATA
    # --------------------------------------------------------

    vehicle_id = raw.get(
        "vehicle_id"
    )

    if vehicle_id is None:

        vehicle_id = raw.get(
            "id"
        )

    year = clean_text(
        first_value(
            raw,
            "Year"
        )
    )

    make = clean_text(
        first_value(
            raw,
            "Make"
        )
    )

    model = clean_text(
        first_value(
            raw,
            "Model / Model Group",
            "Model"
        )
    )

    trim = clean_text(
        first_value(
            raw,
            "Trim / Variant",
            "Trim"
        )
    )

    body_type = clean_text(
        first_value(
            raw,
            "Body Type",
            "BodyType"
        )
    )

    fuel_type_raw = clean_text(
        first_value(
            raw,
            "Fuel Type",
            "FuelType"
        )
    )

    # --------------------------------------------------------
    # FUEL TYPES
    # --------------------------------------------------------

    fuel_types = clean_list(
        fuel_type_raw
    )

    if not fuel_types and fuel_type_raw:

        fuel_types = [
            fuel_type_raw
        ]

    # --------------------------------------------------------
    # PRICE
    # --------------------------------------------------------

    msrp = clean_number(
        first_value(
            raw,
            "MSRP",
            "Price",
            "price_msrp"
        )
    )

    # --------------------------------------------------------
    # PERFORMANCE
    # --------------------------------------------------------

    horsepower = clean_number(
        first_value(
            raw,
            "Horsepower"
        )
    )

    torque = clean_number(
        first_value(
            raw,
            "Torque"
        )
    )

    # --------------------------------------------------------
    # ENGINE
    # --------------------------------------------------------

    engine = clean_text(
        first_value(
            raw,
            "Engine"
        )
    )

    displacement = clean_text(
        first_value(
            raw,
            "Displacement"
        )
    )

    cylinders = clean_text(
        first_value(
            raw,
            "Cylinders"
        )
    )

    transmission = clean_text(
        first_value(
            raw,
            "Transmission"
        )
    )

    drivetrain = clean_text(
        first_value(
            raw,
            "Drivetrain"
        )
    )

    # --------------------------------------------------------
    # ECONOMY
    # --------------------------------------------------------

    mpg = clean_text(
        first_value(
            raw,
            "MPG"
        )
    )

    mpg_city = clean_text(
        first_value(
            raw,
            "MPG City"
        )
    )

    mpg_highway = clean_text(
        first_value(
            raw,
            "MPG Highway"
        )
    )

    ev_range = clean_text(
        first_value(
            raw,
            "EV range",
            "EV Range"
        )
    )

    battery = clean_text(
        first_value(
            raw,
            "Battery"
        )
    )

    # --------------------------------------------------------
    # PRACTICALITY
    # --------------------------------------------------------

    seating = clean_number(
        first_value(
            raw,
            "Seating"
        )
    )

    cargo = clean_number(
        first_value(
            raw,
            "Cargo"
        )
    )

    towing = clean_number(
        first_value(
            raw,
            "Towing"
        )
    )

    # --------------------------------------------------------
    # REVIEW
    # --------------------------------------------------------

    rating = clean_text(
        first_value(
            raw,
            "C&D Rating",
            "Rating"
        )
    )

    pros = clean_list(
        first_value(
            raw,
            "Pros (Highs)",
            "Pros"
        )
    )

    cons = clean_list(
        first_value(
            raw,
            "Cons (Lows)",
            "Cons"
        )
    )

    description = clean_text(
        first_value(
            raw,
            "Description",
            "Review Summary / Verdict"
        )
    )

    final_word = clean_text(
        first_value(
            raw,
            "Final Word",
            "Review Summary / Verdict"
        )
    )

    review_summary = clean_text(
        first_value(
            raw,
            "Review Summary / Verdict",
            "Final Word"
        )
    )

    review_url = clean_text(
        first_value(
            raw,
            "Review URL"
        )
    )

    cd_source = clean_text(
        first_value(
            raw,
            "C&D source",
            "C&D Source"
        )
    )

    # --------------------------------------------------------
    # NEWSROOM & ROAD TEST REVIEW DATA
    # --------------------------------------------------------

    nr_data = get_news_and_reviews()
    nr_item = (
        nr_data.get("by_id", {}).get(str(vehicle_id))
        or nr_data.get("by_key", {}).get(f"{make}_{model}".lower())
        or {}
    )

    news_headline = (
        clean_text(first_value(raw, "news_headline", "News Article Headline"))
        or nr_item.get("headline", "")
    )
    news_article = (
        clean_text(first_value(raw, "news_article", "Full News Article (Journalistic Coverage)"))
        or nr_item.get("article", "")
    )
    road_test_review = (
        clean_text(first_value(raw, "road_test_review", "In-Depth Road Test Review (5-6 Lines)"))
        or nr_item.get("review", "")
    )
    oem_newsroom_url = (
        clean_text(first_value(raw, "oem_newsroom_url", "Official OEM Newsroom URL"))
        or nr_item.get("oem_url", "")
    )
    review_lines = nr_item.get("review_lines", [])
    if not review_lines and road_test_review:
        review_lines = [l.strip() for l in road_test_review.split("\n") if l.strip()]

    video_title = clean_text(first_value(raw, "video_title", "youtube_video_title")) or nr_item.get("video_title", "")
    video_url = clean_text(first_value(raw, "video_url", "youtube_video_link")) or nr_item.get("video_url", "")
    video_id = clean_text(first_value(raw, "video_id", "youtube_video_id")) or nr_item.get("video_id", "")

    if not rating and nr_item.get("rating"):
        rating = nr_item.get("rating")

    if not pros and nr_item.get("pros"):
        pros = nr_item.get("pros")

    if not cons and nr_item.get("cons"):
        cons = nr_item.get("cons")

    # --------------------------------------------------------
    # IMAGE & GALLERY
    # --------------------------------------------------------

    image = get_vehicle_image(
        raw
    )

    gallery = get_vehicle_gallery(
        vehicle_id,
        make,
        model
    )

    images = []

    if gallery:
        images = [
            item["url"]
            for item in gallery
            if isinstance(item, dict) and item.get("url")
        ]

    if not images and image:
        images = [
            image
        ]

    if not image and images:
        image = images[0]

    # --------------------------------------------------------
    # RETURN FRONTEND OBJECT
    # --------------------------------------------------------

    car = {

        "id": vehicle_id,

        "vehicle_id": vehicle_id,

        "year": year,

        "make": make,

        "model": model,

        "trim": trim,

        "bodyType": body_type,

        "body_type": body_type,

        "fuelType": fuel_type_raw,

        "fuel_type": fuel_type_raw,

        "fuelTypes": fuel_types,

        "msrp": msrp,

        "price": {
            "msrp": msrp
        },

        "horsepower": horsepower,

        "torque": torque,

        "engine": engine,

        "displacement": displacement,

        "cylinders": cylinders,

        "transmission": transmission,

        "drivetrain": drivetrain,

        "mpg": mpg,

        "mpgCity": mpg_city,

        "mpgHighway": mpg_highway,

        "evRange": ev_range,

        "battery": battery,

        "seating": seating,

        "cargo": cargo,

        "towing": towing,

        "rating": rating,

        "pros": pros,

        "cons": cons,

        "prosText": ", ".join(
            pros
        ),

        "consText": ", ".join(
            cons
        ),

        "description": description,

        "finalWord": final_word,

        "reviewSummary": review_summary,

        "reviewUrl": review_url,

        "cdSource": cd_source,

        "newsHeadline": news_headline,

        "newsArticle": news_article,

        "roadTestReview": road_test_review,

        "roadTestReviewLines": review_lines,

        "oemNewsroomUrl": oem_newsroom_url,

        "image": image,

        "images": images,

        "gallery": gallery,

        "video_title": video_title,

        "video_url": video_url,

        "video_id": video_id,

        "videoTitle": video_title,

        "videoUrl": video_url,

        "videoId": video_id,

        "sourceData": raw
    }

    return car


# ============================================================
# FIND ONE VEHICLE
# ============================================================

def find_car_by_id(car_id):

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT rowid, *
        FROM vehicles
        WHERE vehicle_id = ?
           OR rowid = ?
        LIMIT 1
        """,
        (
            car_id,
            car_id
        )
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return row_to_car(
        row
    )


_CAR_VIDEOS_CACHE = None

def get_car_videos_map():
    """
    Load and cache the official 455-car YouTube video mapping.
    """
    global _CAR_VIDEOS_CACHE
    if _CAR_VIDEOS_CACHE is not None:
        return _CAR_VIDEOS_CACHE

    mapping_file = BASE_DIR / "data" / "car_videos_mapping.json"
    if mapping_file.exists():
        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                _CAR_VIDEOS_CACHE = json.load(f)
                return _CAR_VIDEOS_CACHE
        except Exception as e:
            app.logger.warning(f"Error loading car_videos_mapping.json: {e}")

    _CAR_VIDEOS_CACHE = {}
    return _CAR_VIDEOS_CACHE


def get_motornation_video_for_car(car):
    """
    Select the official video from @motornationofficial specified for each car
    from the curated 455-vehicle dataset.
    """
    if not car:
        return {
            "video_id": "Z0I64NzsFNQ",
            "title": "2025 Toyota Corolla vs 2025 Honda Civic Compared | Sedans Clash! — @motornationofficial",
            "url": "https://www.youtube.com/watch?v=Z0I64NzsFNQ",
            "car_name": "MotorNation Vehicle Review"
        }

    # 1. If car already has non-empty video fields
    if car.get("video_id") and car.get("video_title"):
        return {
            "video_id": car.get("video_id"),
            "title": car.get("video_title"),
            "url": car.get("video_url") or f"https://www.youtube.com/watch?v={car.get('video_id')}",
            "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
        }

    # 2. Check JSON mapping by vehicle ID (1..455)
    vid_map = get_car_videos_map()
    car_id_str = str(car.get("vehicle_id") or car.get("id") or "")
    if car_id_str and car_id_str in vid_map:
        info = vid_map[car_id_str]
        return {
            "video_id": info.get("video_id") or "Z0I64NzsFNQ",
            "title": info.get("title") or "MotorNation Video Review",
            "url": info.get("url") or f"https://www.youtube.com/watch?v={info.get('video_id', 'Z0I64NzsFNQ')}",
            "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
        }

    # 3. Match by make and model
    make_clean = (car.get("make") or "").strip().lower()
    model_clean = (car.get("model") or "").strip().lower()
    for item in vid_map.values():
        if (item.get("make") or "").lower() == make_clean and (item.get("model") or "").lower() == model_clean:
            return {
                "video_id": item.get("video_id") or "Z0I64NzsFNQ",
                "title": item.get("title") or "MotorNation Video Review",
                "url": item.get("url") or f"https://www.youtube.com/watch?v={item.get('video_id', 'Z0I64NzsFNQ')}",
                "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
            }

    # Default fallback
    return {
        "video_id": "Z0I64NzsFNQ",
        "title": "2025 Toyota Corolla vs 2025 Honda Civic Compared | Sedans Clash! — @motornationofficial",
        "url": "https://www.youtube.com/watch?v=Z0I64NzsFNQ",
        "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
    }


def find_rivals_for_car(car, limit=3):
    """
    Find authentic competitor/rival vehicles with same segment,
    prioritizing different manufacturer and similar price class.
    """
    try:
        body_type = (car.get("bodyType") or car.get("body_type") or "").strip()
        vehicle_id = car.get("vehicle_id") or car.get("id") or 0
        current_make = (car.get("make") or "").strip()
        msrp_val = None
        try:
            msrp_val = float(car.get("msrp") or (car.get("price") or {}).get("msrp") or 0)
        except (ValueError, TypeError):
            pass

        bt_lower = body_type.lower()
        where_body = "1=1"
        params_body = []
        if any(w in bt_lower for w in ["truck", "pickup"]):
            where_body = "([Body Type] LIKE ? OR [Body Type] LIKE ?)"
            params_body = ["%truck%", "%pickup%"]
        elif any(w in bt_lower for w in ["3-row", "three-row"]):
            where_body = "([Body Type] LIKE ? OR [Body Type] LIKE ?)"
            params_body = ["%3-row%", "%three-row%"]
        elif any(w in bt_lower for w in ["sedan", "hatch", "liftback", "fastback"]):
            where_body = "([Body Type] LIKE ? OR [Body Type] LIKE ? OR [Body Type] LIKE ?)"
            params_body = ["%sedan%", "%hatch%", "%liftback%"]
        elif any(w in bt_lower for w in ["coupe", "convertible", "sports car", "supercar", "hypercar"]):
            where_body = "([Body Type] LIKE ? OR [Body Type] LIKE ? OR [Body Type] LIKE ? OR [Body Type] LIKE ?)"
            params_body = ["%coupe%", "%convertible%", "%supercar%", "%sports car%"]
        elif any(w in bt_lower for w in ["suv", "crossover"]):
            where_body = "([Body Type] LIKE ? OR [Body Type] LIKE ?)"
            params_body = ["%suv%", "%crossover%"]
        elif any(w in bt_lower for w in ["minivan", "van"]):
            where_body = "([Body Type] LIKE ? OR [Body Type] LIKE ?)"
            params_body = ["%van%", "%minivan%"]

        connection = get_db()
        cursor = connection.cursor()

        # Step 1: Matching segment, different brand, closest MSRP
        query = f"""
            SELECT rowid, * FROM vehicles
            WHERE rowid != ? AND vehicle_id != ? AND Make != ?
              AND {where_body}
            ORDER BY ABS(CAST(REPLACE(REPLACE(MSRP, '$', ''), ',', '') AS REAL) - ?) ASC
            LIMIT ?
        """
        params = [vehicle_id, vehicle_id, current_make] + params_body + [msrp_val or 40000, limit]
        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Step 2: Fallback if fewer than limit
        if len(rows) < limit:
            needed = limit - len(rows)
            existing_ids = [r[0] for r in rows] + [vehicle_id]
            placeholders = ",".join("?" for _ in existing_ids)
            fallback_query = f"""
                SELECT rowid, * FROM vehicles
                WHERE rowid NOT IN ({placeholders}) AND Make != ?
                ORDER BY ABS(CAST(REPLACE(REPLACE(MSRP, '$', ''), ',', '') AS REAL) - ?) ASC
                LIMIT ?
            """
            cursor.execute(fallback_query, (*existing_ids, current_make, msrp_val or 40000, needed))
            rows.extend(cursor.fetchall())

        connection.close()
        return [row_to_car(r) for r in rows]

    except Exception as e:
        app.logger.warning("Error fetching rivals: %s", e)
        return []


# ============================================================
# HOME
# ============================================================

@app.route(
    "/",
    endpoint="home"
)
def index():

    return render_template(
        "index.html"
    )


# ============================================================
# CARS PAGE
# ============================================================

@app.route(
    "/cars"
)
def cars():

    return render_template(
        "cars.html"
    )


# ============================================================
# CAR DETAILS
# ============================================================

@app.route(
    "/car/<int:car_id>"
)
def car_details(car_id):

    car = find_car_by_id(
        car_id
    )

    if car is None:
        return "Vehicle not found", 404

    trims, msrp_range_str, min_m, max_m = get_trims_and_range_for_car(car)
    rivals = find_rivals_for_car(car, limit=3)
    video_info = get_motornation_video_for_car(car)

    return render_template(
        "car-details.html",
        car=car,
        vehicle=car,
        car_id=car_id,
        trims=trims,
        msrp_range_str=msrp_range_str,
        msrp_min=min_m,
        msrp_max=max_m,
        rivals=rivals,
        video_info=video_info
    )


# ============================================================
# COMPARE
# ============================================================

@app.route(
    "/compare"
)
def compare():

    return render_template(
        "compare.html"
    )


# ============================================================
# REVIEWS
# ============================================================

@app.route(
    "/reviews"
)
def reviews():

    nr_data = get_news_and_reviews()
    items = nr_data.get("items", [])
    brands = sorted(list(set(item["make"] for item in items if item.get("make"))))
    featured = items[0] if items else None

    return render_template(
        "reviews.html",
        reviews=items[:24],
        featured=featured,
        brands=brands,
        total_count=len(items)
    )


@app.route(
    "/api/reviews"
)
def api_reviews():

    query = request.args.get("q", "").strip().lower()
    make = request.args.get("make", "").strip().lower()
    min_rating = request.args.get("rating", "").strip()
    limit = request.args.get("limit", "24").strip()
    offset = int(request.args.get("offset", "0"))

    nr_data = get_news_and_reviews()
    items = nr_data.get("items", [])

    results = []
    for item in items:
        if make and item.get("make", "").lower() != make:
            continue
        if min_rating:
            try:
                r_val = float(str(item.get("rating", "0")).split("/")[0])
                if r_val < float(min_rating):
                    continue
            except (ValueError, IndexError):
                pass
        if query:
            match_txt = f"{item.get('make', '')} {item.get('model', '')} {item.get('trim', '')} {item.get('review', '')} {' '.join(item.get('pros', []))} {' '.join(item.get('cons', []))}".lower()
            if query not in match_txt:
                continue
        results.append(item)

    total_matched = len(results)
    if limit and limit.isdigit() and int(limit) > 0:
        paged_results = results[offset : offset + int(limit)]
    else:
        paged_results = results[offset:]

    return jsonify({
        "count": len(paged_results),
        "total": total_matched,
        "offset": offset,
        "has_more": (offset + len(paged_results)) < total_matched,
        "reviews": paged_results
    })


# ============================================================
# NEWS
# ============================================================

@app.route(
    "/news"
)
def news():

    nr_data = get_news_and_reviews()
    items = nr_data.get("items", [])
    brands = sorted(list(set(item["make"] for item in items if item.get("make"))))
    featured = items[0] if items else None

    return render_template(
        "news.html",
        news_items=items[:24],
        featured=featured,
        brands=brands,
        total_count=len(items)
    )


@app.route(
    "/api/news"
)
def api_news():

    query = request.args.get("q", "").strip().lower()
    make = request.args.get("make", "").strip().lower()
    body_type = request.args.get("bodyType", "").strip().lower()
    limit = request.args.get("limit", "24").strip()
    offset = int(request.args.get("offset", "0"))

    nr_data = get_news_and_reviews()
    items = nr_data.get("items", [])

    results = []
    for item in items:
        if make and item.get("make", "").lower() != make:
            continue
        if body_type and item.get("body_type", "").lower() != body_type:
            continue
        if query:
            match_txt = f"{item.get('make', '')} {item.get('model', '')} {item.get('headline', '')} {item.get('article', '')}".lower()
            if query not in match_txt:
                continue
        results.append(item)

    total_matched = len(results)
    if limit and limit.isdigit() and int(limit) > 0:
        paged_results = results[offset : offset + int(limit)]
    else:
        paged_results = results[offset:]

    return jsonify({
        "count": len(paged_results),
        "total": total_matched,
        "offset": offset,
        "has_more": (offset + len(paged_results)) < total_matched,
        "news": paged_results
    })


@app.route(
    "/reviews/<int:car_id>"
)
@app.route(
    "/reviews/<path:car_slug>"
)
def review_detail(car_id=None, car_slug=None):

    car = None
    matched_review = None
    if car_id is not None:
        car = find_car_by_id(car_id)
    elif car_slug:
        if str(car_slug).isdigit():
            car = find_car_by_id(int(car_slug))
        else:
            slug_clean = str(car_slug).strip().lower()
            # 1. Match against API reviews slug
            for r in get_motornation_editorial_reviews():
                if r.get("slug", "").lower() == slug_clean:
                    matched_review = r
                    cname = (r.get("car_name") or "").lower()
                    for cid in range(1, 500):
                        c = find_car_by_id(cid)
                        if c and (c.get("make") or "").lower() in cname and (c.get("model") or "").lower() in cname:
                            car = c
                            break
                    break

            # 2. Match against DB cars
            if not car:
                for cid in range(1, 500):
                    c = find_car_by_id(cid)
                    if not c:
                        continue
                    approx = f"{c.get('year','')}-{c.get('make','')}-{c.get('model','')}".lower().replace(" ", "-")
                    if approx in slug_clean or slug_clean in approx:
                        car = c
                        break

            # 3. If still not in DB, but matched_review exists, synthesize car from review!
            if not car and matched_review:
                name_clean = matched_review.get("car_name", "").replace(" Review", "").strip()
                parts = name_clean.split(" ")
                year_val = matched_review.get("model_year") or (parts[0] if parts and parts[0].isdigit() else "2027")
                rest = parts[1:] if parts and parts[0].isdigit() else parts
                make_val = rest[0] if rest else "Vehicle"
                model_val = " ".join(rest[1:]) if len(rest) > 1 else (parts[1] if len(parts) > 1 else "Vehicle")
                car = {
                    "id": 0,
                    "vehicle_id": 0,
                    "year": year_val,
                    "make": make_val,
                    "model": model_val,
                    "trim": "",
                    "bodyType": "Ultra-Luxury Vehicle",
                    "fuelType": "Gasoline",
                    "msrp": None,
                    "image": matched_review.get("images", [""])[0] if matched_review.get("images") else "",
                    "images": matched_review.get("images", []),
                    "gallery": [{"url": u, "caption": f"{name_clean}"} for u in matched_review.get("images", [])]
                }

    if not car:
        return "Vehicle review not found", 404

    review = build_review_data(car)
    trims, msrp_range_str, min_m, max_m = get_trims_and_range_for_car(car)
    nr_data = get_news_and_reviews()
    nr_item = nr_data.get("by_id", {}).get(str(car.get('id', ''))) or nr_data.get("by_key", {}).get(f"{car.get('make','')}_{car.get('model','')}".lower()) or {}
    rivals = find_rivals_for_car(car, limit=3)
    video_info = get_motornation_video_for_car(car)

    return render_template(
        "review-detail.html",
        car=car,
        review=review,
        review_item=nr_item,
        trims=trims,
        msrp_range_str=msrp_range_str,
        rivals=rivals,
        video_info=video_info
    )


@app.route(
    "/news/<int:car_id>"
)
def news_detail(car_id):

    car = find_car_by_id(car_id)
    if not car:
        return "Vehicle news not found", 404

    nr_data = get_news_and_reviews()
    nr_item = nr_data.get("by_id", {}).get(str(car_id)) or nr_data.get("by_key", {}).get(f"{car.get('make','')}_{car.get('model','')}".lower()) or {}
    rivals = find_rivals_for_car(car, limit=3)
    video_info = get_motornation_video_for_car(car)

    return render_template(
        "news-detail.html",
        car=car,
        news_item=nr_item,
        rivals=rivals,
        video_info=video_info
    )


@app.route(
    "/api/reviews/<int:car_id>"
)
def api_review_item(car_id):

    car = find_car_by_id(car_id)
    if not car:
        return jsonify({"error": "Review not found"}), 404
    review = build_review_data(car)
    return jsonify(review)


@app.route(
    "/api/news/<int:car_id>"
)
def api_news_item(car_id):

    nr_data = get_news_and_reviews()
    item = nr_data.get("by_id", {}).get(str(car_id))
    if not item:
        return jsonify({"error": "Article not found"}), 404
    return jsonify(item)


# ============================================================
# API - ALL CARS
# ============================================================

@app.route(
    "/api/cars"
)
def api_cars():

    try:

        query = request.args.get(
            "q",
            ""
        ).strip()

        make = request.args.get(
            "make",
            ""
        ).strip()

        body_type = request.args.get(
            "bodyType",
            ""
        ).strip()

        fuel_type = request.args.get(
            "fuelType",
            ""
        ).strip()

        max_price = request.args.get(
            "maxPrice",
            ""
        ).strip()

        sort_value = request.args.get(
            "sort",
            ""
        ).strip()

        connection = get_db()

        cursor = connection.cursor()

        sql = """
            SELECT rowid, *
            FROM vehicles
            WHERE 1 = 1
        """

        parameters = []

        # ----------------------------------------------------
        # SEARCH
        # ----------------------------------------------------

        if query:

            sql += """
                AND (
                    LOWER(COALESCE("Make", ''))
                    LIKE LOWER(?)

                    OR

                    LOWER(
                        COALESCE(
                            "Model / Model Group",
                            ''
                        )
                    )
                    LIKE LOWER(?)

                    OR

                    LOWER(
                        COALESCE(
                            "Trim / Variant",
                            ''
                        )
                    )
                    LIKE LOWER(?)
                )
            """

            search_value = (
                "%"
                + query
                + "%"
            )

            parameters.extend([
                search_value,
                search_value,
                search_value
            ])

        # ----------------------------------------------------
        # MAKE
        # ----------------------------------------------------

        if make:

            sql += """
                AND LOWER(
                    COALESCE("Make", '')
                ) = LOWER(?)
            """

            parameters.append(
                make
            )

        # ----------------------------------------------------
        # BODY TYPE
        # ----------------------------------------------------

        if body_type:

            sql += """
                AND LOWER(
                    COALESCE("Body Type", '')
                ) = LOWER(?)
            """

            parameters.append(
                body_type
            )

        # ----------------------------------------------------
        # FUEL TYPE
        # ----------------------------------------------------

        if fuel_type:

            sql += """
                AND LOWER(
                    COALESCE("Fuel Type", '')
                ) LIKE LOWER(?)
            """

            parameters.append(
                "%"
                + fuel_type
                + "%"
            )

        # ----------------------------------------------------
        # MAX PRICE
        # ----------------------------------------------------

        if max_price:

            numeric_price = clean_number(
                max_price
            )

            if numeric_price > 0:

                sql += """
                    AND CAST(
                        REPLACE(
                            REPLACE(
                                REPLACE(
                                    COALESCE(
                                        "MSRP",
                                        '0'
                                    ),
                                    '$',
                                    ''
                                ),
                                ',',
                                ''
                            ),
                            'USD',
                            ''
                        )
                        AS REAL
                    ) <= ?
                """

                parameters.append(
                    numeric_price
                )

        # ----------------------------------------------------
        # SORT
        # ----------------------------------------------------

        if sort_value == "price-asc":

            sql += """
                ORDER BY
                    CAST(
                        REPLACE(
                            REPLACE(
                                COALESCE(
                                    "MSRP",
                                    '0'
                                ),
                                '$',
                                ''
                            ),
                            ',',
                            ''
                        )
                        AS REAL
                    ) ASC
            """

        elif sort_value == "price-desc":

            sql += """
                ORDER BY
                    CAST(
                        REPLACE(
                            REPLACE(
                                COALESCE(
                                    "MSRP",
                                    '0'
                                ),
                                '$',
                                ''
                            ),
                            ',',
                            ''
                        )
                        AS REAL
                    ) DESC
            """

        elif sort_value == "hp-desc":

            sql += """
                ORDER BY
                    CAST(
                        COALESCE(
                            "Horsepower",
                            '0'
                        )
                        AS REAL
                    ) DESC
            """

        elif sort_value == "year-desc":

            sql += """
                ORDER BY
                    CAST(
                        COALESCE(
                            "Year",
                            '0'
                        )
                        AS INTEGER
                    ) DESC
            """

        else:

            sql += """
                ORDER BY
                    CAST(
                        COALESCE(
                            "Year",
                            '0'
                        )
                        AS INTEGER
                    ) DESC,
                    "Make" COLLATE NOCASE,
                    "Model / Model Group"
                        COLLATE NOCASE,
                    "Trim / Variant"
                        COLLATE NOCASE
            """

        cursor.execute(
            sql,
            parameters
        )

        rows = cursor.fetchall()

        connection.close()

        cars_data = [
            row_to_car(row)
            for row in rows
        ]

        return jsonify({
            "count": len(
                cars_data
            ),
            "total": len(
                cars_data
            ),
            "cars": cars_data
        })

    except Exception as error:

        app.logger.exception(
            "Error loading vehicles."
        )

        return jsonify({
            "error": str(error),
            "cars": [],
            "count": 0
        }), 500


# ============================================================
# API - SINGLE CAR
# ============================================================

@app.route(
    "/api/cars/<int:car_id>"
)
def api_car(car_id):

    try:

        car = find_car_by_id(
            car_id
        )

        if car is None:

            return jsonify({
                "error":
                    "Vehicle not found"
            }), 404

        return jsonify(
            car
        )

    except Exception as error:

        app.logger.exception(
            "Error loading vehicle %s",
            car_id
        )

        return jsonify({
            "error": str(error)
        }), 500


# ============================================================
# API - SEARCH
# ============================================================

@app.route(
    "/api/cars/search"
)
def api_search():

    query = request.args.get(
        "q",
        ""
    ).strip()

    if not query:

        return jsonify({
            "query": "",
            "count": 0,
            "cars": []
        })

    connection = get_db()

    cursor = connection.cursor()

    search_value = (
        "%"
        + query
        + "%"
    )

    cursor.execute(
        """
        SELECT rowid, *
        FROM vehicles
        WHERE
            LOWER(
                COALESCE(
                    "Make",
                    ''
                )
            )
            LIKE LOWER(?)

            OR

            LOWER(
                COALESCE(
                    "Model / Model Group",
                    ''
                )
            )
            LIKE LOWER(?)

            OR

            LOWER(
                COALESCE(
                    "Trim / Variant",
                    ''
                )
            )
            LIKE LOWER(?)

        ORDER BY
            "Make" COLLATE NOCASE,
            "Model / Model Group"
                COLLATE NOCASE
        """,
        (
            search_value,
            search_value,
            search_value
        )
    )

    rows = cursor.fetchall()

    connection.close()

    results = [
        row_to_car(row)
        for row in rows
    ]

    return jsonify({
        "query": query,
        "count": len(
            results
        ),
        "cars": results
    })


# ============================================================
# API - MAKES
# ============================================================

@app.route(
    "/api/makes"
)
def api_makes():

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT DISTINCT
            "Make"
        FROM vehicles
        WHERE
            "Make" IS NOT NULL
            AND TRIM("Make") != ''
        ORDER BY
            "Make" COLLATE NOCASE
        """
    )

    rows = cursor.fetchall()

    connection.close()

    makes = [
        clean_text(
            row["Make"]
        )
        for row in rows
        if clean_text(
            row["Make"]
        )
    ]

    return jsonify({
        "count": len(
            makes
        ),
        "makes": makes
    })


# ============================================================
# API - MODELS
# ============================================================

@app.route(
    "/api/models"
)
def api_models():

    make = request.args.get(
        "make",
        ""
    ).strip()

    connection = get_db()

    cursor = connection.cursor()

    if make:

        cursor.execute(
            """
            SELECT DISTINCT
                "Model / Model Group"
            FROM vehicles
            WHERE
                LOWER(
                    COALESCE(
                        "Make",
                        ''
                    )
                )
                = LOWER(?)

                AND

                "Model / Model Group"
                    IS NOT NULL

                AND

                TRIM(
                    "Model / Model Group"
                ) != ''

            ORDER BY
                "Model / Model Group"
                COLLATE NOCASE
            """,
            (
                make,
            )
        )

    else:

        cursor.execute(
            """
            SELECT DISTINCT
                "Model / Model Group"
            FROM vehicles
            WHERE
                "Model / Model Group"
                    IS NOT NULL

                AND

                TRIM(
                    "Model / Model Group"
                ) != ''

            ORDER BY
                "Model / Model Group"
                COLLATE NOCASE
            """
        )

    rows = cursor.fetchall()

    connection.close()

    models = [
        clean_text(
            row["Model / Model Group"]
        )
        for row in rows
        if clean_text(
            row["Model / Model Group"]
        )
    ]

    return jsonify({
        "count": len(
            models
        ),
        "models": models
    })


# ============================================================
# API - DATASET INFORMATION
# ============================================================

@app.route(
    "/api/dataset"
)
def api_dataset():

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM vehicles
        """
    )

    vehicle_count = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(DISTINCT "Make")
        FROM vehicles
        WHERE
            "Make" IS NOT NULL
            AND TRIM("Make") != ''
        """
    )

    make_count = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM vehicles
        WHERE
            "Image" IS NOT NULL
            AND TRIM("Image") != ''
        """
    )

    local_image_count = (
        cursor.fetchone()[0]
    )

    connection.close()

    return jsonify({
        "dataset":
            "MotorNation Master Vehicle Database",

        "source":
            "MotorNation Master Excel Database",

        "vehicleCount":
            vehicle_count,

        "makeCount":
            make_count,

        "localImageCount":
            local_image_count,

        "database":
            str(DATABASE_FILE),

        "status":
            "database_connected",

        "scraping":
            False
    })


# ============================================================
# API - HEALTH
# ============================================================

@app.route(
    "/api/health"
)
def api_health():

    try:

        connection = get_db()

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM vehicles
            """
        )

        vehicle_count = (
            cursor.fetchone()[0]
        )

        connection.close()

        return jsonify({
            "status":
                "ok",

            "database":
                "connected",

            "vehicleCount":
                vehicle_count
        })

    except Exception as error:

        app.logger.exception(
            "Health check failed."
        )

        return jsonify({
            "status":
                "error",

            "database":
                "error",

            "message":
                str(error)
        }), 500


# ============================================================
# ADMIN AUTHENTICATION
# ============================================================

def admin_logged_in():

    return session.get(
        "admin_logged_in",
        False
    )


def admin_required():

    return admin_logged_in()


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route(
    "/admin/login",
    methods=[
        "GET",
        "POST"
    ]
)
def admin_login():

    if admin_logged_in():

        return redirect(
            url_for(
                "admin_dashboard"
            )
        )

    error = ""

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        if password == ADMIN_PASSWORD:

            session[
                "admin_logged_in"
            ] = True

            app.logger.info(
                "Admin login successful."
            )

            return redirect(
                url_for(
                    "admin_dashboard"
                )
            )

        error = (
            "Incorrect password."
        )

        app.logger.warning(
            "Failed admin login attempt."
        )

    return render_template(
        "admin-login.html",
        error=error
    )


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route(
    "/admin/logout"
)
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )

    return redirect(
        url_for(
            "admin_login"
        )
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route(
    "/admin"
)
def admin_dashboard():

    if not admin_required():

        return redirect(
            url_for(
                "admin_login"
            )
        )

    search = request.args.get(
        "q",
        ""
    ).strip()

    connection = get_db()

    cursor = connection.cursor()

    # --------------------------------------------------------
    # VEHICLE LIST
    # --------------------------------------------------------

    if search:

        search_value = (
            "%"
            + search
            + "%"
        )

        cursor.execute(
            """
            SELECT
                vehicle_id,
                "Year",
                "Make",
                "Model / Model Group",
                "Trim / Variant",
                "Body Type",
                "Fuel Type",
                "MSRP",
                "Horsepower"
            FROM vehicles
            WHERE
                LOWER(
                    COALESCE(
                        "Make",
                        ''
                    )
                )
                LIKE LOWER(?)

                OR

                LOWER(
                    COALESCE(
                        "Model / Model Group",
                        ''
                    )
                )
                LIKE LOWER(?)

                OR

                LOWER(
                    COALESCE(
                        "Trim / Variant",
                        ''
                    )
                )
                LIKE LOWER(?)

            ORDER BY
                "Make",
                "Model / Model Group"

            LIMIT 200
            """,
            (
                search_value,
                search_value,
                search_value
            )
        )

    else:

        cursor.execute(
            """
            SELECT
                vehicle_id,
                "Year",
                "Make",
                "Model / Model Group",
                "Trim / Variant",
                "Body Type",
                "Fuel Type",
                "MSRP",
                "Horsepower"
            FROM vehicles

            ORDER BY
                "Make",
                "Model / Model Group"

            LIMIT 200
            """
        )

    vehicles = cursor.fetchall()

    # --------------------------------------------------------
    # TOTAL VEHICLES
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM vehicles
        """
    )

    total_vehicles = (
        cursor.fetchone()[0]
    )

    # --------------------------------------------------------
    # TOTAL MAKES
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(
            DISTINCT "Make"
        )
        FROM vehicles
        WHERE
            "Make" IS NOT NULL
            AND TRIM("Make") != ''
        """
    )

    total_makes = (
        cursor.fetchone()[0]
    )

    # --------------------------------------------------------
    # ELECTRIC VEHICLES
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM vehicles
        WHERE
            LOWER(
                COALESCE(
                    "Fuel Type",
                    ''
                )
            )
            LIKE '%electric%'
        """
    )

    total_ev = (
        cursor.fetchone()[0]
    )

    # --------------------------------------------------------
    # LOCAL IMAGES
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM vehicles
        WHERE
            "Image" IS NOT NULL
            AND TRIM("Image") != ''
        """
    )

    vehicles_with_images = (
        cursor.fetchone()[0]
    )

    connection.close()

    return render_template(
        "admin.html",

        vehicles=vehicles,

        total_vehicles=
            total_vehicles,

        total_makes=
            total_makes,

        total_ev=
            total_ev,

        vehicles_with_images=
            vehicles_with_images,

        search=search
    )


# ============================================================
# ADMIN FORM FIELD MAPPING
# ============================================================

ADMIN_FIELD_MAP = {

    "Year":
        "year",

    "Make":
        "make",

    "Model / Model Group":
        "model",

    "Trim / Variant":
        "trim",

    "Body Type":
        "body_type",

    "Fuel Type":
        "fuel_type",

    "MSRP":
        "msrp",

    "Horsepower":
        "horsepower",

    "Torque":
        "torque",

    "Engine":
        "engine",

    "Displacement":
        "displacement",

    "Cylinders":
        "cylinders",

    "Transmission":
        "transmission",

    "Drivetrain":
        "drivetrain",

    "MPG":
        "mpg",

    "EV range":
        "ev_range",

    "Battery":
        "battery",

    "Seating":
        "seating",

    "Cargo":
        "cargo",

    "Towing":
        "towing",

    "C&D Rating":
        "rating",

    "Pros (Highs)":
        "pros",

    "Cons (Lows)":
        "cons",

    "Review Summary / Verdict":
        "final_word",

    "Review URL":
        "review_url",

    "C&D source":
        "cd_source",

    "Image":
        "image",

    "Description":
        "description"
}


# ============================================================
# READ ADMIN FORM
# ============================================================

def get_admin_form_values():

    values = {}

    form = request.form

    columns = get_vehicle_columns()

    for column in columns:

        field_name = (
            ADMIN_FIELD_MAP.get(
                column
            )
        )

        val = None
        if column in form:
            val = form.get(column)
        elif field_name and field_name in form:
            val = form.get(field_name)

        if val is None:
            continue

        value = str(val).strip()

        # Pros and cons are stored as
        # newline-separated text.

        if column in {
            "Pros (Highs)",
            "Cons (Lows)"
        }:

            items = clean_list(
                value
            )

            value = "\n".join(
                items
            )

        values[column] = value

    return values


# ============================================================
# ADMIN ADD VEHICLE
# ============================================================

@app.route(
    "/admin/add",
    methods=[
        "GET",
        "POST"
    ]
)
def admin_add_vehicle():

    if not admin_required():

        return redirect(
            url_for(
                "admin_login"
            )
        )

    error = ""

    if request.method == "POST":

        try:

            values = (
                get_admin_form_values()
            )

            if not values:

                raise ValueError(
                    "No vehicle fields were submitted."
                )

            connection = get_db()

            cursor = connection.cursor()

            insert_columns = []

            insert_values = []

            placeholders = []

            for column, value in values.items():

                insert_columns.append(
                    quote_column(
                        column
                    )
                )

                insert_values.append(
                    value
                )

                placeholders.append(
                    "?"
                )

            sql = f"""
                INSERT INTO vehicles
                (
                    {", ".join(
                        insert_columns
                    )}
                )
                VALUES
                (
                    {", ".join(
                        placeholders
                    )}
                )
            """

            cursor.execute(
                sql,
                insert_values
            )

            new_id = (
                cursor.lastrowid
            )

            connection.commit()

            connection.close()

            app.logger.info(
                "Admin added vehicle ID %s",
                new_id
            )

            return redirect(
                url_for(
                    "admin_dashboard"
                )
            )

        except Exception as error:

            error = str(
                error
            )

            app.logger.exception(
                "Failed to add vehicle."
            )

    return render_template(
        "admin-vehicle-form.html",
        mode="add",
        vehicle=None,
        columns=get_vehicle_columns(),
        error=error
    )


# ============================================================
# ADMIN EDIT VEHICLE
# ============================================================

@app.route(
    "/admin/edit/<int:vehicle_id>",
    methods=[
        "GET",
        "POST"
    ]
)
@app.route(
    "/admin/edit",
    methods=[
        "GET",
        "POST"
    ]
)
def admin_edit_vehicle(
    vehicle_id=None
):

    if not admin_required():

        return redirect(
            url_for(
                "admin_login"
            )
        )

    if vehicle_id is None:
        try:
            vehicle_id = int(request.args.get("vehicle_id") or request.args.get("car_id") or request.form.get("vehicle_id") or request.form.get("car_id") or 0)
        except (ValueError, TypeError):
            vehicle_id = 0

    if not vehicle_id:
        return redirect(
            url_for(
                "admin_dashboard"
            )
        )

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM vehicles
        WHERE vehicle_id = ?
        """,
        (
            vehicle_id,
        )
    )

    database_vehicle = (
        cursor.fetchone()
    )

    connection.close()

    if database_vehicle is None:

        return "Vehicle not found", 404

    error = ""

    if request.method == "POST":

        try:

            values = (
                get_admin_form_values()
            )

            if not values:

                raise ValueError(
                    "No vehicle fields were submitted."
                )

            connection = get_db()

            cursor = connection.cursor()

            assignments = []

            update_values = []

            for column, value in values.items():

                assignments.append(
                    f"{quote_column(column)} = ?"
                )

                update_values.append(
                    value
                )

            update_values.append(
                vehicle_id
            )

            sql = f"""
                UPDATE vehicles
                SET
                    {", ".join(
                        assignments
                    )}
                WHERE vehicle_id = ?
            """

            cursor.execute(
                sql,
                update_values
            )

            connection.commit()

            connection.close()

            app.logger.info(
                "Admin edited vehicle ID %s",
                vehicle_id
            )

            return redirect(
                url_for(
                    "admin_dashboard"
                )
            )

        except Exception as exc:

            error = str(
                exc
            )

            app.logger.exception(
                "Failed to edit vehicle ID %s",
                vehicle_id
            )

    # Convert DB row into the same
    # object used by the public website.

    vehicle = row_to_car(
        database_vehicle
    )

    return render_template(
        "admin-vehicle-form.html",

        mode="edit",

        vehicle=vehicle,

        columns=
            get_vehicle_columns(),

        error=error
    )


# ============================================================
# ADMIN DELETE VEHICLE
# ============================================================

@app.route(
    "/admin/delete/<int:vehicle_id>",
    methods=[
        "POST"
    ]
)
def admin_delete_vehicle(
    vehicle_id
):

    if not admin_required():

        return redirect(
            url_for(
                "admin_login"
            )
        )

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM vehicles
        WHERE vehicle_id = ?
        """,
        (
            vehicle_id,
        )
    )

    deleted = (
        cursor.rowcount
    )

    connection.commit()

    connection.close()

    if deleted:

        app.logger.info(
            "Admin deleted vehicle ID %s",
            vehicle_id
        )

    else:

        app.logger.warning(
            "Delete requested for missing vehicle ID %s",
            vehicle_id
        )

    return redirect(
        url_for(
            "admin_dashboard"
        )
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):

    try:

        return render_template(
            "404.html"
        ), 404

    except Exception:

        return (
            "404 - Page not found",
            404
        )


@app.errorhandler(500)
def internal_error(error):

    app.logger.exception(
        "Internal server error."
    )

    try:

        return render_template(
            "500.html"
        ), 500

    except Exception:

        return (
            "500 - Internal server error",
            500
        )


# ============================================================
# STARTUP
# ============================================================

if __name__ == "__main__":

    ensure_database_structure()

    app.logger.info(
        "========================================"
    )

    app.logger.info(
        "MotorNation starting"
    )

    app.logger.info(
        "Database: %s",
        DATABASE_FILE
    )

    app.logger.info(
        "Images: %s",
        IMAGE_DIR
    )

    app.logger.info(
        "========================================"
    )

    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    app.run(
        host=host,
        port=port,
        debug=debug
    )
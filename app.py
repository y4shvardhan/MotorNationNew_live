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


def get_motornation_video_for_car(car):
    """
    Select an authentic, directly-playable video from @motornationofficial
    matching the vehicle's make, model, or body category.
    """
    make = (car.get("make") or "").strip().lower()
    model = (car.get("model") or "").strip().lower()
    body = (car.get("bodyType") or car.get("body_type") or "").strip().lower()

    # Trucks & Pickups
    if any(w in model for w in ["tundra", "tacoma", "silverado", "f-150", "ram", "colorado", "ranger", "frontier", "sierra"]) or any(w in body for w in ["truck", "pickup"]):
        return {
            "video_id": "FCxwMVjtb6w",
            "title": "2026 Pickups & Trucks In-Depth Evaluation — @motornationofficial",
            "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
        }

    # BMW Models
    if "bmw" in make:
        if any(w in model for w in ["ix3", "ix", "ix5", "i4", "i5", "i7"]) or "electric" in body or "ev" in body:
            return {
                "video_id": "zvvPLCMGW1c",
                "title": "2027 BMW iX3 & Next-Gen EV In-Depth Review — @motornationofficial",
                "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
            }
        elif "x1" in model:
            return {
                "video_id": "D-CbzfvCbRc",
                "title": "2027 BMW X1 vs Lexus NX Luxury Compact Showdown — @motornationofficial",
                "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
            }
        elif any(w in model for w in ["3 series", "4 series", "5 series", "7 series", "m3", "m4", "m5", "m2", "coupe", "sedan"]):
            return {
                "video_id": "XT-yh0I2f4A",
                "title": "2027 BMW 3 Series & Sports Sedan Evaluation — @motornationofficial",
                "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
            }
        else:
            return {
                "video_id": "M0q3Fdn3tFo",
                "title": "Why The BMW X5 & Luxury SUV Lineup Dominates — @motornationofficial",
                "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
            }

    # Mercedes-Benz
    if "mercedes" in make:
        if any(w in model for w in ["glc", "c-class", "cle", "cla"]):
            return {
                "video_id": "YWvvbp5ez_4",
                "title": "2027 Mercedes GLC 350e vs Lexus RX: Battle of Luxury & Power — @motornationofficial",
                "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
            }
        else:
            return {
                "video_id": "jEoFC8FV2Ac",
                "title": "2027 Mercedes-Benz GLE Luxury SUV In-Depth Analysis — @motornationofficial",
                "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
            }

    # Lexus & Toyota
    if "lexus" in make or "toyota" in make:
        if any(w in model for w in ["gx", "land cruiser", "4runner"]) or "off-road" in body:
            return {
                "video_id": "PXrSMv94PLU",
                "title": "2027 Lexus GX550 vs Range Rover Sport: Luxury & Off-Road — @motornationofficial",
                "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
            }
        elif any(w in model for w in ["lx", "sequoia"]):
            return {
                "video_id": "o4SzS-_A1wQ",
                "title": "2027 Lexus LX vs Range Rover: Ultimate Luxury Showdown — @motornationofficial",
                "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
            }
        elif "nx" in model:
            return {
                "video_id": "Badyqn3s7mw",
                "title": "2027 Lexus NX vs Mercedes-Benz GLC: Which Luxury SUV to Buy? — @motornationofficial",
                "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
            }
        elif any(w in model for w in ["tx", "grand highlander", "highlander"]) or "3-row" in body:
            return {
                "video_id": "sFEhGY-6zJY",
                "title": "2027 Lexus RX vs 2027 Lexus TX 3-Row Family Comparison — @motornationofficial",
                "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
            }
        else:
            return {
                "video_id": "64gmXwhVmuw",
                "title": "Why the Lexus RX & Premium Japanese Lineup is the Best-Seller — @motornationofficial",
                "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
            }

    # Mazda
    if "mazda" in make:
        return {
            "video_id": "MTg2UxKEq9A",
            "title": "2027 Mazda CX-60 / CX-90 vs Luxury Rivals Comparison — @motornationofficial",
            "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
        }

    # Land Rover / Range Rover
    if "rover" in make or "land rover" in make:
        return {
            "video_id": "iC1UHDnthBo",
            "title": "Range Rover Sport vs BMW X5 vs Mercedes GLE Showdown — @motornationofficial",
            "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
        }

    # Sedans, Coupes & Sports Cars
    if any(w in body for w in ["sedan", "coupe", "hatch", "liftback", "fastback", "sports car", "supercar", "hypercar", "roadster"]):
        return {
            "video_id": "XT-yh0I2f4A",
            "title": "Performance, Handling & Cabin Tech Road Test — @motornationofficial",
            "car_name": f"{car.get('year', '2026')} {car.get('make', '')} {car.get('model', '')}"
        }

    # Default luxury and benchmark comparison video
    return {
        "video_id": "iC1UHDnthBo",
        "title": "2027 Luxury & Performance Benchmark Comparison — @motornationofficial",
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

    rivals = find_rivals_for_car(car, limit=3)
    video_info = get_motornation_video_for_car(car)

    return render_template(
        "car-details.html",
        car=car,
        vehicle=car,
        car_id=car_id,
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
def review_detail(car_id):

    car = find_car_by_id(car_id)
    if not car:
        return "Vehicle review not found", 404

    nr_data = get_news_and_reviews()
    nr_item = nr_data.get("by_id", {}).get(str(car_id)) or nr_data.get("by_key", {}).get(f"{car.get('make','')}_{car.get('model','')}".lower()) or {}
    rivals = find_rivals_for_car(car, limit=3)
    video_info = get_motornation_video_for_car(car)

    return render_template(
        "review-detail.html",
        car=car,
        review_item=nr_item,
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

    nr_data = get_news_and_reviews()
    item = nr_data.get("by_id", {}).get(str(car_id))
    if not item:
        return jsonify({"error": "Review not found"}), 404
    return jsonify(item)


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

        if not field_name:
            continue

        if field_name not in form:
            continue

        value = form.get(
            field_name,
            ""
        )

        value = value.strip()

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
def admin_edit_vehicle(
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
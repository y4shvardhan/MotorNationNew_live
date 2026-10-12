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

DATABASE_DIR.mkdir(
    parents=True,
    exist_ok=True
)

IMAGE_DIR.mkdir(
    parents=True,
    exist_ok=True
)

_cached_galleries = None


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


def find_rivals_for_car(car, limit=3):
    """
    Find competitor/rival vehicles with same body type or category.
    """
    try:
        body_type = car.get("bodyType") or car.get("body_type") or ""
        vehicle_id = car.get("vehicle_id") or car.get("id") or 0

        connection = get_db()
        cursor = connection.cursor()

        if body_type:
            cursor.execute(
                """
                SELECT rowid, *
                FROM vehicles
                WHERE ("Body Type" = ? OR "Body" = ?)
                  AND rowid != ?
                  AND vehicle_id != ?
                ORDER BY RANDOM()
                LIMIT ?
                """,
                (body_type, body_type, vehicle_id, vehicle_id, limit)
            )
        else:
            cursor.execute(
                """
                SELECT rowid, *
                FROM vehicles
                WHERE rowid != ? AND vehicle_id != ?
                ORDER BY RANDOM()
                LIMIT ?
                """,
                (vehicle_id, vehicle_id, limit)
            )

        rows = cursor.fetchall()
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

    return render_template(
        "car-details.html",
        car=car,
        vehicle=car,
        car_id=car_id,
        rivals=rivals
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

    return render_template(
        "reviews.html"
    )


# ============================================================
# NEWS
# ============================================================

@app.route(
    "/news"
)
def news():

    return render_template(
        "news.html"
    )


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
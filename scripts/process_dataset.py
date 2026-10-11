from pathlib import Path
import csv
import json
from datetime import datetime


# ============================================================
# MotorNation - 2026 Vehicle Dataset Processor
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "vehicles_raw.csv"
)

PROCESSED_CSV = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "vehicles_2026.csv"
)

EXPORT_JSON = (
    PROJECT_ROOT
    / "data"
    / "exports"
    / "vehicles_2026.json"
)


# ============================================================
# CSV fields
# ============================================================

NUMERIC_FIELDS = {
    "year",
    "engine_cylinders",
    "horsepower",
    "torque",
    "msrp",
    "destination_charge",
    "mpg_city",
    "mpg_highway",
    "mpg_combined",
    "ev_range",
    "plug_in_range",
    "seating",
    "cargo_capacity",
    "length",
    "width",
    "height",
    "wheelbase",
    "curb_weight",
    "towing_capacity",
}


# ============================================================
# Helper functions
# ============================================================

def clean_text(value):
    """Clean a text value."""
    if value is None:
        return ""

    return str(value).strip()


def convert_value(field, value):
    """
    Convert CSV values into appropriate Python types.
    Empty values become None.
    """

    value = clean_text(value)

    if value == "":
        return None

    if field in NUMERIC_FIELDS:

        if field == "year":
            return int(float(value))

        if field == "engine_cylinders":
            return int(float(value))

        if field == "seating":
            return int(float(value))

        return float(value)

    return value


def normalize_vehicle(row):
    """
    Convert one CSV row into a clean vehicle dictionary.
    """

    vehicle = {}

    for field, value in row.items():
        vehicle[field] = convert_value(field, value)

    return vehicle


# ============================================================
# Create website-friendly record
# ============================================================

def create_website_record(vehicle):
    """
    Create a normalized structure that can later be used
    directly by the MotorNation Flask application.
    """

    return {
        "id": vehicle.get("id"),
        "year": vehicle.get("year"),

        "make": vehicle.get("make"),
        "model": vehicle.get("model"),
        "trim": vehicle.get("trim"),
        "variant": vehicle.get("variant"),

        "bodyType": vehicle.get("body_type"),
        "vehicleType": vehicle.get("vehicle_type"),
        "fuelType": vehicle.get("fuel_type"),

        "price": vehicle.get("msrp"),

        "engine": vehicle.get("engine"),
        "engineDisplacement": vehicle.get(
            "engine_displacement"
        ),
        "engineCylinders": vehicle.get(
            "engine_cylinders"
        ),

        "horsepower": vehicle.get("horsepower"),
        "torque": vehicle.get("torque"),

        "transmission": vehicle.get("transmission"),
        "drivetrain": vehicle.get("drivetrain"),

        "destinationCharge": vehicle.get(
            "destination_charge"
        ),

        "mpg": {
            "city": vehicle.get("mpg_city"),
            "highway": vehicle.get("mpg_highway"),
            "combined": vehicle.get("mpg_combined"),
        },

        "evRange": vehicle.get("ev_range"),
        "plugInRange": vehicle.get(
            "plug_in_range"
        ),

        "seating": vehicle.get("seating"),
        "cargo": vehicle.get("cargo_capacity"),

        "dimensions": {
            "length": vehicle.get("length"),
            "width": vehicle.get("width"),
            "height": vehicle.get("height"),
            "wheelbase": vehicle.get("wheelbase"),
        },

        "curbWeight": vehicle.get("curb_weight"),
        "towingCapacity": vehicle.get(
            "towing_capacity"
        ),

        "description": vehicle.get(
            "description"
        ),

        "pros": vehicle.get("pros"),
        "cons": vehicle.get("cons"),

        "features": vehicle.get("features"),

        "image": vehicle.get("image_url"),

        "source": {
            "name": vehicle.get("source_name"),
            "url": vehicle.get("source_url"),
        },

        "lastUpdated": vehicle.get(
            "last_updated"
        ),
    }


# ============================================================
# Main processing function
# ============================================================

def process_dataset():

    print("=" * 70)
    print("MotorNation - 2026 Vehicle Dataset Processor")
    print("=" * 70)

    # --------------------------------------------------------
    # Check source file
    # --------------------------------------------------------

    print()
    print("Input file:")
    print(RAW_FILE)

    if not RAW_FILE.exists():
        print()
        print("ERROR: Raw dataset was not found.")
        return False

    # --------------------------------------------------------
    # Read raw CSV
    # --------------------------------------------------------

    try:
        with RAW_FILE.open(
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            reader = csv.DictReader(file)

            rows = list(reader)

    except Exception as exc:

        print()
        print("ERROR: Could not read raw CSV.")
        print(f"Reason: {exc}")

        return False

    if not rows:

        print()
        print("ERROR: Raw dataset contains no records.")

        return False

    print()
    print(f"Raw records found: {len(rows)}")

    # --------------------------------------------------------
    # Normalize records
    # --------------------------------------------------------

    vehicles = []

    for row in rows:

        vehicle = normalize_vehicle(row)

        vehicles.append(vehicle)

    print(
        f"Records normalized: {len(vehicles)}"
    )

    # --------------------------------------------------------
    # Create processed directory
    # --------------------------------------------------------

    PROCESSED_CSV.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    EXPORT_JSON.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Write processed CSV
    # --------------------------------------------------------

    with PROCESSED_CSV.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=rows[0].keys(),
            extrasaction="ignore"
        )

        writer.writeheader()

        for vehicle in vehicles:
            writer.writerow(vehicle)

    print()
    print("Processed CSV created:")
    print(PROCESSED_CSV)

    # --------------------------------------------------------
    # Create website records
    # --------------------------------------------------------

    website_records = []

    for vehicle in vehicles:

        website_record = create_website_record(
            vehicle
        )

        website_records.append(
            website_record
        )

    # --------------------------------------------------------
    # Create JSON package
    # --------------------------------------------------------

    json_package = {
        "dataset": {
            "name": "MotorNation 2026 U.S. Vehicle Master Dataset",
            "modelYear": 2026,
            "recordCount": len(
                website_records
            ),
            "generatedAt": datetime.now().isoformat(
                timespec="seconds"
            ),
        },

        "cars": website_records,
    }

    # --------------------------------------------------------
    # Write JSON
    # --------------------------------------------------------

    with EXPORT_JSON.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            json_package,
            file,
            indent=2,
            ensure_ascii=False
        )

    print()
    print("JSON export created:")
    print(EXPORT_JSON)

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    makes = sorted(
        {
            vehicle.get("make")
            for vehicle in vehicles
            if vehicle.get("make")
        }
    )

    models = sorted(
        {
            (
                vehicle.get("make"),
                vehicle.get("model")
            )
            for vehicle in vehicles
            if vehicle.get("make")
            and vehicle.get("model")
        }
    )

    print()
    print("-" * 70)
    print("DATASET SUMMARY")
    print("-" * 70)

    print(
        f"Vehicle variants: {len(vehicles)}"
    )

    print(
        f"Manufacturers: {len(makes)}"
    )

    print(
        f"Unique make/model combinations: "
        f"{len(models)}"
    )

    print()
    print("Manufacturers:")

    for make in makes:
        print(f"  - {make}")

    print()
    print("=" * 70)
    print("PROCESSING COMPLETE")
    print("=" * 70)

    return True


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":

    success = process_dataset()

    if not success:
        raise SystemExit(1)
from pathlib import Path
import csv
from collections import Counter


# ============================================================
# MotorNation - Vehicle Dataset Validator
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_FILE = PROJECT_ROOT / "data" / "raw" / "vehicles_raw.csv"


# ------------------------------------------------------------
# Required columns
# ------------------------------------------------------------

REQUIRED_COLUMNS = [
    "id",
    "year",
    "make",
    "model",
    "trim",
    "variant",
    "body_type",
    "vehicle_type",
    "fuel_type",
    "engine",
    "horsepower",
    "transmission",
    "drivetrain",
    "msrp",
    "seating",
    "description",
    "source_url",
    "source_name",
    "last_updated",
]


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def is_blank(value):
    """Return True when a value is empty or contains only spaces."""
    return value is None or str(value).strip() == ""


def to_number(value):
    """Convert a value to float when possible."""
    if is_blank(value):
        return None

    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


# ------------------------------------------------------------
# Main validation
# ------------------------------------------------------------

def validate_dataset():
    print("=" * 70)
    print("MotorNation - 2026 Vehicle Dataset Validator")
    print("=" * 70)

    print()
    print(f"Dataset: {CSV_FILE}")

    if not CSV_FILE.exists():
        print()
        print("ERROR: Dataset file was not found.")
        print(f"Expected location: {CSV_FILE}")
        return False

    print("File found.")
    print()

    # --------------------------------------------------------
    # Read CSV
    # --------------------------------------------------------

    try:
        with CSV_FILE.open(
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as file:
            reader = csv.DictReader(file)

            columns = reader.fieldnames or []
            rows = list(reader)

    except Exception as exc:
        print("ERROR: Could not read the CSV file.")
        print(f"Reason: {exc}")
        return False

    # --------------------------------------------------------
    # Check columns
    # --------------------------------------------------------

    print("-" * 70)
    print("1. COLUMN CHECK")
    print("-" * 70)

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in columns
    ]

    if missing_columns:
        print("FAILED")
        print("Missing columns:")

        for column in missing_columns:
            print(f"  - {column}")

        return False

    print("PASSED")
    print(f"Columns found: {len(columns)}")

    # --------------------------------------------------------
    # Check rows
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("2. RECORD CHECK")
    print("-" * 70)

    print(f"Total records: {len(rows)}")

    if not rows:
        print("FAILED")
        print("The dataset contains no records.")
        return False

    print("PASSED")

    # --------------------------------------------------------
    # Duplicate ID check
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("3. DUPLICATE ID CHECK")
    print("-" * 70)

    ids = [
        row.get("id", "").strip()
        for row in rows
        if not is_blank(row.get("id"))
    ]

    id_counts = Counter(ids)

    duplicate_ids = [
        vehicle_id
        for vehicle_id, count in id_counts.items()
        if count > 1
    ]

    if duplicate_ids:
        print("FAILED")
        print("Duplicate IDs found:")

        for vehicle_id in duplicate_ids:
            print(f"  - {vehicle_id}")

    else:
        print("PASSED")
        print("No duplicate IDs found.")

    # --------------------------------------------------------
    # Required field check
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("4. REQUIRED FIELD CHECK")
    print("-" * 70)

    missing_fields = []

    for row_number, row in enumerate(rows, start=2):
        for column in REQUIRED_COLUMNS:
            if is_blank(row.get(column)):
                missing_fields.append(
                    (row_number, column)
                )

    if missing_fields:
        print("WARNING")
        print(
            f"Missing required values: "
            f"{len(missing_fields)}"
        )

        # Show only the first 20 problems
        for row_number, column in missing_fields[:20]:
            print(
                f"  Row {row_number}: "
                f"{column} is empty"
            )

        if len(missing_fields) > 20:
            print(
                f"  ... and "
                f"{len(missing_fields) - 20} more"
            )

    else:
        print("PASSED")
        print("No required fields are missing.")

    # --------------------------------------------------------
    # Year check
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("5. MODEL YEAR CHECK")
    print("-" * 70)

    invalid_years = []

    for row_number, row in enumerate(rows, start=2):
        value = row.get("year", "").strip()

        try:
            year = int(value)

            if year < 2026:
                invalid_years.append(
                    (row_number, value)
                )

        except ValueError:
            invalid_years.append(
                (row_number, value)
            )

    if invalid_years:
        print("WARNING")

        for row_number, value in invalid_years[:20]:
            print(
                f"  Row {row_number}: "
                f"invalid year '{value}'"
            )

    else:
        print("PASSED")
        print("All records have valid 2026-or-newer years.")

    # --------------------------------------------------------
    # MSRP check
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("6. MSRP CHECK")
    print("-" * 70)

    invalid_prices = []

    for row_number, row in enumerate(rows, start=2):
        value = row.get("msrp", "").strip()
        price = to_number(value)

        if price is None or price <= 0:
            invalid_prices.append(
                (row_number, value)
            )

    if invalid_prices:
        print("WARNING")

        for row_number, value in invalid_prices[:20]:
            print(
                f"  Row {row_number}: "
                f"invalid MSRP '{value}'"
            )

    else:
        print("PASSED")
        print("All records have valid MSRP values.")

    # --------------------------------------------------------
    # Horsepower check
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("7. HORSEPOWER CHECK")
    print("-" * 70)

    invalid_hp = []

    for row_number, row in enumerate(rows, start=2):
        value = row.get("horsepower", "").strip()

        if is_blank(value):
            continue

        horsepower = to_number(value)

        if horsepower is None or horsepower <= 0:
            invalid_hp.append(
                (row_number, value)
            )

    if invalid_hp:
        print("WARNING")

        for row_number, value in invalid_hp[:20]:
            print(
                f"  Row {row_number}: "
                f"invalid horsepower '{value}'"
            )

    else:
        print("PASSED")

    # --------------------------------------------------------
    # Make/model/trim check
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("8. VEHICLE IDENTITY CHECK")
    print("-" * 70)

    invalid_identity = []

    for row_number, row in enumerate(rows, start=2):

        make = row.get("make", "").strip()
        model = row.get("model", "").strip()
        trim = row.get("trim", "").strip()

        if not make or not model or not trim:
            invalid_identity.append(
                (row_number, make, model, trim)
            )

    if invalid_identity:
        print("WARNING")

        for row_number, make, model, trim in invalid_identity[:20]:
            print(
                f"  Row {row_number}: "
                f"make='{make}', "
                f"model='{model}', "
                f"trim='{trim}'"
            )

    else:
        print("PASSED")
        print("Make, model and trim are present.")

    # --------------------------------------------------------
    # Variant count
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("9. VARIANT SUMMARY")
    print("-" * 70)

    vehicle_groups = {}

    for row in rows:
        key = (
            row.get("make", "").strip(),
            row.get("model", "").strip(),
            row.get("year", "").strip(),
        )

        vehicle_groups.setdefault(key, 0)
        vehicle_groups[key] += 1

    for (make, model, year), count in sorted(vehicle_groups.items()):
        print(
            f"{year} {make} {model}: "
            f"{count} variant(s)"
        )

    # --------------------------------------------------------
    # Fuel type summary
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("10. FUEL TYPE SUMMARY")
    print("-" * 70)

    fuel_counts = Counter(
        row.get("fuel_type", "").strip()
        for row in rows
        if not is_blank(row.get("fuel_type"))
    )

    for fuel_type, count in sorted(fuel_counts.items()):
        print(
            f"{fuel_type}: {count}"
        )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("VALIDATION COMPLETE")
    print("=" * 70)

    if duplicate_ids:
        print("RESULT: FAILED")
        print("Fix duplicate IDs before continuing.")
        return False

    if missing_columns:
        print("RESULT: FAILED")
        return False

    print("RESULT: PASSED")
    print()
    print(
        "The dataset structure is ready for the next stage."
    )

    return True


# ------------------------------------------------------------
# Run
# ------------------------------------------------------------

if __name__ == "__main__":
    success = validate_dataset()

    if not success:
        raise SystemExit(1)
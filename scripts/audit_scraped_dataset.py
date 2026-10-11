from pathlib import Path
import json


# ============================================================
# MotorNation - Existing Scraped Dataset Audit
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATASET_FILE = PROJECT_ROOT / "cars_v2_enriched.json"


def get_cars(data):
    """
    Support either:

    {
        "cars": [...]
    }

    or:

    [...]
    """

    if isinstance(data, dict):
        cars = data.get("cars", [])

        if isinstance(cars, list):
            return cars

        return []

    if isinstance(data, list):
        return data

    return []


def clean(value):
    if value is None:
        return ""

    return str(value).strip()


def main():

    print("=" * 70)
    print("MotorNation - Existing Scraped Dataset Audit")
    print("=" * 70)

    # --------------------------------------------------------
    # Locate dataset
    # --------------------------------------------------------

    print()
    print("Dataset:")
    print(DATASET_FILE)

    if not DATASET_FILE.exists():

        print()
        print("ERROR: Dataset file was not found.")
        print()
        print("Expected location:")
        print(DATASET_FILE)
        print()

        return False

    print("File found.")

    # --------------------------------------------------------
    # Load JSON
    # --------------------------------------------------------

    try:

        with DATASET_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

    except Exception as exc:

        print()
        print("ERROR: Could not read JSON.")
        print(f"Reason: {exc}")

        return False

    # --------------------------------------------------------
    # Get vehicle records
    # --------------------------------------------------------

    cars = get_cars(data)

    print()
    print("-" * 70)
    print("1. RECORD COUNT")
    print("-" * 70)

    print(f"Total records: {len(cars)}")

    if not cars:

        print()
        print("ERROR: No vehicle records found.")

        return False

    # --------------------------------------------------------
    # First record structure
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("2. FIRST RECORD STRUCTURE")
    print("-" * 70)

    first_car = cars[0]

    if isinstance(first_car, dict):

        for key in first_car.keys():
            print(f"  - {key}")

    # --------------------------------------------------------
    # Manufacturers
    # --------------------------------------------------------

    manufacturers = sorted(
        {
            clean(car.get("make"))
            for car in cars
            if isinstance(car, dict)
            and clean(car.get("make"))
        }
    )

    print()
    print("-" * 70)
    print("3. MANUFACTURERS")
    print("-" * 70)

    print(
        f"Unique manufacturers: "
        f"{len(manufacturers)}"
    )

    for make in manufacturers:
        print(f"  - {make}")

    # --------------------------------------------------------
    # Unique models
    # --------------------------------------------------------

    models = sorted(
        {
            (
                clean(car.get("make")),
                clean(car.get("model"))
            )
            for car in cars
            if isinstance(car, dict)
            and clean(car.get("make"))
            and clean(car.get("model"))
        }
    )

    print()
    print("-" * 70)
    print("4. UNIQUE MODELS")
    print("-" * 70)

    print(
        f"Unique make/model combinations: "
        f"{len(models)}"
    )

    # --------------------------------------------------------
    # Model year
    # --------------------------------------------------------

    years = sorted(
        {
            car.get("year")
            for car in cars
            if isinstance(car, dict)
            and car.get("year") is not None
        }
    )

    print()
    print("-" * 70)
    print("5. MODEL YEARS")
    print("-" * 70)

    print(
        f"Years found: {len(years)}"
    )

    for year in years:
        print(f"  - {year}")

    # --------------------------------------------------------
    # Fuel types
    # --------------------------------------------------------

    fuel_types = {}

    for car in cars:

        if not isinstance(car, dict):
            continue

        fuels = car.get("fuelTypes", [])

        if isinstance(fuels, str):
            fuels = [fuels]

        if not isinstance(fuels, list):
            continue

        for fuel in fuels:

            fuel = clean(fuel)

            if fuel:

                fuel_types[fuel] = (
                    fuel_types.get(fuel, 0) + 1
                )

    print()
    print("-" * 70)
    print("6. FUEL TYPES")
    print("-" * 70)

    for fuel, count in sorted(
        fuel_types.items()
    ):
        print(
            f"{fuel}: {count}"
        )

    # --------------------------------------------------------
    # Duplicate IDs
    # --------------------------------------------------------

    ids = []

    for car in cars:

        if isinstance(car, dict):

            car_id = clean(
                car.get("id")
            )

            if car_id:
                ids.append(car_id)

    duplicate_ids = sorted(
        {
            car_id
            for car_id in ids
            if ids.count(car_id) > 1
        }
    )

    print()
    print("-" * 70)
    print("7. DUPLICATE IDs")
    print("-" * 70)

    print(
        f"Duplicate IDs: "
        f"{len(duplicate_ids)}"
    )

    if duplicate_ids:

        for car_id in duplicate_ids:
            print(f"  - {car_id}")

    # --------------------------------------------------------
    # Missing MSRP
    # --------------------------------------------------------

    missing_msrp = []

    for car in cars:

        if not isinstance(car, dict):
            continue

        price = car.get("price")

        if isinstance(price, dict):

            msrp = price.get("msrp")

        else:

            msrp = price

        if msrp is None or clean(msrp) == "":
            missing_msrp.append(
                car.get("id")
            )

    print()
    print("-" * 70)
    print("8. MSRP")
    print("-" * 70)

    print(
        f"Records missing MSRP: "
        f"{len(missing_msrp)}"
    )

    # --------------------------------------------------------
    # Missing horsepower
    # --------------------------------------------------------

    missing_hp = []

    for car in cars:

        if not isinstance(car, dict):
            continue

        specifications = car.get(
            "specifications",
            {}
        )

        if not isinstance(
            specifications,
            dict
        ):
            specifications = {}

        horsepower = specifications.get(
            "horsepower"
        )

        if horsepower is None:
            missing_hp.append(
                car.get("id")
            )

    print()
    print("-" * 70)
    print("9. HORSEPOWER")
    print("-" * 70)

    print(
        f"Records missing horsepower: "
        f"{len(missing_hp)}"
    )

    # --------------------------------------------------------
    # Missing images
    # --------------------------------------------------------

    missing_images = []

    for car in cars:

        if not isinstance(car, dict):
            continue

        images = car.get(
            "images",
            []
        )

        if not images:

            missing_images.append(
                car.get("id")
            )

    print()
    print("-" * 70)
    print("10. IMAGES")
    print("-" * 70)

    print(
        f"Records missing images: "
        f"{len(missing_images)}"
    )

    # --------------------------------------------------------
    # Trim-level status
    # --------------------------------------------------------

    trim_level_true = 0
    trim_level_false = 0
    trim_level_unknown = 0

    for car in cars:

        if not isinstance(car, dict):
            continue

        quality = car.get(
            "dataQuality",
            {}
        )

        if not isinstance(
            quality,
            dict
        ):
            trim_level_unknown += 1
            continue

        trim_status = quality.get(
            "trimLevel"
        )

        if trim_status is True:
            trim_level_true += 1

        elif trim_status is False:
            trim_level_false += 1

        else:
            trim_level_unknown += 1

    print()
    print("-" * 70)
    print("11. TRIM-LEVEL COVERAGE")
    print("-" * 70)

    print(
        f"Trim-level records: "
        f"{trim_level_true}"
    )

    print(
        f"Model-level records: "
        f"{trim_level_false}"
    )

    print(
        f"Unknown: "
        f"{trim_level_unknown}"
    )

    # --------------------------------------------------------
    # Source information
    # --------------------------------------------------------

    source_counts = {}

    for car in cars:

        if not isinstance(car, dict):
            continue

        sources = []

        source = car.get("source")

        if isinstance(source, str):
            sources.append(source)

        elif isinstance(source, dict):

            name = clean(
                source.get("name")
            )

            if name:
                sources.append(name)

        sources.append(
            clean(car.get("sourceName"))
        )

        for source_name in sources:

            source_name = clean(
                source_name
            )

            if source_name:

                source_counts[source_name] = (
                    source_counts.get(
                        source_name,
                        0
                    ) + 1
                )

    print()
    print("-" * 70)
    print("12. SOURCES")
    print("-" * 70)

    if source_counts:

        for source, count in sorted(
            source_counts.items()
        ):
            print(
                f"{source}: {count}"
            )

    else:

        print(
            "No source-name field was detected."
        )

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    status_counts = {}

    for car in cars:

        if not isinstance(car, dict):
            continue

        status = clean(
            car.get("status")
        )

        if status:

            status_counts[status] = (
                status_counts.get(
                    status,
                    0
                ) + 1
            )

    print()
    print("-" * 70)
    print("13. VEHICLE STATUS")
    print("-" * 70)

    if status_counts:

        for status, count in sorted(
            status_counts.items()
        ):
            print(
                f"{status}: {count}"
            )

    else:

        print(
            "No status field detected."
        )

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("AUDIT COMPLETE")
    print("=" * 70)

    print()
    print(
        f"Total records: {len(cars)}"
    )

    print(
        f"Manufacturers: "
        f"{len(manufacturers)}"
    )

    print(
        f"Unique models: "
        f"{len(models)}"
    )

    print(
        f"Duplicate IDs: "
        f"{len(duplicate_ids)}"
    )

    print(
        f"Missing MSRP: "
        f"{len(missing_msrp)}"
    )

    print(
        f"Missing horsepower: "
        f"{len(missing_hp)}"
    )

    print(
        f"Missing images: "
        f"{len(missing_images)}"
    )

    print(
        f"Trim-level records: "
        f"{trim_level_true}"
    )

    print(
        f"Model-level records: "
        f"{trim_level_false}"
    )

    print()
    print("=" * 70)
    print("NEXT STEP: USE THIS AUDIT TO PLAN DATA ENRICHMENT")
    print("=" * 70)

    return True


if __name__ == "__main__":

    success = main()

    if not success:
        raise SystemExit(1)
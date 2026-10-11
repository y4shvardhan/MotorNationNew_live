from pathlib import Path
import json
import re
import csv


# ============================================================
# MotorNation
# Extract 2026 Vehicle Candidates
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT
    / "caranddriver_scraper"
    / "cars.jsonl"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "vehicles_2026_candidates.csv"
)


TARGET_YEAR = 2026


# ------------------------------------------------------------
# Year detection
# ------------------------------------------------------------

YEAR_PATTERN = re.compile(
    r"\b(20(?:1[7-9]|2[0-9]|3[0-9]))\b"
)


def clean(value):

    if value is None:
        return ""

    return str(value).strip()


def detect_year(item):

    """
    Try to determine the model year from:

    1. make/model
    2. title
    3. URL
    """

    sources = [
        clean(item.get("model")),
        clean(item.get("title")),
        clean(item.get("url")),
    ]

    for source in sources:

        match = YEAR_PATTERN.search(source)

        if match:

            return int(
                match.group(1)
            )

    return None


def remove_year_from_model(model):

    """
    Remove a year such as:

    Camry 2025

    -> Camry

    This is only used for analysis.
    """

    model = clean(model)

    return YEAR_PATTERN.sub(
        "",
        model
    ).strip()


def main():

    print("=" * 75)
    print("MotorNation - 2026 Candidate Extraction")
    print("=" * 75)

    if not INPUT_FILE.exists():

        print()
        print("ERROR:")
        print(
            f"Input file not found:\n{INPUT_FILE}"
        )

        return False

    records = []

    invalid_lines = 0

    with INPUT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        for line_number, line in enumerate(
            file,
            start=1
        ):

            line = line.strip()

            if not line:
                continue

            try:

                item = json.loads(line)

                if isinstance(item, dict):
                    records.append(item)

            except json.JSONDecodeError:

                invalid_lines += 1

    print()
    print(
        f"Raw records read: {len(records)}"
    )

    print(
        f"Invalid lines: {invalid_lines}"
    )

    # --------------------------------------------------------
    # Extract years
    # --------------------------------------------------------

    year_counts = {}

    candidates = []

    year_unknown = []

    for item in records:

        year = detect_year(item)

        if year is None:

            year_unknown.append(item)

            continue

        year_counts[year] = (
            year_counts.get(year, 0) + 1
        )

        if year == TARGET_YEAR:

            candidates.append(item)

    # --------------------------------------------------------
    # Year summary
    # --------------------------------------------------------

    print()
    print("-" * 75)
    print("MODEL YEAR DETECTION")
    print("-" * 75)

    for year in sorted(year_counts):

        print(
            f"{year}: "
            f"{year_counts[year]}"
        )

    print()
    print(
        f"Records where year could not be detected: "
        f"{len(year_unknown)}"
    )

    # --------------------------------------------------------
    # 2026 candidates
    # --------------------------------------------------------

    print()
    print("-" * 75)
    print("2026 CANDIDATES")
    print("-" * 75)

    print(
        f"2026 candidate records: "
        f"{len(candidates)}"
    )

    # --------------------------------------------------------
    # Build CSV
    # --------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    fieldnames = [
        "source_record_index",
        "make",
        "model",
        "normalized_model",
        "detected_year",
        "title",
        "rating",
        "starting_price",
        "pros",
        "cons",
        "verdict",
        "url",
    ]

    with OUTPUT_FILE.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for index, item in enumerate(
            candidates,
            start=1
        ):

            pros = item.get(
                "pros",
                []
            )

            cons = item.get(
                "cons",
                []
            )

            if isinstance(
                pros,
                list
            ):

                pros = " | ".join(
                    clean(x)
                    for x in pros
                )

            else:

                pros = clean(pros)

            if isinstance(
                cons,
                list
            ):

                cons = " | ".join(
                    clean(x)
                    for x in cons
                )

            else:

                cons = clean(cons)

            model = clean(
                item.get("model")
            )

            writer.writerow(
                {
                    "source_record_index":
                        index,

                    "make":
                        clean(
                            item.get("make")
                        ),

                    "model":
                        model,

                    "normalized_model":
                        remove_year_from_model(
                            model
                        ),

                    "detected_year":
                        TARGET_YEAR,

                    "title":
                        clean(
                            item.get("title")
                        ),

                    "rating":
                        clean(
                            item.get("rating")
                        ),

                    "starting_price":
                        clean(
                            item.get(
                                "starting_price"
                            )
                        ),

                    "pros":
                        pros,

                    "cons":
                        cons,

                    "verdict":
                        clean(
                            item.get("verdict")
                        ),

                    "url":
                        clean(
                            item.get("url")
                        ),
                }
            )

    # --------------------------------------------------------
    # Manufacturer summary
    # --------------------------------------------------------

    manufacturers = {}

    for item in candidates:

        make = clean(
            item.get("make")
        )

        if make:

            manufacturers[make] = (
                manufacturers.get(
                    make,
                    0
                ) + 1
            )

    print()
    print("-" * 75)
    print("2026 MANUFACTURER COVERAGE")
    print("-" * 75)

    for make, count in sorted(
        manufacturers.items()
    ):

        print(
            f"{make:30} {count}"
        )

    print()
    print(
        f"2026 manufacturers found: "
        f"{len(manufacturers)}"
    )

    # --------------------------------------------------------
    # Final output
    # --------------------------------------------------------

    print()
    print("=" * 75)
    print("EXTRACTION COMPLETE")
    print("=" * 75)

    print()
    print(
        f"Input records: {len(records)}"
    )

    print(
        f"2026 candidates: {len(candidates)}"
    )

    print()
    print(
        "Output:"
    )

    print(OUTPUT_FILE)

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "This is a candidate dataset only."
    )

    print(
        "It has NOT yet been declared the final"
    )

    print(
        "MotorNation 2026 master dataset."
    )

    return True


if __name__ == "__main__":

    success = main()

    if not success:
        raise SystemExit(1)
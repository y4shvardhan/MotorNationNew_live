from pathlib import Path
import csv


# ============================================================
# MotorNation - 2026 Model Discovery Setup
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

MANUFACTURERS_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "manufacturers_2026.csv"
)

MODELS_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "models_2026.csv"
)


COLUMNS = [
    "id",
    "year",
    "make",
    "model",
    "vehicle_type",
    "body_type",
    "fuel_type",
    "source_url",
    "source_name",
    "verified",
    "last_verified",
]


def main():

    print("=" * 70)
    print("MotorNation - 2026 Model Discovery Setup")
    print("=" * 70)

    # --------------------------------------------------------
    # Check manufacturer file
    # --------------------------------------------------------

    if not MANUFACTURERS_FILE.exists():

        print()
        print("ERROR:")
        print("Manufacturer file was not found:")
        print(MANUFACTURERS_FILE)

        return False

    # --------------------------------------------------------
    # Read manufacturers
    # --------------------------------------------------------

    with MANUFACTURERS_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        manufacturers = list(
            csv.DictReader(file)
        )

    active_manufacturers = [
        row
        for row in manufacturers
        if row.get("active", "").strip().lower()
        == "true"
    ]

    print()
    print(
        f"Manufacturers found: {len(manufacturers)}"
    )

    print(
        f"Active manufacturers: "
        f"{len(active_manufacturers)}"
    )

    # --------------------------------------------------------
    # Create models file if necessary
    # --------------------------------------------------------

    MODELS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if not MODELS_FILE.exists():

        with MODELS_FILE.open(
            "w",
            encoding="utf-8",
            newline=""
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=COLUMNS
            )

            writer.writeheader()

        print()
        print("Created model discovery file:")
        print(MODELS_FILE)

    else:

        print()
        print("Model discovery file already exists:")
        print(MODELS_FILE)

    # --------------------------------------------------------
    # Display manufacturers
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("MANUFACTURER COLLECTION CHECKLIST")
    print("-" * 70)

    for number, manufacturer in enumerate(
        active_manufacturers,
        start=1
    ):

        print(
            f"{number:02d}. "
            f"{manufacturer['make']}"
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("MODEL DISCOVERY SETUP COMPLETE")
    print("=" * 70)

    print()
    print("Next file:")
    print(MODELS_FILE)

    print()
    print(
        "The models file is intentionally empty."
    )

    print(
        "We will populate it only with "
        "verified 2026 U.S. models."
    )

    return True


if __name__ == "__main__":

    success = main()

    if not success:
        raise SystemExit(1)
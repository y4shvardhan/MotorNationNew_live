from pathlib import Path
import json
from collections import Counter


# ============================================================
# MotorNation
# Audit Existing Car and Driver Scraped JSONL Dataset
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

JSONL_FILE = (
    PROJECT_ROOT
    / "caranddriver_scraper"
    / "cars.jsonl"
)


def clean(value):
    if value is None:
        return ""

    return str(value).strip()


def main():

    print("=" * 75)
    print("MotorNation - Existing Scraped JSONL Audit")
    print("=" * 75)

    print()
    print("Source file:")
    print(JSONL_FILE)

    if not JSONL_FILE.exists():

        print()
        print("ERROR: cars.jsonl was not found.")
        return False

    print("File found.")

    # --------------------------------------------------------
    # Read JSONL
    # --------------------------------------------------------

    records = []
    invalid_lines = 0

    with JSONL_FILE.open(
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

    # --------------------------------------------------------
    # Basic information
    # --------------------------------------------------------

    print()
    print("-" * 75)
    print("1. BASIC DATASET INFORMATION")
    print("-" * 75)

    print(
        f"Valid JSON records: {len(records)}"
    )

    print(
        f"Invalid JSON lines: {invalid_lines}"
    )

    if not records:

        print()
        print("ERROR: No valid records found.")
        return False

    # --------------------------------------------------------
    # Fields
    # --------------------------------------------------------

    field_counts = Counter()

    for item in records:

        for key in item.keys():

            field_counts[key] += 1

    print()
    print("-" * 75)
    print("2. ALL SCRAPED FIELDS")
    print("-" * 75)

    print(
        f"Unique fields found: "
        f"{len(field_counts)}"
    )

    for field, count in sorted(
        field_counts.items()
    ):

        percentage = (
            count / len(records)
        ) * 100

        print(
            f"{field:35} "
            f"{count:6} "
            f"({percentage:6.2f}%)"
        )

    # --------------------------------------------------------
    # Manufacturers
    # --------------------------------------------------------

    manufacturers = Counter()

    for item in records:

        make = clean(
            item.get("make")
        )

        if make:
            manufacturers[make] += 1

    print()
    print("-" * 75)
    print("3. MANUFACTURERS")
    print("-" * 75)

    print(
        f"Unique manufacturers: "
        f"{len(manufacturers)}"
    )

    for make, count in sorted(
        manufacturers.items()
    ):

        print(
            f"{make:30} {count}"
        )

    # --------------------------------------------------------
    # Models
    # --------------------------------------------------------

    models = Counter()

    for item in records:

        make = clean(
            item.get("make")
        )

        model = clean(
            item.get("model")
        )

        if make and model:

            models[
                (make, model)
            ] += 1

    print()
    print("-" * 75)
    print("4. UNIQUE MODELS")
    print("-" * 75)

    print(
        f"Unique make/model combinations: "
        f"{len(models)}"
    )

    # --------------------------------------------------------
    # Show models by manufacturer
    # --------------------------------------------------------

    models_by_make = {}

    for (make, model), count in models.items():

        models_by_make.setdefault(
            make,
            []
        ).append(
            (model, count)
        )

    for make in sorted(
        models_by_make
    ):

        print()
        print(f"[{make}]")

        for model, count in sorted(
            models_by_make[make]
        ):

            print(
                f"  {model} "
                f"({count} records)"
            )

    # --------------------------------------------------------
    # Years
    # --------------------------------------------------------

    years = Counter()

    for item in records:

        year = item.get("year")

        if year is not None:

            years[
                str(year)
            ] += 1

    print()
    print("-" * 75)
    print("5. MODEL YEARS")
    print("-" * 75)

    if years:

        for year, count in sorted(
            years.items()
        ):

            print(
                f"{year}: {count}"
            )

    else:

        print(
            "No year field detected."
        )

    # --------------------------------------------------------
    # Titles
    # --------------------------------------------------------

    title_count = sum(
        1
        for item in records
        if clean(item.get("title"))
    )

    print()
    print("-" * 75)
    print("6. TITLE COVERAGE")
    print("-" * 75)

    print(
        f"Records with title: "
        f"{title_count}/{len(records)}"
    )

    # --------------------------------------------------------
    # Prices
    # --------------------------------------------------------

    price_count = sum(
        1
        for item in records
        if (
            item.get("starting_price")
            is not None
            and clean(
                item.get("starting_price")
            )
        )
    )

    print()
    print("-" * 75)
    print("7. PRICE COVERAGE")
    print("-" * 75)

    print(
        f"Records with starting price: "
        f"{price_count}/{len(records)}"
    )

    # --------------------------------------------------------
    # Ratings
    # --------------------------------------------------------

    rating_count = sum(
        1
        for item in records
        if (
            item.get("rating")
            is not None
            and clean(item.get("rating"))
        )
    )

    print()
    print("-" * 75)
    print("8. RATING COVERAGE")
    print("-" * 75)

    print(
        f"Records with rating: "
        f"{rating_count}/{len(records)}"
    )

    # --------------------------------------------------------
    # Pros / Cons / Verdict
    # --------------------------------------------------------

    pros_count = sum(
        1
        for item in records
        if item.get("pros")
    )

    cons_count = sum(
        1
        for item in records
        if item.get("cons")
    )

    verdict_count = sum(
        1
        for item in records
        if clean(item.get("verdict"))
    )

    print()
    print("-" * 75)
    print("9. EDITORIAL DATA")
    print("-" * 75)

    print(
        f"Pros:    {pros_count}/{len(records)}"
    )

    print(
        f"Cons:    {cons_count}/{len(records)}"
    )

    print(
        f"Verdict: {verdict_count}/{len(records)}"
    )

    # --------------------------------------------------------
    # URLs
    # --------------------------------------------------------

    url_count = sum(
        1
        for item in records
        if clean(item.get("url"))
    )

    print()
    print("-" * 75)
    print("10. SOURCE URL COVERAGE")
    print("-" * 75)

    print(
        f"Records with URL: "
        f"{url_count}/{len(records)}"
    )

    # --------------------------------------------------------
    # Duplicate URLs
    # --------------------------------------------------------

    urls = [
        clean(item.get("url"))
        for item in records
        if clean(item.get("url"))
    ]

    url_counts = Counter(urls)

    duplicate_urls = {
        url: count
        for url, count in url_counts.items()
        if count > 1
    }

    print()
    print("-" * 75)
    print("11. DUPLICATE URL CHECK")
    print("-" * 75)

    print(
        f"Duplicate URLs: "
        f"{len(duplicate_urls)}"
    )

    for url, count in list(
        duplicate_urls.items()
    )[:20]:

        print(
            f"{count}x {url}"
        )

    # --------------------------------------------------------
    # Empty / incomplete records
    # --------------------------------------------------------

    incomplete = []

    for index, item in enumerate(
        records,
        start=1
    ):

        missing = []

        for field in [
            "make",
            "model",
            "title",
            "url"
        ]:

            if not clean(
                item.get(field)
            ):

                missing.append(field)

        if missing:

            incomplete.append(
                {
                    "record": index,
                    "missing": missing
                }
            )

    print()
    print("-" * 75)
    print("12. BASIC RECORD COMPLETENESS")
    print("-" * 75)

    print(
        f"Records missing one or more "
        f"basic fields: {len(incomplete)}"
    )

    for item in incomplete[:20]:

        print(
            f"Record {item['record']}: "
            f"{', '.join(item['missing'])}"
        )

    # --------------------------------------------------------
    # First record sample
    # --------------------------------------------------------

    print()
    print("-" * 75)
    print("13. FIRST RECORD SAMPLE")
    print("-" * 75)

    print(
        json.dumps(
            records[0],
            indent=2,
            ensure_ascii=False
        )
    )

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    print()
    print("=" * 75)
    print("AUDIT COMPLETE")
    print("=" * 75)

    print()
    print(
        f"Total records: {len(records)}"
    )

    print(
        f"Unique manufacturers: "
        f"{len(manufacturers)}"
    )

    print(
        f"Unique models: "
        f"{len(models)}"
    )

    print(
        f"Unique fields: "
        f"{len(field_counts)}"
    )

    print(
        f"Duplicate URLs: "
        f"{len(duplicate_urls)}"
    )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "The existing scraped JSONL has been "
        "audited only."
    )

    print(
        "No source data has been modified."
    )

    print(
        "No records have been deleted."
    )

    print(
        "No scraper has been changed."
    )

    return True


if __name__ == "__main__":

    success = main()

    if not success:
        raise SystemExit(1)
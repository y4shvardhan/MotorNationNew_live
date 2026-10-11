import json
import csv
from pathlib import Path
from datetime import datetime, timezone


# ============================================================
# MOTOR NATION - BUILD FULL SCRAPED DATASET
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    BASE_DIR
    / "caranddriver_scraper"
    / "cars.jsonl"
)

OUTPUT_JSON = (
    BASE_DIR
    / "data"
    / "exports"
    / "vehicles_all_scraped.json"
)

OUTPUT_CSV = (
    BASE_DIR
    / "data"
    / "processed"
    / "vehicles_all_scraped.csv"
)


# ============================================================
# CREATE OUTPUT DIRECTORIES
# ============================================================

OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    if isinstance(value, list):
        return ", ".join(
            str(item).strip()
            for item in value
            if str(item).strip()
        )

    return str(value).strip()


def clean_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    value = str(value).strip()

    if not value:
        return []

    return [value]


def parse_price(value):
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    cleaned = (
        value
        .replace("$", "")
        .replace(",", "")
        .strip()
    )

    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_year(make, model, title, url):
    """
    Try to detect a model year from the existing scraped data.

    This is informational only.
    It does NOT mean the vehicle has been verified
    as being sold in that model year.
    """

    import re

    sources = [
        model,
        title,
        url,
    ]

    for source in sources:

        text = clean_text(source)

        matches = re.findall(
            r"\b(20(?:1[7-9]|2[0-9]|3[0-9]))\b",
            text
        )

        if matches:
            return int(matches[0])

    return None


# ============================================================
# READ RAW JSONL
# ============================================================

if not INPUT_FILE.exists():

    print()
    print("ERROR: Source file was not found:")
    print(INPUT_FILE)
    print()

    raise SystemExit(1)


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

        except json.JSONDecodeError:

            invalid_lines += 1

            print(
                f"WARNING: Invalid JSON "
                f"on line {line_number}"
            )

            continue

        if not isinstance(item, dict):
            continue

        records.append(item)


# ============================================================
# BUILD CLEAN DATASET
# ============================================================

vehicles = []

seen_urls = set()

duplicate_urls = 0


for index, item in enumerate(
    records,
    start=1
):

    make = clean_text(
        item.get("make")
    )

    model = clean_text(
        item.get("model")
    )

    title = clean_text(
        item.get("title")
    )

    url = clean_text(
        item.get("url")
    )

    # --------------------------------------------------------
    # Skip records without a useful vehicle identity
    # --------------------------------------------------------

    if not make and not model and not title:
        continue

    # --------------------------------------------------------
    # URL duplicate check
    # --------------------------------------------------------

    if url:

        if url in seen_urls:

            duplicate_urls += 1
            continue

        seen_urls.add(url)

    # --------------------------------------------------------
    # Build vehicle record
    # --------------------------------------------------------

    vehicle = {

        "id": index,

        "year": extract_year(
            make,
            model,
            title,
            url
        ),

        "make": make,

        "model": model,

        "title": title,

        "rating": clean_text(
            item.get("rating")
        ),

        "price": parse_price(
            item.get("starting_price")
        ),

        "startingPrice": clean_text(
            item.get("starting_price")
        ),

        "pros": clean_list(
            item.get("pros")
        ),

        "cons": clean_list(
            item.get("cons")
        ),

        "verdict": clean_text(
            item.get("verdict")
        ),

        "description": clean_text(
            item.get("verdict")
        ),

        "source": {

            "name": "Car and Driver",

            "url": url,

            "type": "scraped_editorial_data",

        },

        "dataStatus": {

            "source": "Car and Driver",

            "yearVerified": False,

            "specificationsVerified": False,

            "trimVerified": False,

            "variantVerified": False,

        },

    }

    vehicles.append(vehicle)


# ============================================================
# DATASET METADATA
# ============================================================

generated_at = datetime.now(
    timezone.utc
).isoformat()


dataset = {

    "dataset": {

        "name":
            "MotorNation Full Scraped Vehicle Dataset",

        "description":
            "Vehicle records collected from the existing "
            "MotorNation Car and Driver scrape.",

        "recordCount":
            len(vehicles),

        "source":
            "Car and Driver",

        "generatedAt":
            generated_at,

        "status":
            "scraped_source_dataset",

        "warning":
            "This dataset is not a verified 2026 "
            "U.S. vehicle catalog. Records represent "
            "the existing scraped source data.",

    },

    "cars":
        vehicles,

}


# ============================================================
# WRITE JSON
# ============================================================

with OUTPUT_JSON.open(
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        dataset,
        file,
        indent=2,
        ensure_ascii=False
    )


# ============================================================
# WRITE CSV
# ============================================================

csv_columns = [

    "id",
    "year",
    "make",
    "model",
    "title",
    "rating",
    "price",
    "startingPrice",
    "pros",
    "cons",
    "verdict",
    "description",
    "sourceName",
    "sourceUrl",

]


with OUTPUT_CSV.open(
    "w",
    encoding="utf-8-sig",
    newline=""
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=csv_columns
    )

    writer.writeheader()

    for vehicle in vehicles:

        writer.writerow({

            "id":
                vehicle["id"],

            "year":
                vehicle["year"] or "",

            "make":
                vehicle["make"],

            "model":
                vehicle["model"],

            "title":
                vehicle["title"],

            "rating":
                vehicle["rating"],

            "price":
                vehicle["price"] or "",

            "startingPrice":
                vehicle["startingPrice"],

            "pros":
                " | ".join(
                    vehicle["pros"]
                ),

            "cons":
                " | ".join(
                    vehicle["cons"]
                ),

            "verdict":
                vehicle["verdict"],

            "description":
                vehicle["description"],

            "sourceName":
                vehicle["source"]["name"],

            "sourceUrl":
                vehicle["source"]["url"],

        })


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 75)
print("MotorNation - Full Scraped Dataset")
print("=" * 75)

print()
print(f"Input records:              {len(records)}")
print(f"Invalid JSON lines:         {invalid_lines}")
print(f"Duplicate URLs skipped:    {duplicate_urls}")
print(f"Final vehicle records:      {len(vehicles)}")

print()
print("OUTPUT FILES")
print("-" * 75)

print()
print(OUTPUT_JSON)

print()
print(OUTPUT_CSV)

print()
print("=" * 75)
print("DATASET BUILD COMPLETE")
print("=" * 75)

import os
import re
import time

import pandas as pd
import requests


# ============================================================
# MOTORNATION
# VERIFIED VEHICLE IMAGE URL FINDER
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

EXCEL_FILE = os.path.join(
    BASE_DIR,
    "excel",
    "USA_Master_Car_Catalog_2026_with_Images_Reviews_Pros_Cons.xlsx"
)

OUTPUT_FILE = os.path.join(
    BASE_DIR,
    "excel",
    "MotorNation_Master_With_Verified_Images.xlsx"
)

SHEET_NAME = "Master 2026-2027 US Catalog"

SUMMARY_SHEET = "Executive Summary & Analytics"

API_URL = (
    "https://commons.wikimedia.org/w/api.php"
)

HEADERS = {
    "User-Agent": (
        "MotorNation/1.0 "
        "(vehicle research dataset)"
    )
}


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(value):

    if pd.isna(value):
        return ""

    value = str(value).strip()

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value


def normalize_text(value):

    value = clean_text(value)

    value = value.lower()

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# BUILD SEARCH QUERIES
# ============================================================

def build_search_queries(
    year,
    make,
    model
):

    year = clean_text(year)
    make = clean_text(make)
    model = clean_text(model)

    queries = []

    if year and make and model:

        queries.append(
            f"{year} {make} {model}"
        )

    if make and model:

        queries.append(
            f"{make} {model}"
        )

    if model:

        queries.append(
            model
        )

    # Remove duplicate queries
    unique_queries = []

    for query in queries:

        if query not in unique_queries:

            unique_queries.append(query)

    return unique_queries


# ============================================================
# SEARCH WIKIMEDIA COMMONS
# ============================================================

def search_commons(
    query,
    limit=10
):

    params = {

        "action": "query",

        "format": "json",

        "generator": "search",

        "gsrsearch": query,

        "gsrnamespace": 6,

        "gsrlimit": limit,

        "prop": "imageinfo",

        "iiprop": "url|mime|size",

        "iiurlwidth": 1200,
    }

    try:

        response = requests.get(
            API_URL,
            params=params,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        pages = data.get(
            "query",
            {}
        ).get(
            "pages",
            {}
        )

        return list(
            pages.values()
        )

    except Exception as error:

        print(
            f"      Wikimedia request failed: {error}"
        )

        return []


# ============================================================
# VERIFY IMAGE URL
# ============================================================

def validate_image_url(url):

    if not url:

        return False

    # --------------------------------------------------------
    # Try HEAD first
    # --------------------------------------------------------

    try:

        response = requests.head(
            url,
            headers=HEADERS,
            timeout=15,
            allow_redirects=True
        )

        content_type = (
            response.headers
            .get(
                "Content-Type",
                ""
            )
            .lower()
        )

        if (
            response.status_code == 200
            and content_type.startswith("image/")
        ):

            return True

    except Exception:
        pass


    # --------------------------------------------------------
    # Some servers don't support HEAD correctly.
    # Try GET.
    # --------------------------------------------------------

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
            stream=True
        )

        content_type = (
            response.headers
            .get(
                "Content-Type",
                ""
            )
            .lower()
        )

        valid = (
            response.status_code == 200
            and content_type.startswith("image/")
        )

        response.close()

        return valid

    except Exception:

        return False


# ============================================================
# SCORE SEARCH RESULT
# ============================================================

def score_result(
    page,
    year,
    make,
    model
):

    title = clean_text(
        page.get(
            "title",
            ""
        )
    )

    normalized_title = normalize_text(
        title
    )

    normalized_make = normalize_text(
        make
    )

    normalized_model = normalize_text(
        model
    )

    normalized_year = normalize_text(
        year
    )

    score = 0


    # --------------------------------------------------------
    # MAKE
    # --------------------------------------------------------

    if (
        normalized_make
        and normalized_make in normalized_title
    ):

        score += 30


    # --------------------------------------------------------
    # MODEL
    # --------------------------------------------------------

    if (
        normalized_model
        and normalized_model in normalized_title
    ):

        score += 40


    # --------------------------------------------------------
    # YEAR
    # --------------------------------------------------------

    if (
        normalized_year
        and normalized_year in normalized_title
    ):

        score += 30


    # --------------------------------------------------------
    # VEHICLE WORDS
    # --------------------------------------------------------

    vehicle_words = [
        "car",
        "automobile",
        "vehicle",
        "sedan",
        "suv",
        "coupe",
        "truck",
        "wagon",
        "hatchback",
        "crossover",
        "pickup",
        "convertible",
    ]

    for word in vehicle_words:

        if word in normalized_title:

            score += 2


    # --------------------------------------------------------
    # BAD / IRRELEVANT RESULTS
    # --------------------------------------------------------

    bad_words = [
        "logo",
        "dealership",
        "dealer",
        "sign",
        "person",
        "race",
        "racing",
        "toy",
        "model kit",
        "wheel",
        "engine",
    ]

    for word in bad_words:

        if word in normalized_title:

            score -= 15


    return score


# ============================================================
# FIND BEST IMAGE
# ============================================================

def find_vehicle_image(
    year,
    make,
    model
):

    queries = build_search_queries(
        year,
        make,
        model
    )

    candidates = []


    # --------------------------------------------------------
    # Search each query
    # --------------------------------------------------------

    for query in queries:

        print(
            f"      Searching: {query}"
        )

        pages = search_commons(
            query,
            limit=10
        )

        for page in pages:

            title = page.get(
                "title",
                ""
            )

            image_info = page.get(
                "imageinfo",
                []
            )

            if not image_info:

                continue

            info = image_info[0]

            # Prefer thumbnail because it is generally
            # easier to load on a website.

            url = (
                info.get("thumburl")
                or info.get("url")
            )

            if not url:

                continue

            mime = str(
                info.get(
                    "mime",
                    ""
                )
            ).lower()

            if not mime.startswith(
                "image/"
            ):

                continue

            score = score_result(
                page,
                year,
                make,
                model
            )

            candidates.append(
                {
                    "title": title,
                    "url": url,
                    "score": score,
                    "mime": mime,
                }
            )


    if not candidates:

        return None


    # --------------------------------------------------------
    # Highest score first
    # --------------------------------------------------------

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True
    )


    # --------------------------------------------------------
    # Verify candidates
    # --------------------------------------------------------

    for candidate in candidates:

        print(
            "      Testing:"
            f" {candidate['title']}"
        )

        if validate_image_url(
            candidate["url"]
        ):

            print(
                "      VERIFIED:"
            )

            print(
                f"      {candidate['url']}"
            )

            return candidate


    return None


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "MOTORNATION — VERIFIED VEHICLE IMAGE FINDER"
    )
    print("=" * 70)
    print()


    # --------------------------------------------------------
    # CHECK EXCEL
    # --------------------------------------------------------

    if not os.path.exists(
        EXCEL_FILE
    ):

        print(
            "ERROR: Excel file not found:"
        )

        print(
            EXCEL_FILE
        )

        return


    print(
        "Excel file:"
    )

    print(
        EXCEL_FILE
    )

    print()


    # --------------------------------------------------------
    # READ MASTER SHEET
    # --------------------------------------------------------

    try:

        df = pd.read_excel(
            EXCEL_FILE,
            sheet_name=SHEET_NAME,
            header=2
        )

    except Exception as error:

        print(
            "ERROR reading Excel:"
        )

        print(error)

        return


    print(
        f"Vehicles found: {len(df)}"
    )

    print()


    # --------------------------------------------------------
    # REQUIRED COLUMNS
    # --------------------------------------------------------

    required_columns = [
        "Year",
        "Make",
        "Model / Model Group",
    ]


    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]


    if missing_columns:

        print(
            "ERROR: Missing columns:"
        )

        for column in missing_columns:

            print(
                f" - {column}"
            )

        print()

        print(
            "Available columns:"
        )

        for column in df.columns:

            print(
                f" - {column}"
            )

        return


    # --------------------------------------------------------
    # CREATE RESULT COLUMNS
    # --------------------------------------------------------

    if "Verified Image URL" not in df.columns:

        df[
            "Verified Image URL"
        ] = ""


    if "Image Status" not in df.columns:

        df[
            "Image Status"
        ] = ""


    if "Image Source" not in df.columns:

        df[
            "Image Source"
        ] = ""


    if "Image File" not in df.columns:

        df[
            "Image File"
        ] = ""


    # --------------------------------------------------------
    # COUNTERS
    # --------------------------------------------------------

    total = len(df)

    verified = 0

    not_found = 0


    # --------------------------------------------------------
    # PROCESS VEHICLES
    # --------------------------------------------------------

    for index, row in df.iterrows():

        vehicle_number = index + 1


        year = clean_text(
            row.get(
                "Year",
                ""
            )
        )


        make = clean_text(
            row.get(
                "Make",
                ""
            )
        )


        model = clean_text(
            row.get(
                "Model / Model Group",
                ""
            )
        )


        print()
        print("-" * 70)

        print(
            f"[{vehicle_number}/{total}] "
            f"{year} {make} {model}"
        )


        # ----------------------------------------------------
        # CHECK EXISTING VERIFIED URL
        # ----------------------------------------------------

        existing = clean_text(
            row.get(
                "Verified Image URL",
                ""
            )
        )


        if (
            existing
            and existing.startswith("http")
        ):

            print(
                "      Existing verified URL."
            )

            verified += 1

            continue


        # ----------------------------------------------------
        # SEARCH
        # ----------------------------------------------------

        result = find_vehicle_image(
            year,
            make,
            model
        )


        # ----------------------------------------------------
        # VERIFIED
        # ----------------------------------------------------

        if result:

            df.at[
                index,
                "Verified Image URL"
            ] = result["url"]


            df.at[
                index,
                "Image Status"
            ] = "Verified"


            df.at[
                index,
                "Image Source"
            ] = "Wikimedia Commons"


            df.at[
                index,
                "Image File"
            ] = result["title"]


            verified += 1


            print(
                "      STATUS: VERIFIED"
            )


        # ----------------------------------------------------
        # NOT FOUND
        # ----------------------------------------------------

        else:

            df.at[
                index,
                "Verified Image URL"
            ] = ""


            df.at[
                index,
                "Image Status"
            ] = "Not Found"


            df.at[
                index,
                "Image Source"
            ] = ""


            df.at[
                index,
                "Image File"
            ] = ""


            not_found += 1


            print(
                "      STATUS:"
                " NO VERIFIED IMAGE FOUND"
            )


        # ----------------------------------------------------
        # SMALL DELAY
        # ----------------------------------------------------

        time.sleep(
            0.4
        )


    # ========================================================
    # SAVE OUTPUT
    # ========================================================

    print()
    print("=" * 70)
    print(
        "SAVING RESULTS"
    )
    print("=" * 70)
    print()


    try:

        summary_df = pd.read_excel(
            EXCEL_FILE,
            sheet_name=SUMMARY_SHEET,
            header=None
        )

    except Exception:

        summary_df = None


    try:

        with pd.ExcelWriter(
            OUTPUT_FILE,
            engine="openpyxl"
        ) as writer:

            df.to_excel(
                writer,
                sheet_name=SHEET_NAME,
                index=False
            )


            if summary_df is not None:

                summary_df.to_excel(
                    writer,
                    sheet_name=SUMMARY_SHEET,
                    index=False,
                    header=False
                )

    except Exception as error:

        print(
            "ERROR saving Excel:"
        )

        print(error)

        return


    # ========================================================
    # FINAL REPORT
    # ========================================================

    print()
    print("=" * 70)
    print(
        "IMAGE SEARCH COMPLETE"
    )
    print("=" * 70)
    print()

    print(
        f"Total vehicles : {total}"
    )

    print(
        f"Verified       : {verified}"
    )

    print(
        f"Not found      : {not_found}"
    )

    print()

    print(
        "Output:"
    )

    print(
        OUTPUT_FILE
    )

    print()

    print(
        "Only image URLs that were actually"
    )

    print(
        "validated as image responses were"
    )

    print(
        "marked as Verified."
    )

    print()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
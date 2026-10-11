import os
import re
import sqlite3
import time
import html
import urllib.request
import urllib.error
from urllib.parse import urljoin, urlparse

import openpyxl


# ============================================================
# MOTOR NATION
# RESOLVE CURRENT CAR AND DRIVER IMAGES FOR ALL 455 VEHICLES
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

EXCEL_FILE = os.path.join(
    BASE_DIR,
    "excel",
    "USA_Master_Car_Catalog_2026_with_Images_Reviews_Pros_Cons.xlsx"
)

DATABASE_FILE = os.path.join(
    BASE_DIR,
    "database",
    "motornation.db"
)

IMAGE_DIR = os.path.join(
    BASE_DIR,
    "static",
    "images"
)

SHEET_NAME = "Master 2026-2027 US Catalog"

TIMEOUT = 20

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/154.0.0.0 Safari/537.36"
)


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


def safe_filename(value):
    value = clean_text(value)

    value = re.sub(
        r'[<>:"/\\|?*]',
        "",
        value
    )

    value = re.sub(
        r"\s+",
        "_",
        value
    )

    value = re.sub(
        r"_+",
        "_",
        value
    )

    return value.strip("_")


def normalize_url(url):
    if not url:
        return ""

    url = html.unescape(url)

    url = url.replace(
        "\\/",
        "/"
    )

    url = url.strip(
        "\"' "
    )

    return url


# ============================================================
# HTTP
# ============================================================

def fetch_page(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT
    ) as response:

        data = response.read()

        charset = response.headers.get_content_charset()

        if charset:
            try:
                return data.decode(
                    charset,
                    errors="ignore"
                )
            except:
                pass

        return data.decode(
            "utf-8",
            errors="ignore"
        )


def fetch_image(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "image/avif,image/webp,image/apng,"
                "image/svg+xml,image/*,*/*;q=0.8"
            ),
            "Referer": "https://www.caranddriver.com/"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT
    ) as response:

        content_type = (
            response.headers.get(
                "Content-Type",
                ""
            )
            .lower()
        )

        data = response.read()

        if not data:
            raise ValueError(
                "Empty image response"
            )

        if (
            "text/html" in content_type
            or "application/json" in content_type
        ):
            raise ValueError(
                f"Not an image: {content_type}"
            )

        return data, content_type


# ============================================================
# IMAGE VALIDATION
# ============================================================

def is_image(data, content_type):

    content_type = clean_text(
        content_type
    ).lower()

    if content_type.startswith("image/"):
        return True

    if data[:3] == b"\xff\xd8\xff":
        return True

    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return True

    if data[:6] in (
        b"GIF87a",
        b"GIF89a"
    ):
        return True

    if (
        len(data) >= 12
        and data[:4] == b"RIFF"
        and data[8:12] == b"WEBP"
    ):
        return True

    if (
        len(data) >= 12
        and data[4:8] == b"ftyp"
    ):
        return True

    return False


def image_extension(url, content_type):

    content_type = clean_text(
        content_type
    ).lower()

    if "jpeg" in content_type:
        return ".jpg"

    if "jpg" in content_type:
        return ".jpg"

    if "png" in content_type:
        return ".png"

    if "webp" in content_type:
        return ".webp"

    if "gif" in content_type:
        return ".gif"

    if "avif" in content_type:
        return ".avif"

    path = urlparse(url).path.lower()

    if path.endswith(".jpeg"):
        return ".jpg"

    if path.endswith(".jpg"):
        return ".jpg"

    if path.endswith(".png"):
        return ".png"

    if path.endswith(".webp"):
        return ".webp"

    if path.endswith(".gif"):
        return ".gif"

    if path.endswith(".avif"):
        return ".avif"

    return ".jpg"


# ============================================================
# EXTRACT IMAGE URLS FROM CAR AND DRIVER HTML
# ============================================================

def extract_image_urls(page_url, page_html):

    candidates = []

    # --------------------------------------------------------
    # 1. Open Graph image
    # --------------------------------------------------------

    og_patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']'
    ]

    for pattern in og_patterns:

        matches = re.findall(
            pattern,
            page_html,
            flags=re.IGNORECASE
        )

        for match in matches:

            image_url = normalize_url(
                match
            )

            if image_url:
                candidates.append(
                    urljoin(
                        page_url,
                        image_url
                    )
                )

    # --------------------------------------------------------
    # 2. All Hearst image URLs embedded in page
    # --------------------------------------------------------

    hearst_patterns = [
        r'https://hips\.hearstapps\.com/[^"\'<>\s]+',
        r'https:\\/\\/hips\.hearstapps\.com\\/[^"\'<>\s]+'
    ]

    for pattern in hearst_patterns:

        matches = re.findall(
            pattern,
            page_html,
            flags=re.IGNORECASE
        )

        for match in matches:

            image_url = normalize_url(
                match
            )

            image_url = image_url.replace(
                "&amp;",
                "&"
            )

            if image_url:
                candidates.append(
                    image_url
                )

    # --------------------------------------------------------
    # 3. src/srcset image URLs
    # --------------------------------------------------------

    src_patterns = [
        r'<img[^>]+src=["\']([^"\']+)',
        r'<img[^>]+srcset=["\']([^"\']+)'
    ]

    for pattern in src_patterns:

        matches = re.findall(
            pattern,
            page_html,
            flags=re.IGNORECASE
        )

        for match in matches:

            # srcset can contain:
            # url 640w, url 1280w
            parts = match.split(",")

            for part in parts:

                part = part.strip()

                if not part:
                    continue

                image_url = part.split()[0]

                image_url = normalize_url(
                    image_url
                )

                if (
                    "hearstapps.com" in image_url
                    or image_url.startswith("http")
                ):

                    candidates.append(
                        urljoin(
                            page_url,
                            image_url
                        )
                    )

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    unique = []

    seen = set()

    for url in candidates:

        url = normalize_url(
            url
        )

        if not url:
            continue

        if url in seen:
            continue

        seen.add(url)

        unique.append(
            url
        )

    return unique


# ============================================================
# FIND WORKING IMAGE
# ============================================================

def find_working_image(
    review_url,
    year,
    make,
    model
):

    if not review_url:
        return "", "No Review URL"

    print(
        f"      Page: {review_url}"
    )

    try:

        page_html = fetch_page(
            review_url
        )

    except Exception as error:

        return (
            "",
            f"Page failed: {error}"
        )

    candidates = extract_image_urls(
        review_url,
        page_html
    )

    print(
        f"      Image candidates found: {len(candidates)}"
    )

    if not candidates:

        return (
            "",
            "No image URLs found on page"
        )

    # --------------------------------------------------------
    # Score candidates
    # --------------------------------------------------------

    target_text = (
        f"{year} {make} {model}"
        .lower()
    )

    scored = []

    for index, url in enumerate(
        candidates
    ):

        lower = url.lower()

        score = 0

        # Vehicle terms
        for word in [
            str(year).lower(),
            make.lower(),
            model.lower()
        ]:

            if word and word in lower:
                score += 10

        # Car image indicators
        if "hmg-prod" in lower:
            score += 5

        if "images" in lower:
            score += 3

        # Avoid obvious non-car assets
        bad_words = [
            "logo",
            "icon",
            "avatar",
            "author",
            "facebook",
            "twitter",
            "instagram",
            "video",
            "sprite",
            "placeholder",
            "favicon"
        ]

        for bad in bad_words:

            if bad in lower:
                score -= 50

        scored.append(
            (
                score,
                index,
                url
            )
        )

    scored.sort(
        reverse=True
    )

    # --------------------------------------------------------
    # Try best candidates
    # --------------------------------------------------------

    attempts = 0

    for score, index, url in scored:

        if attempts >= 8:
            break

        attempts += 1

        print(
            f"      Testing image {attempts}:"
        )

        print(
            f"      {url}"
        )

        try:

            data, content_type = fetch_image(
                url
            )

            if not is_image(
                data,
                content_type
            ):

                print(
                    "      Not a valid image"
                )

                continue

            print(
                "      WORKING IMAGE FOUND"
            )

            return (
                url,
                ""
            )

        except Exception as error:

            print(
                f"      Failed: {error}"
            )

    return (
        "",
        "No working image found"
    )


# ============================================================
# DATABASE MATCH
# ============================================================

def update_database_image(
    cursor,
    year,
    make,
    model,
    trim,
    web_path
):

    # --------------------------------------------------------
    # First try exact vehicle
    # --------------------------------------------------------

    cursor.execute(
        """
        UPDATE vehicles
        SET "Image URL" = ?,
            "Image" = ?
        WHERE "Year" = ?
          AND "Make" = ?
          AND "Model / Model Group" = ?
          AND "Trim / Variant" = ?
        """,
        (
            web_path,
            web_path,
            year,
            make,
            model,
            trim
        )
    )

    if cursor.rowcount > 0:
        return cursor.rowcount

    # --------------------------------------------------------
    # Then model-level match
    # --------------------------------------------------------

    cursor.execute(
        """
        UPDATE vehicles
        SET "Image URL" = ?,
            "Image" = ?
        WHERE "Year" = ?
          AND "Make" = ?
          AND "Model / Model Group" = ?
        """,
        (
            web_path,
            web_path,
            year,
            make,
            model
        )
    )

    return cursor.rowcount


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("MOTOR NATION")
    print("CURRENT IMAGE RESOLVER - ALL 455 VEHICLES")
    print("=" * 70)
    print()

    # --------------------------------------------------------
    # CHECK FILES
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

    if not os.path.exists(
        DATABASE_FILE
    ):

        print(
            "ERROR: Database not found:"
        )

        print(
            DATABASE_FILE
        )

        return

    os.makedirs(
        IMAGE_DIR,
        exist_ok=True
    )

    # --------------------------------------------------------
    # OPEN EXCEL
    # --------------------------------------------------------

    print(
        "Opening Excel..."
    )

    workbook = openpyxl.load_workbook(
        EXCEL_FILE,
        read_only=True,
        data_only=True
    )

    print(
        f"Using sheet: {SHEET_NAME}"
    )

    worksheet = workbook[
        SHEET_NAME
    ]

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    header_row = 3

    headers = [
        clean_text(cell.value)
        for cell in worksheet[header_row]
    ]

    header_map = {}

    for index, header in enumerate(
        headers,
        start=1
    ):

        if header:
            header_map[header] = index

    print()
    print(
        "Required columns:"
    )

    for column in [
        "Year",
        "Make",
        "Model / Model Group",
        "Trim / Variant",
        "Image URL",
        "Review URL"
    ]:

        print(
            f" - {column}: "
            f"{'FOUND' if column in header_map else 'MISSING'}"
        )

    # --------------------------------------------------------
    # READ VEHICLES
    # --------------------------------------------------------

    vehicles = []

    for excel_row, row in enumerate(
        worksheet.iter_rows(
            min_row=header_row + 1,
            values_only=True
        ),
        start=header_row + 1
    ):

        year = clean_text(
            row[
                header_map["Year"] - 1
            ]
        )

        make = clean_text(
            row[
                header_map["Make"] - 1
            ]
        )

        model = clean_text(
            row[
                header_map["Model / Model Group"] - 1
            ]
        )

        trim = clean_text(
            row[
                header_map["Trim / Variant"] - 1
            ]
        )

        old_image_url = clean_text(
            row[
                header_map["Image URL"] - 1
            ]
        )

        review_url = ""

        if "Review URL" in header_map:

            review_url = clean_text(
                row[
                    header_map["Review URL"] - 1
                ]
            )

        if not make and not model:
            continue

        vehicles.append(
            {
                "excel_row": excel_row,
                "year": year,
                "make": make,
                "model": model,
                "trim": trim,
                "old_image_url": old_image_url,
                "review_url": review_url
            }
        )

    workbook.close()

    print()
    print(
        f"Vehicle rows found: {len(vehicles)}"
    )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    # Make sure columns exist
    cursor.execute(
        "PRAGMA table_info(vehicles)"
    )

    database_columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    if "Image URL" not in database_columns:

        cursor.execute(
            """
            ALTER TABLE vehicles
            ADD COLUMN "Image URL" TEXT
            """
        )

    if "Image" not in database_columns:

        cursor.execute(
            """
            ALTER TABLE vehicles
            ADD COLUMN "Image" TEXT
            """
        )

    connection.commit()

    # --------------------------------------------------------
    # CACHE
    # --------------------------------------------------------

    page_cache = {}

    image_cache = {}

    successful = 0
    failed = 0

    failures = []

    print()
    print("=" * 70)
    print("RESOLVING CURRENT IMAGES")
    print("=" * 70)

    # --------------------------------------------------------
    # PROCESS VEHICLES
    # --------------------------------------------------------

    for position, vehicle in enumerate(
        vehicles,
        start=1
    ):

        year = vehicle["year"]
        make = vehicle["make"]
        model = vehicle["model"]
        trim = vehicle["trim"]
        review_url = vehicle["review_url"]

        print()
        print(
            f"[{position}/{len(vehicles)}] "
            f"{year} {make} {model}"
        )

        if trim:
            print(
                f"      Trim: {trim}"
            )

        # ----------------------------------------------------
        # No review URL
        # ----------------------------------------------------

        if not review_url:

            print(
                "      NO REVIEW URL"
            )

            failed += 1

            failures.append(
                {
                    "vehicle": (
                        f"{year} {make} {model} {trim}"
                    ),
                    "error": "No Review URL"
                }
            )

            continue

        # ----------------------------------------------------
        # Same review URL = same base vehicle image
        # ----------------------------------------------------

        cache_key = review_url

        if cache_key in image_cache:

            image_url = image_cache[
                cache_key
            ]

            print(
                "      Using cached image"
            )

        else:

            image_url, error = find_working_image(
                review_url,
                year,
                make,
                model
            )

            if image_url:

                image_cache[
                    cache_key
                ] = image_url

            else:

                image_cache[
                    cache_key
                ] = ""

                print(
                    f"      IMAGE FAILED: {error}"
                )

        # ----------------------------------------------------
        # FAILURE
        # ----------------------------------------------------

        if not image_url:

            failed += 1

            failures.append(
                {
                    "vehicle": (
                        f"{year} {make} {model} {trim}"
                    ),
                    "error": "No working image"
                }
            )

            time.sleep(0.5)

            continue

        # ----------------------------------------------------
        # DOWNLOAD IMAGE
        # ----------------------------------------------------

        filename_base = "_".join(
            [
                safe_filename(year),
                safe_filename(make),
                safe_filename(model)
            ]
        )

        filename_base = filename_base[
            :180
        ]

        # Avoid duplicate download
        existing_file = None

        for extension in [
            ".jpg",
            ".png",
            ".webp",
            ".gif",
            ".avif"
        ]:

            candidate = os.path.join(
                IMAGE_DIR,
                filename_base + extension
            )

            if os.path.exists(
                candidate
            ):

                existing_file = candidate
                break

        if existing_file:

            local_file = existing_file

            print(
                "      Local image already exists"
            )

        else:

            try:

                data, content_type = fetch_image(
                    image_url
                )

                if not is_image(
                    data,
                    content_type
                ):

                    raise ValueError(
                        "Downloaded data is not an image"
                    )

                extension = image_extension(
                    image_url,
                    content_type
                )

                local_file = os.path.join(
                    IMAGE_DIR,
                    filename_base + extension
                )

                with open(
                    local_file,
                    "wb"
                ) as file:

                    file.write(
                        data
                    )

                print(
                    f"      SAVED: {local_file}"
                )

            except Exception as error:

                print(
                    f"      DOWNLOAD FAILED: {error}"
                )

                failed += 1

                failures.append(
                    {
                        "vehicle": (
                            f"{year} {make} {model} {trim}"
                        ),
                        "error": str(error)
                    }
                )

                time.sleep(0.5)

                continue

        # ----------------------------------------------------
        # WEB PATH
        # ----------------------------------------------------

        local_filename = os.path.basename(
            local_file
        )

        web_path = (
            "/static/images/"
            + local_filename
        )

        # ----------------------------------------------------
        # DATABASE
        # ----------------------------------------------------

        updated = update_database_image(
            cursor,
            year,
            make,
            model,
            trim,
            web_path
        )

        connection.commit()

        print(
            f"      DATABASE: {web_path}"
        )

        print(
            f"      Rows updated: {updated}"
        )

        successful += 1

        # Small delay
        time.sleep(0.25)

    # --------------------------------------------------------
    # FINAL DATABASE CHECK
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM vehicles
        """
    )

    total_database = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM vehicles
        WHERE "Image URL" LIKE '/static/images/%'
        """
    )

    local_images = cursor.fetchone()[0]

    connection.commit()
    connection.close()

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("FINAL IMAGE REPORT")
    print("=" * 70)
    print()

    print(
        f"Excel vehicle rows:       {len(vehicles)}"
    )

    print(
        f"Database vehicles:        {total_database}"
    )

    print(
        f"Images successfully set:  {successful}"
    )

    print(
        f"Images failed:            {failed}"
    )

    print(
        f"Local image paths in DB:  {local_images}"
    )

    print()

    print(
        "Image directory:"
    )

    print(
        IMAGE_DIR
    )

    # --------------------------------------------------------
    # FAILURE REPORT
    # --------------------------------------------------------

    if failures:

        failure_file = os.path.join(
            BASE_DIR,
            "image_download_failures.txt"
        )

        with open(
            failure_file,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(
                "MOTOR NATION IMAGE FAILURES\n"
            )

            file.write(
                "=" * 70
                + "\n\n"
            )

            for failure in failures:

                file.write(
                    f"Vehicle: {failure['vehicle']}\n"
                )

                file.write(
                    f"Error: {failure['error']}\n"
                )

                file.write(
                    "-" * 70
                    + "\n"
                )

        print()
        print(
            f"Failure report: {failure_file}"
        )

    else:

        print()
        print(
            "ALL VEHICLES HAVE WORKING LOCAL IMAGES."
        )

    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
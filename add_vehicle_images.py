import sqlite3
import pandas as pd
from pathlib import Path

# ============================================================
# MOTOR NATION
# IMPORT IMAGE URLS FROM EXCEL INTO SQLITE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

EXCEL_FILE = (
    BASE_DIR
    / "excel"
    / "MotorNation_Master.xlsx"
)

DATABASE_FILE = (
    BASE_DIR
    / "database"
    / "motornation.db"
)

SHEET_NAME = "Master 2026-2027 US Catalog"


# ============================================================
# CLEAN VALUE
# ============================================================

def clean_value(value):

    if pd.isna(value):
        return ""

    return str(value).strip()


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("MOTORNATION - IMPORT IMAGE URLS FROM EXCEL")
    print("=" * 70)
    print()

    # --------------------------------------------------------
    # Check Excel
    # --------------------------------------------------------

    if not EXCEL_FILE.exists():

        print("ERROR: Excel file not found:")
        print(EXCEL_FILE)

        return

    print("Excel file:")
    print(EXCEL_FILE)
    print()

    # --------------------------------------------------------
    # Read Excel
    #
    # Your vehicle headers start on row 3,
    # therefore pandas header=2
    # --------------------------------------------------------

    df = pd.read_excel(
        EXCEL_FILE,
        sheet_name=SHEET_NAME,
        header=2
    )

    # Clean column names

    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

    print("Excel columns:")
    print()

    for column in df.columns:
        print(" -", column)

    print()

    # --------------------------------------------------------
    # Find required columns
    # --------------------------------------------------------

    image_column = None
    make_column = None
    model_column = None
    year_column = None

    for column in df.columns:

        column_lower = column.lower()

        if column_lower == "image url":
            image_column = column

        if column_lower == "make":
            make_column = column

        if (
            column_lower == "model"
            or column_lower == "model / model group"
        ):
            model_column = column

        if column_lower == "year":
            year_column = column

    # --------------------------------------------------------
    # Check Image URL
    # --------------------------------------------------------

    if image_column is None:

        print()
        print(
            "ERROR: Image URL column was not found."
        )

        print()
        print(
            "Available columns:"
        )

        for column in df.columns:
            print(column)

        return

    print(
        "Image column found:",
        image_column
    )

    print()

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    if not DATABASE_FILE.exists():

        print(
            "ERROR: SQLite database not found:"
        )

        print(
            DATABASE_FILE
        )

        return

    db = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = db.cursor()

    # --------------------------------------------------------
    # Check database columns
    # --------------------------------------------------------

    database_columns = [

        row[1]

        for row in cursor.execute(
            "PRAGMA table_info(vehicles)"
        ).fetchall()

    ]

    print(
        "Database columns:"
    )

    for column in database_columns:
        print(" -", column)

    print()

    # --------------------------------------------------------
    # Add Image columns if missing
    # --------------------------------------------------------

    if "Image" not in database_columns:

        cursor.execute(
            'ALTER TABLE vehicles ADD COLUMN "Image" TEXT'
        )

        print(
            "Added database column: Image"
        )

    if "Image URL" not in database_columns:

        cursor.execute(
            'ALTER TABLE vehicles ADD COLUMN "Image URL" TEXT'
        )

        print(
            "Added database column: Image URL"
        )

    db.commit()

    print()

    # --------------------------------------------------------
    # Get database vehicles
    # --------------------------------------------------------

    database_rows = cursor.execute(
        """
        SELECT
            vehicle_id,
            Make,
            "Model / Model Group",
            Year
        FROM vehicles
        ORDER BY vehicle_id
        """
    ).fetchall()

    print(
        "Vehicles in database:",
        len(database_rows)
    )

    print(
        "Rows in Excel:",
        len(df)
    )

    print()

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    imported = 0
    skipped = 0
    not_found = 0

    # ========================================================
    # MATCH EXCEL → DATABASE
    # ========================================================

    for index, db_vehicle in enumerate(
        database_rows,
        start=1
    ):

        vehicle_id = db_vehicle[0]

        db_make = clean_value(
            db_vehicle[1]
        )

        db_model = clean_value(
            db_vehicle[2]
        )

        db_year = clean_value(
            db_vehicle[3]
        )

        print(
            f"[{index}/{len(database_rows)}] "
            f"{db_make} {db_model}"
        )

        # ----------------------------------------------------
        # Find matching Excel row
        # ----------------------------------------------------

        matches = df.copy()

        if make_column:

            matches = matches[
                matches[make_column]
                .astype(str)
                .str.strip()
                .str.lower()
                == db_make.lower()
            ]

        if model_column:

            matches = matches[
                matches[model_column]
                .astype(str)
                .str.strip()
                .str.lower()
                == db_model.lower()
            ]

        # ----------------------------------------------------
        # Match year when possible
        # ----------------------------------------------------

        if (
            year_column
            and db_year
            and db_year.lower() != "nan"
        ):

            year_matches = matches[
                matches[year_column]
                .astype(str)
                .str.replace(
                    ".0",
                    "",
                    regex=False
                )
                .str.strip()
                == db_year
            ]

            if not year_matches.empty:

                matches = year_matches

        # ----------------------------------------------------
        # No match
        # ----------------------------------------------------

        if matches.empty:

            print(
                "   No matching Excel row"
            )

            not_found += 1

            continue

        # ----------------------------------------------------
        # Get Image URL
        # ----------------------------------------------------

        image_url = clean_value(
            matches.iloc[0][image_column]
        )

        if not image_url:

            print(
                "   Excel image URL is empty"
            )

            not_found += 1

            continue

        # ----------------------------------------------------
        # Save Image URL
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE vehicles

            SET
                "Image" = ?,
                "Image URL" = ?

            WHERE vehicle_id = ?
            """,
            (
                image_url,
                image_url,
                vehicle_id
            )
        )

        db.commit()

        print(
            "   IMAGE URL SAVED"
        )

        print(
            "   ",
            image_url
        )

        imported += 1

    # ========================================================
    # CLOSE DATABASE
    # ========================================================

    db.close()

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 70)
    print("IMPORT COMPLETE")
    print("=" * 70)

    print(
        "Vehicles:",
        len(database_rows)
    )

    print(
        "Image URLs imported:",
        imported
    )

    print(
        "No image URL:",
        not_found
    )

    print()

    print(
        "Database:"
    )

    print(
        DATABASE_FILE
    )

    print()

    print(
        "Next command:"
    )

    print(
        "python app.py"
    )

    print()

    print(
        "Then open:"
    )

    print(
        "http://127.0.0.1:5000/cars"
    )

    print()


if __name__ == "__main__":

    main()
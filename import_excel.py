from pathlib import Path
import sqlite3
import pandas as pd


# ============================================================
# MOTOR NATION - EXCEL TO SQLITE IMPORTER
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

EXCEL_FILE = (
    BASE_DIR
    / "excel"
    / "USA_Master_Car_Catalog_2026_with_Images_Reviews_Pros_Cons.xlsx"
)

DATABASE_DIR = BASE_DIR / "database"
DATABASE_FILE = DATABASE_DIR / "motornation.db"


# ============================================================
# CHECK EXCEL FILE
# ============================================================

print()
print("=" * 70)
print("MOTOR NATION - VEHICLE DATABASE IMPORT")
print("=" * 70)
print()

if not EXCEL_FILE.exists():

    print("ERROR: Excel file was not found.")
    print()
    print(EXCEL_FILE)
    print()

    raise SystemExit(1)


print("Excel file:")
print(EXCEL_FILE)
print()


# ============================================================
# CREATE DATABASE FOLDER
# ============================================================

DATABASE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# LOAD EXCEL
# ============================================================

print("Reading Excel workbook...")
print()

excel_file = pd.ExcelFile(
    EXCEL_FILE
)

print("Sheets found:")

for sheet in excel_file.sheet_names:
    print(" -", sheet)

print()


# ============================================================
# FIND MASTER SHEET
# ============================================================

master_sheet = None

for sheet in excel_file.sheet_names:

    sheet_lower = sheet.lower()

    if (
        "master" in sheet_lower
        or "catalog" in sheet_lower
        or "vehicle" in sheet_lower
    ):

        master_sheet = sheet
        break


if master_sheet is None:

    master_sheet = excel_file.sheet_names[0]


print("Using sheet:")
print(master_sheet)
print()


# ============================================================
# READ DATA
# ============================================================

print("Reading vehicle data...")

df = pd.read_excel(
    EXCEL_FILE,
    sheet_name=master_sheet,
    header=2
)


# ============================================================
# CLEAN COLUMN NAMES
# ============================================================

df.columns = [
    str(column).strip()
    for column in df.columns
]


# Remove completely empty columns
df = df.dropna(
    axis=1,
    how="all"
)


# Remove completely empty rows
df = df.dropna(
    axis=0,
    how="all"
)


# Reset index
df = df.reset_index(
    drop=True
)


# ============================================================
# DISPLAY COLUMNS
# ============================================================

print()
print("Columns found:")
print()

for column in df.columns:
    print(" -", column)

print()


# ============================================================
# FIND IMAGE COLUMN
# ============================================================

image_column = None

possible_image_columns = [
    "Image URL",
    "Image URL(s)",
    "Image",
    "Photo URL",
    "Photo",
    "ImageURL"
]

for column in possible_image_columns:

    if column in df.columns:

        image_column = column
        break


if image_column is None:

    print()
    print("WARNING:")
    print("No Image URL column was found.")
    print()

else:

    print(
        "Image column detected:",
        image_column
    )

    image_count = (
        df[image_column]
        .notna()
        .sum()
    )

    print(
        "Rows containing image URLs:",
        image_count
    )

    print()


# ============================================================
# NORMALIZE IMAGE COLUMN
# ============================================================

if image_column is not None:

    df[image_column] = (
        df[image_column]
        .fillna("")
        .astype(str)
        .str.strip()
    )


# ============================================================
# CREATE DATABASE
# ============================================================

print("Opening SQLite database...")

connection = sqlite3.connect(
    DATABASE_FILE
)


# ============================================================
# IMPORT TABLE
# ============================================================

print("Importing vehicles...")

df.to_sql(
    "vehicles",
    connection,
    if_exists="replace",
    index=False
)


# ============================================================
# ADD VEHICLE ID
# ============================================================

cursor = connection.cursor()


# Check existing columns
cursor.execute(
    "PRAGMA table_info(vehicles)"
)

columns = [
    row[1]
    for row in cursor.fetchall()
]


if "vehicle_id" not in columns:

    cursor.execute(
        """
        ALTER TABLE vehicles
        ADD COLUMN vehicle_id INTEGER
        """
    )


# Populate vehicle IDs
cursor.execute(
    """
    UPDATE vehicles
    SET vehicle_id = rowid
    """
)


# ============================================================
# CREATE INDEXES
# ============================================================

if "Make" in columns:

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_vehicles_make
        ON vehicles("Make")
        """
    )


if "Model / Model Group" in columns:

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_vehicles_model
        ON vehicles("Model / Model Group")
        """
    )


if "Body Type" in columns:

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_vehicles_body
        ON vehicles("Body Type")
        """
    )


if "Fuel Type" in columns:

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_vehicles_fuel
        ON vehicles("Fuel Type")
        """
    )


# ============================================================
# SAVE
# ============================================================

connection.commit()


# ============================================================
# VERIFY DATABASE
# ============================================================

cursor.execute(
    "SELECT COUNT(*) FROM vehicles"
)

vehicle_count = cursor.fetchone()[0]


# Count images
if image_column is not None:

    cursor.execute(
        f'''
        SELECT COUNT(*)
        FROM vehicles
        WHERE "{image_column}" IS NOT NULL
        AND TRIM("{image_column}") != ''
        '''
    )

    image_count_database = cursor.fetchone()[0]

else:

    image_count_database = 0


# ============================================================
# CLOSE
# ============================================================

connection.close()


# ============================================================
# RESULT
# ============================================================

print()
print("=" * 70)
print("IMPORT COMPLETE")
print("=" * 70)
print()

print(
    "Vehicles imported:",
    vehicle_count
)

print(
    "Vehicles with image URLs:",
    image_count_database
)

print()

print("Database:")
print(DATABASE_FILE)

print()

print("Image column:")
print(image_column)

print()

print("=" * 70)
print("DONE")
print("=" * 70)
print()
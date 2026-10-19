"""
Script to replace 455 cars data with temporary 15 cars data.
In-place replacement without deleting files.
Creates backup of 455 dataset first.
"""
import sqlite3
import json
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "database" / "motornation.db"
DB_BACKUP = BASE_DIR / "database" / "motornation_455_backup.db"
NR_FILE = BASE_DIR / "data" / "news_and_reviews.json"
NR_BACKUP = BASE_DIR / "data" / "news_and_reviews_455_backup.json"
GALLERIES_FILE = BASE_DIR / "data" / "vehicle_galleries.json"
VIDEOS_FILE = BASE_DIR / "data" / "car_videos_mapping.json"

print("1. Creating backups of 455 dataset...")
if not DB_BACKUP.exists():
    shutil.copy2(DB_FILE, DB_BACKUP)
    print(f"Backed up {DB_FILE} -> {DB_BACKUP}")
else:
    print(f"Backup already exists at {DB_BACKUP}")

if not NR_BACKUP.exists():
    shutil.copy2(NR_FILE, NR_BACKUP)
    print(f"Backed up {NR_FILE} -> {NR_BACKUP}")
else:
    print(f"Backup already exists at {NR_BACKUP}")

# The 15 chosen cars representing 10 body styles, all price brackets and fuels
# Original IDs:
SELECTED_ORIGINAL_IDS = [
    1,    # Acura Integra (Compact Liftback / Sedans, $38,000)
    13,   # Aston Martin Vantage (Grand Tourer Coupe / Luxury, $194,400)
    25,   # Audi RS6 Avant (Performance Wagon, $128,895)
    43,   # BMW M2 (Performance Sport Coupe / Coupe, $66,075)
    73,   # Cadillac Escalade (Full-Size Performance SUV, $154,290)
    89,   # Chevrolet Corvette (Sports Car / Coupe, $70,000)
    109,  # Ford F-150 (Full-Size Pickup, $56,100)
    117,  # Ford Mustang (V8 Muscle Car / Coupe, $48,000)
    142,  # Honda Civic (Hot Hatchback, $46,690)
    161,  # Hyundai Ioniq 5 N (High-Performance EV Hatch / Electric, $67,475)
    186,  # Kia Carnival (Minivan / MUV / Hybrid, $54,000)
    238,  # Mercedes-Benz C-Class (Compact Executive Sedan / Sedans / Luxury, $49,500)
    282,  # Porsche 718 Boxster (Mid-Engine Roadster / Convertible, $99,500)
    318,  # Tesla Model 3 (Compact Luxury EV Sport Sedan / Electric, $54,990)
    330,  # Toyota Camry (Mid-Size Sedan / Sedans / Hybrid, $34,495)
]

# ID mapping: old ID -> new ID (1..15)
ID_MAP = {old_id: new_id for new_id, old_id in enumerate(SELECTED_ORIGINAL_IDS, start=1)}
REVERSE_MAP = {new_id: old_id for old_id, new_id in ID_MAP.items()}

print("2. Extracting selected cars from SQLite database...")
conn = sqlite3.connect(DB_FILE)
conn.row_factory = sqlite3.Row
c = conn.cursor()

placeholders = ",".join("?" * len(SELECTED_ORIGINAL_IDS))
c.execute(f"SELECT * FROM vehicles WHERE vehicle_id IN ({placeholders}) ORDER BY vehicle_id", SELECTED_ORIGINAL_IDS)
db_rows = [dict(row) for row in c.fetchall()]

# Re-order according to SELECTED_ORIGINAL_IDS order
db_rows_sorted = []
for old_id in SELECTED_ORIGINAL_IDS:
    match = next((r for r in db_rows if r.get("vehicle_id") == old_id), None)
    if match:
        db_rows_sorted.append(match)

print(f"Extracted {len(db_rows_sorted)} rows from database.")

# Update vehicle_id to 1..15
for idx, row in enumerate(db_rows_sorted, start=1):
    row["vehicle_id"] = idx

print("3. Replacing records in vehicles table in-place...")
# Clear table and insert the 15 records
c.execute("DELETE FROM vehicles")
cols = list(db_rows_sorted[0].keys())
col_names = ", ".join(f'"{col}"' for col in cols)
col_placeholders = ", ".join("?" * len(cols))

insert_sql = f"INSERT INTO vehicles ({col_names}) VALUES ({col_placeholders})"
for row in db_rows_sorted:
    c.execute(insert_sql, [row[col] for col in cols])

conn.commit()
c.execute("SELECT COUNT(*) FROM vehicles")
new_db_count = c.fetchone()[0]
print(f"New vehicle count in motornation.db: {new_db_count}")
conn.close()

print("4. Updating news_and_reviews.json in-place...")
with open(NR_BACKUP, "r", encoding="utf-8") as f:
    nr_full = json.load(f)

full_items = nr_full.get("items", [])
new_items = []
by_id = {}
by_key = {}

for new_id, old_id in enumerate(SELECTED_ORIGINAL_IDS, start=1):
    # Find item by old_id or vehicle_id
    item_match = next((item for item in full_items if item.get("id") == old_id or item.get("vehicle_id") == old_id), None)
    if item_match:
        item_copy = dict(item_match)
        item_copy["id"] = new_id
        item_copy["vehicle_id"] = new_id
        new_items.append(item_copy)
        by_id[str(new_id)] = item_copy
        by_id[str(old_id)] = item_copy # keep backward compatibility
        key = f"{item_copy.get('make', '')}_{item_copy.get('model', '')}".lower()
        by_key[key] = item_copy

new_nr_data = {
    "count": len(new_items),
    "items": new_items,
    "by_id": by_id,
    "by_key": by_key
}

with open(NR_FILE, "w", encoding="utf-8") as f:
    json.dump(new_nr_data, f, indent=2, ensure_ascii=False)
print(f"Updated news_and_reviews.json with {len(new_items)} items.")

print("5. Updating vehicle_galleries.json mappings...")
if GALLERIES_FILE.exists():
    with open(GALLERIES_FILE, "r", encoding="utf-8") as f:
        galleries = json.load(f)
    
    # Ensure keys for 1..15 exist
    for new_id, old_id in enumerate(SELECTED_ORIGINAL_IDS, start=1):
        old_key = str(old_id)
        new_key = str(new_id)
        if old_key in galleries and new_key not in galleries:
            galleries[new_key] = galleries[old_key]
    
    with open(GALLERIES_FILE, "w", encoding="utf-8") as f:
        json.dump(galleries, f, indent=2, ensure_ascii=False)
    print("Updated vehicle galleries mapping.")

print("6. Updating car_videos_mapping.json mappings...")
if VIDEOS_FILE.exists():
    with open(VIDEOS_FILE, "r", encoding="utf-8") as f:
        videos = json.load(f)
    
    for new_id, old_id in enumerate(SELECTED_ORIGINAL_IDS, start=1):
        old_key = str(old_id)
        new_key = str(new_id)
        if old_key in videos:
            entry = dict(videos[old_key])
            entry["id"] = new_id
            videos[new_key] = entry
    
    with open(VIDEOS_FILE, "w", encoding="utf-8") as f:
        json.dump(videos, f, indent=2, ensure_ascii=False)
    print("Updated car videos mapping.")

print("Replacement complete! All files preserved in-place with 15 temporary cars.")

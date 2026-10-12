import sqlite3
import urllib.request
import re
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

DB_PATH = Path("database/motornation.db")
OUTPUT_FILE = Path("data/vehicle_galleries.json")
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

# Load existing cache if present
galleries_cache = {}
if OUTPUT_FILE.exists():
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            galleries_cache = json.load(f)
        print(f"Loaded {len(galleries_cache)} existing galleries from cache.")
    except Exception as e:
        print("Error loading cache:", e)

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    SELECT vehicle_id, Make, [Model / Model Group] as Model, [Trim / Variant] as Trim, Image, [Image URL] as ImageUrl, [Review URL] as ReviewUrl 
    FROM vehicles
""")
vehicles = [dict(r) for r in cursor.fetchall()]
conn.close()

print(f"Total vehicles in database: {len(vehicles)}")

# Unique review URLs to scrape
url_to_vehicles = {}
for v in vehicles:
    rurl = v.get("ReviewUrl")
    if rurl and "caranddriver.com" in rurl:
        url_to_vehicles.setdefault(rurl, []).append(v)

print(f"Unique review URLs to process: {len(url_to_vehicles)}")

def scrape_gallery(review_url, vlist):
    slug = review_url.rstrip("/").split("/")[-1].lower()
    make = vlist[0]["Make"]
    model = vlist[0]["Model"]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(review_url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            
            # Find high-res hearst images
            raw_imgs = set(re.findall(r"https://hips\.hearstapps\.com/hmg-prod/images/[a-zA-Z0-9_\-\.]+\.(?:jpg|jpeg|png|webp)", html))
            
            clean_slug = slug.replace("-", "").replace("_", "")
            model_words = [w.lower() for w in re.split(r"[\s\-_]+", model) if len(w) > 1]
            
            matched = []
            for img in raw_imgs:
                lower = img.lower()
                if any(bad in lower for bad in ["logo", "icon", "author", "avatar", "badge", "banner", "hearst-magazines", "hearst-autos", "illustration"]):
                    continue
                
                # Check slug or model match in image filename
                img_name = lower.split("/")[-1]
                slug_match = slug in img_name or clean_slug in img_name.replace("-", "").replace("_", "")
                model_match = any(w in img_name for w in model_words)
                
                if slug_match or model_match:
                    matched.append(img)
            
            # Categorize into Exterior, Interior, Details
            exterior = []
            interior = []
            details = []
            general = []
            
            for img in matched:
                lower = img.lower()
                high_res = f"{img}?resize=1200:*"
                
                if any(k in lower for k in ["interior", "cockpit", "cabin", "steering", "dash", "infotainment", "screen", "seat"]):
                    interior.append({
                        "url": high_res,
                        "caption": f"{make} {model} — Cockpit & Interior",
                        "category": "Interior"
                    })
                elif any(k in lower for k in ["rear", "back", "tail", "exhaust"]):
                    exterior.append({
                        "url": high_res,
                        "caption": f"{make} {model} — Rear Profile",
                        "category": "Exterior"
                    })
                elif any(k in lower for k in ["side", "profile"]):
                    exterior.append({
                        "url": high_res,
                        "caption": f"{make} {model} — Side Profile",
                        "category": "Exterior"
                    })
                elif any(k in lower for k in ["front", "grille", "headlight", "fascia"]):
                    exterior.append({
                        "url": high_res,
                        "caption": f"{make} {model} — Front Three-Quarter",
                        "category": "Exterior"
                    })
                elif any(k in lower for k in ["wheel", "brake", "engine", "badge", "exhaust", "detail"]):
                    details.append({
                        "url": high_res,
                        "caption": f"{make} {model} — Performance & Details",
                        "category": "Details"
                    })
                else:
                    general.append({
                        "url": high_res,
                        "caption": f"{make} {model} — View",
                        "category": "Exterior"
                    })
            
            # Combine balanced gallery: up to 3 exterior, up to 3 interior, details & general
            curated = []
            curated.extend(exterior[:3])
            curated.extend(interior[:3])
            curated.extend(details[:2])
            for g in general:
                if len(curated) >= 6:
                    break
                curated.append(g)
            
            return review_url, curated
    except Exception as e:
        return review_url, []

print("Starting concurrent gallery scraping...")
start_time = time.time()

# Determine which URLs need scraping
urls_to_scrape = [url for url in url_to_vehicles.keys() if url not in galleries_cache or not galleries_cache[url]]
print(f"URLs needing scraping: {len(urls_to_scrape)}")

with ThreadPoolExecutor(max_workers=14) as executor:
    futures = {executor.submit(scrape_gallery, url, url_to_vehicles[url]): url for url in urls_to_scrape}
    done_count = 0
    for fut in futures:
        url, gallery = fut.result()
        galleries_cache[url] = gallery
        done_count += 1
        if done_count % 30 == 0 or done_count == len(urls_to_scrape):
            print(f"Scraped {done_count}/{len(urls_to_scrape)} URLs ({time.time() - start_time:.1f}s)")

# Build vehicle-level lookup by vehicle_id and make_model
vehicle_galleries = {}
for v in vehicles:
    vid = str(v["vehicle_id"])
    make = v["Make"]
    model = v["Model"]
    key = f"{make}_{model}".lower()
    
    rurl = v.get("ReviewUrl")
    hearst_photos = galleries_cache.get(rurl, []) if rurl else []
    
    # Primary image is always the local image if available
    local_img = v.get("Image") or v.get("ImageUrl") or ""
    
    car_photos = []
    if local_img:
        car_photos.append({
            "url": local_img,
            "caption": f"{make} {model} — Main Exterior",
            "category": "Exterior"
        })
    
    # Add hearst photos (avoid duplicates)
    seen_urls = {local_img}
    for p in hearst_photos:
        u = p["url"]
        if u not in seen_urls:
            seen_urls.add(u)
            car_photos.append(p)
    
    # If still fewer than 2 photos, provide fallback high-def automotive category angles
    vehicle_galleries[vid] = car_photos
    vehicle_galleries[key] = car_photos

# Save to disk
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(vehicle_galleries, f, indent=2)

print(f"SUCCESS: Saved galleries for {len(vehicle_galleries)} vehicle keys to {OUTPUT_FILE}")
print(f"Total time elapsed: {time.time() - start_time:.2f} seconds.")

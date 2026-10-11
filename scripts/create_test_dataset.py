from pathlib import Path
import csv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "vehicles_raw.csv"
)


COLUMNS = [
    "id",
    "year",
    "make",
    "model",
    "trim",
    "variant",
    "body_type",
    "vehicle_type",
    "fuel_type",
    "engine",
    "engine_displacement",
    "engine_cylinders",
    "horsepower",
    "torque",
    "transmission",
    "drivetrain",
    "msrp",
    "destination_charge",
    "mpg_city",
    "mpg_highway",
    "mpg_combined",
    "ev_range",
    "plug_in_range",
    "seating",
    "cargo_capacity",
    "length",
    "width",
    "height",
    "wheelbase",
    "curb_weight",
    "towing_capacity",
    "description",
    "pros",
    "cons",
    "features",
    "image_url",
    "source_url",
    "source_name",
    "last_updated",
]


VEHICLES = [
    {
        "id": "202600001",
        "year": 2026,
        "make": "Toyota",
        "model": "Camry",
        "trim": "LE",
        "variant": "LE",
        "body_type": "Sedan",
        "vehicle_type": "Passenger Car",
        "fuel_type": "Gasoline",
        "engine": "2.5L 4-Cylinder",
        "engine_displacement": "2.5L",
        "engine_cylinders": 4,
        "horsepower": 225,
        "torque": 163,
        "transmission": "8-Speed Automatic",
        "drivetrain": "FWD",
        "msrp": 28400,
        "destination_charge": "",
        "mpg_city": 53,
        "mpg_highway": 50,
        "mpg_combined": 51,
        "ev_range": "",
        "plug_in_range": "",
        "seating": 5,
        "cargo_capacity": 15.1,
        "length": "",
        "width": "",
        "height": "",
        "wheelbase": "",
        "curb_weight": "",
        "towing_capacity": "",
        "description": "2026 Toyota Camry LE test record.",
        "pros": "Fuel-efficient; Comfortable; Reliable",
        "cons": "Test dataset record",
        "features": (
            "Toyota Safety Sense; "
            "Wireless Apple CarPlay; "
            "Wireless Android Auto"
        ),
        "image_url": "",
        "source_url": "https://www.toyota.com/camry/",
        "source_name": "Toyota",
        "last_updated": "2026-10-06",
    },
    {
        "id": "202600002",
        "year": 2026,
        "make": "Toyota",
        "model": "Camry",
        "trim": "SE",
        "variant": "SE",
        "body_type": "Sedan",
        "vehicle_type": "Passenger Car",
        "fuel_type": "Gasoline",
        "engine": "2.5L 4-Cylinder",
        "engine_displacement": "2.5L",
        "engine_cylinders": 4,
        "horsepower": 225,
        "torque": 163,
        "transmission": "8-Speed Automatic",
        "drivetrain": "FWD",
        "msrp": 30700,
        "destination_charge": "",
        "mpg_city": 48,
        "mpg_highway": 47,
        "mpg_combined": 47,
        "ev_range": "",
        "plug_in_range": "",
        "seating": 5,
        "cargo_capacity": 15.1,
        "length": "",
        "width": "",
        "height": "",
        "wheelbase": "",
        "curb_weight": "",
        "towing_capacity": "",
        "description": "2026 Toyota Camry SE test record.",
        "pros": "Sportier styling; Efficient; Good value",
        "cons": "Test dataset record",
        "features": (
            "Toyota Safety Sense; "
            "Wireless Apple CarPlay; "
            "Wireless Android Auto"
        ),
        "image_url": "",
        "source_url": "https://www.toyota.com/camry/",
        "source_name": "Toyota",
        "last_updated": "2026-10-06",
    },
    {
        "id": "202600003",
        "year": 2026,
        "make": "Toyota",
        "model": "Camry",
        "trim": "XLE",
        "variant": "XLE",
        "body_type": "Sedan",
        "vehicle_type": "Passenger Car",
        "fuel_type": "Hybrid",
        "engine": "2.5L 4-Cylinder Hybrid",
        "engine_displacement": "2.5L",
        "engine_cylinders": 4,
        "horsepower": 225,
        "torque": 163,
        "transmission": "eCVT",
        "drivetrain": "FWD",
        "msrp": 34000,
        "destination_charge": "",
        "mpg_city": 48,
        "mpg_highway": 47,
        "mpg_combined": 47,
        "ev_range": "",
        "plug_in_range": "",
        "seating": 5,
        "cargo_capacity": 15.1,
        "length": "",
        "width": "",
        "height": "",
        "wheelbase": "",
        "curb_weight": "",
        "towing_capacity": "",
        "description": "2026 Toyota Camry XLE test record.",
        "pros": "Premium interior; Excellent efficiency; Comfortable",
        "cons": "Test dataset record",
        "features": (
            "Toyota Safety Sense; "
            "Wireless Apple CarPlay; "
            "Wireless Android Auto"
        ),
        "image_url": "",
        "source_url": "https://www.toyota.com/camry/",
        "source_name": "Toyota",
        "last_updated": "2026-10-06",
    },
    {
        "id": "202600004",
        "year": 2026,
        "make": "Ford",
        "model": "Mustang",
        "trim": "GT",
        "variant": "GT",
        "body_type": "Coupe",
        "vehicle_type": "Passenger Car",
        "fuel_type": "Gasoline",
        "engine": "5.0L V8",
        "engine_displacement": "5.0L",
        "engine_cylinders": 8,
        "horsepower": 480,
        "torque": 415,
        "transmission": "6-Speed Manual",
        "drivetrain": "RWD",
        "msrp": 47000,
        "destination_charge": "",
        "mpg_city": 15,
        "mpg_highway": 24,
        "mpg_combined": 18,
        "ev_range": "",
        "plug_in_range": "",
        "seating": 4,
        "cargo_capacity": "",
        "length": "",
        "width": "",
        "height": "",
        "wheelbase": "",
        "curb_weight": "",
        "towing_capacity": "",
        "description": "2026 Ford Mustang GT test record.",
        "pros": "Strong V8 performance; Engaging handling",
        "cons": "Poor fuel economy; Limited rear seats",
        "features": (
            "SYNC 4; "
            "Ford Co-Pilot360; "
            "Performance features"
        ),
        "image_url": "",
        "source_url": "https://www.ford.com/mustang/",
        "source_name": "Ford",
        "last_updated": "2026-10-06",
    },
    {
        "id": "202600005",
        "year": 2026,
        "make": "Hyundai",
        "model": "Ioniq 5",
        "trim": "SE",
        "variant": "SE",
        "body_type": "SUV",
        "vehicle_type": "Passenger Car",
        "fuel_type": "Electric",
        "engine": "Electric Motor",
        "engine_displacement": "",
        "engine_cylinders": "",
        "horsepower": 225,
        "torque": 258,
        "transmission": "Single-Speed Automatic",
        "drivetrain": "RWD",
        "msrp": 35000,
        "destination_charge": "",
        "mpg_city": "",
        "mpg_highway": "",
        "mpg_combined": "",
        "ev_range": 245,
        "plug_in_range": "",
        "seating": 5,
        "cargo_capacity": "",
        "length": "",
        "width": "",
        "height": "",
        "wheelbase": "",
        "curb_weight": "",
        "towing_capacity": "",
        "description": "2026 Hyundai Ioniq 5 SE test record.",
        "pros": "Long driving range; Fast charging; Spacious interior",
        "cons": "Test dataset record",
        "features": (
            "Fast charging; "
            "Driver assistance; "
            "Wireless smartphone connectivity"
        ),
        "image_url": "",
        "source_url": "https://www.hyundaiusa.com/us/en/vehicles/ioniq-5",
        "source_name": "Hyundai",
        "last_updated": "2026-10-06",
    },
]


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=COLUMNS,
            extrasaction="ignore",
        )

        writer.writeheader()

        for vehicle in VEHICLES:
            writer.writerow(vehicle)

    print("=" * 70)
    print("MotorNation Test Dataset Created")
    print("=" * 70)
    print(f"File: {OUTPUT_FILE}")
    print(f"Records: {len(VEHICLES)}")
    print(f"Columns: {len(COLUMNS)}")
    print()
    print("CSV was written using Python's CSV writer.")
    print("This prevents comma/column alignment problems.")
    print("=" * 70)


if __name__ == "__main__":
    main()
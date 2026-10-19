/* =========================================================
   MotorNation — Cars Catalog
========================================================= */

document.addEventListener("DOMContentLoaded", () => {
    initializeCarsPage();
});


let allCars = [];


/* =========================================================
   ELEMENTS
========================================================= */

const elements = {
    results: document.getElementById("cars-results"),
    loading: document.getElementById("cars-loading"),
    error: document.getElementById("cars-error"),
    noResults: document.getElementById("no-results"),

    search: document.getElementById("search-input"),
    make: document.getElementById("make-filter"),
    body: document.getElementById("body-filter"),
    fuel: document.getElementById("fuel-filter"),
    price: document.getElementById("price-filter"),
    minPrice: document.getElementById("min-price-input"),
    maxPrice: document.getElementById("max-price-input"),
    sort: document.getElementById("sort-filter"),

    resultCount: document.getElementById("results-count"),
    toolbarCount:
        document.getElementById("results-count-toolbar"),

    clear: document.getElementById("clear-filters"),
    retry: document.getElementById("retry-cars"),
    noResultsClear:
        document.getElementById("no-results-clear"),

    activeFilters:
        document.getElementById("active-filters"),

    activeFilterList:
        document.getElementById("active-filter-list")
};


/* =========================================================
   INIT
========================================================= */

async function initializeCarsPage() {

    bindEvents();

    await loadCars();
}


/* =========================================================
   EVENTS
========================================================= */

function bindEvents() {

    elements.search?.addEventListener(
        "input",
        applyFilters
    );

    elements.make?.addEventListener(
        "change",
        applyFilters
    );

    elements.body?.addEventListener(
        "change",
        applyFilters
    );

    elements.fuel?.addEventListener(
        "change",
        applyFilters
    );

    elements.price?.addEventListener(
        "change",
        applyFilters
    );

    elements.minPrice?.addEventListener(
        "input",
        () => {
            document.querySelectorAll(".budget-chip").forEach(c => c.classList.remove("active"));
            applyFilters();
        }
    );

    elements.maxPrice?.addEventListener(
        "input",
        () => {
            document.querySelectorAll(".budget-chip").forEach(c => c.classList.remove("active"));
            applyFilters();
        }
    );

    document.querySelectorAll(".budget-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            const min = chip.getAttribute("data-min") || "";
            const max = chip.getAttribute("data-max") || "";
            if (elements.minPrice) elements.minPrice.value = min;
            if (elements.maxPrice) elements.maxPrice.value = max;
            document.querySelectorAll(".budget-chip").forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            applyFilters();
        });
    });

    elements.sort?.addEventListener(
        "change",
        applyFilters
    );

    elements.clear?.addEventListener(
        "click",
        clearFilters
    );

    elements.noResultsClear?.addEventListener(
        "click",
        clearFilters
    );

    elements.retry?.addEventListener(
        "click",
        loadCars
    );
}


/* =========================================================
   LOAD
========================================================= */

async function loadCars() {

    showLoading();

    try {

        const response = await fetch(
            "/api/cars",
            {
                headers: {
                    "Accept": "application/json"
                },
                cache: "no-store"
            }
        );

        if (!response.ok) {
            throw new Error(
                `API error: ${response.status}`
            );
        }

        const data = await response.json();

        allCars = Array.isArray(data)
            ? data
            : Array.isArray(data.cars)
                ? data.cars
                : [];

        populateFilters();

        applyFilters();

    } catch (error) {

        console.error(
            "MotorNation Cars error:",
            error
        );

        showError();
    }
}


/* =========================================================
   FILTER OPTIONS
========================================================= */

function populateFilters() {

    const makes = unique(
        allCars.map(
            car => car.make
        )
    );

    const bodies = unique(
        allCars.map(
            car =>
                car.bodyType ??
                car.body
        )
    );

    const fuels = unique(
        allCars.map(
            car =>
                car.fuelType ??
                car.fuel
        )
    );

    fillSelect(
        elements.make,
        "All Makes",
        makes
    );

    // Keep the 10 defined body types in HTML; do not overwrite with raw DB values

    fillSelect(
        elements.fuel,
        "All Fuel Types",
        fuels
    );
}


/* =========================================================
   BODY TYPE MATCHER (10 EXACT MOTOR NATION CATEGORIES)
========================================================= */

function matchesBodyType(car, target) {
    if (!target) return true;
    const t = String(target).toLowerCase().trim();
    const rawBody = String(car?.bodyType || car?.body || car?.sourceData?.["Body Type"] || car?.sourceData?.Body_Style || "").toLowerCase();
    const rawClass = String(car?.class || car?.sourceData?.Class || "").toLowerCase();
    const rawTrim = String(car?.trim || car?.variant || car?.model || "").toLowerCase();
    const full = `${rawBody} ${rawClass} ${rawTrim} ${String(car?.make || "")}`.toLowerCase();

    if (t === "suv") {
        return full.includes("suv") || full.includes("crossover") || full.includes("4x4") || full.includes("sport utility") || full.includes("off-roader");
    }
    if (t === "sedans" || t === "sedan") {
        return full.includes("sedan") || full.includes("saloon") || full.includes("liftback") || full.includes("fastback") || full.includes("sportback");
    }
    if (t === "hatchback") {
        return full.includes("hatch") || full.includes("hatchback");
    }
    if (t === "muv") {
        return full.includes("muv") || full.includes("mpv") || full.includes("multi-utility") || full.includes("multi-purpose");
    }
    if (t === "luxury") {
        const price = getPrice(car);
        const luxuryMakes = ["porsche", "mercedes", "bmw", "audi", "lexus", "genesis", "land rover", "range rover", "bentley", "rolls-royce", "aston martin", "ferrari", "maserati", "lamborghini", "cadillac", "lincoln"];
        const make = String(car?.make || "").toLowerCase();
        return full.includes("luxury") || full.includes("ultra-luxury") || full.includes("pinnacle") || luxuryMakes.includes(make) || price >= 70000;
    }
    if (t === "convertible") {
        return full.includes("convertible") || full.includes("cabriolet") || full.includes("roadster") || full.includes("spyder") || full.includes("targa");
    }
    if (t === "pickup") {
        return full.includes("pickup") || full.includes("truck") || full.includes("cab") || full.includes("crew");
    }
    if (t === "coupe") {
        return full.includes("coupe") || full.includes("coupé") || full.includes("2-door") || full.includes("supercar") || full.includes("hypercar");
    }
    if (t === "minivan") {
        return full.includes("minivan") || full.includes("van") || full.includes("microbus");
    }
    if (t === "wagon") {
        return full.includes("wagon") || full.includes("estate") || full.includes("touring") || full.includes("all-terrain") || full.includes("allroad");
    }
    return full.includes(t);
}


function fillSelect(
    select,
    defaultLabel,
    values
) {

    if (!select) {
        return;
    }

    const current = select.value;

    select.innerHTML = `
        <option value="">
            ${defaultLabel}
        </option>
    `;

    values
        .filter(Boolean)
        .sort((a, b) =>
            String(a).localeCompare(String(b))
        )
        .forEach(value => {

            const option =
                document.createElement("option");

            option.value = value;
            option.textContent = value;

            select.appendChild(option);
        });

    select.value = current;
}


/* =========================================================
   FILTERING
========================================================= */

function applyFilters() {

    let filtered = [...allCars];

    const search =
        elements.search?.value
            .trim()
            .toLowerCase() || "";

    const make =
        elements.make?.value || "";

    const body =
        elements.body?.value || "";

    const fuel =
        elements.fuel?.value || "";

    const maxPrice =
        Number(elements.price?.value || 0);

    const sort =
        elements.sort?.value || "";


    if (search) {

        filtered = filtered.filter(car => {

            const text = [
                car.make,
                car.model,
                car.variant,
                car.trim
            ]
                .filter(Boolean)
                .join(" ")
                .toLowerCase();

            return text.includes(search);
        });
    }


    if (make) {

        filtered = filtered.filter(
            car =>
                String(car.make || "")
                    .toLowerCase() ===
                make.toLowerCase()
        );
    }


    if (body) {
        filtered = filtered.filter(car => matchesBodyType(car, body));
    }


    if (fuel) {
        filtered = filtered.filter(car => {
            const value =
                car.fuelType ??
                car.fuel ??
                "";
            return String(value).toLowerCase().includes(fuel.toLowerCase());
        });
    }

    const minPrice = Number(elements.minPrice?.value || 0);
    const maxPriceVal = Number(elements.maxPrice?.value || elements.price?.value || 0);

    if (minPrice > 0) {
        filtered = filtered.filter(car => getPrice(car) >= minPrice);
    }

    if (maxPriceVal > 0) {
        filtered = filtered.filter(car =>
            getPrice(car) > 0 &&
            getPrice(car) <= maxPriceVal
        );
    }


    if (sort === "price-asc") {

        filtered.sort(
            (a, b) =>
                getPrice(a) -
                getPrice(b)
        );
    }

    else if (sort === "price-desc") {

        filtered.sort(
            (a, b) =>
                getPrice(b) -
                getPrice(a)
        );
    }

    else if (sort === "hp-desc") {

        filtered.sort(
            (a, b) =>
                getHorsepower(b) -
                getHorsepower(a)
        );
    }


    renderCars(filtered);

    updateCounts(filtered.length);

    updateActiveFilters();
}


/* =========================================================
   RENDER
========================================================= */

function renderCars(cars) {

    hideLoading();

    if (!elements.results) {
        return;
    }

    if (!cars.length) {

        elements.results.innerHTML = "";

        showNoResults();

        return;
    }

    hideNoResults();

    elements.results.innerHTML =
        cars.map(createCarCard).join("");

    if (window.MotorNationCompare) {
        window.MotorNationCompare.updateAllButtons();
    }

    if (window.MotorNationFavorites) {
        window.MotorNationFavorites.updateAllButtons();
    }
}


/* =========================================================
   CARD
========================================================= */

function createCarCard(car) {

    const name =
        getVehicleName(car);

    const trim =
        getVehicleTrim(car);

    const url =
        `/car/${encodeURIComponent(
            car.id ??
            car.vehicle_id
        )}`;

    const image =
        getImage(car);

    const price =
        getPrice(car);

    const year =
        car.year || "2026";

    const body =
        car.bodyType ??
        car.body ??
        "Vehicle";

    const seating =
        car.seating ? `${car.seating} Seats` :
        (car.sourceData?.Seating ? `${car.sourceData.Seating} Seats` : "5 Seats");

    const fuel =
        car.fuelType ??
        car.fuel ??
        "N/A";

    const hp =
        getHorsepower(car);


    return `
        <article class="car-card">

            <a
                href="${escapeHTML(url)}"
                class="car-card-image-wrapper"
            >

                ${
                    image
                        ? `
                            <img
                                src="${escapeHTML(image)}"
                                alt="${escapeHTML(name)}"
                                class="car-card-image"
                                loading="lazy"
                                onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"
                            >

                            <div
                                class="car-image-placeholder"
                                style="display:none;"
                            >
                                <span>
                                    No Image Available
                                </span>
                            </div>
                        `
                        : `
                            <div class="car-image-placeholder">
                                <span>
                                    No Image Available
                                </span>
                            </div>
                        `
                }

                <span class="car-card-year">
                    ${escapeHTML(year)}
                </span>

                <button
                    type="button"
                    class="card-favorite-btn"
                    data-favorite-id="${escapeHTML(car?.id ?? car?.vehicle_id ?? '')}"
                    onclick="event.preventDefault(); event.stopPropagation(); window.MotorNationFavorites && window.MotorNationFavorites.toggle('${escapeHTML(car?.id ?? car?.vehicle_id ?? '')}')"
                    aria-label="Save vehicle"
                    title="Save vehicle"
                >
                    ♡
                </button>

            </a>


            <div class="car-card-content">

                <div class="car-card-meta-row">
                    <span class="car-card-category">
                        ${escapeHTML(body)}
                    </span>
                    ${
                        trim
                            ? `
                                <span
                                    class="car-card-trim-badge"
                                    title="Trim: ${escapeHTML(trim)}"
                                >
                                    ${escapeHTML(trim)}
                                </span>
                            `
                            : ""
                    }
                </div>

                <h3 class="car-card-title">

                    <a
                        href="${escapeHTML(url)}"
                    >
                        ${escapeHTML(name)}
                    </a>

                </h3>


                <div class="car-card-price">

                    ${
                        price > 0
                            ? formatPrice(price)
                            : "Price unavailable"
                    }

                </div>


                <div class="car-card-specs">

                    <span>
                        ${escapeHTML(fuel)}
                    </span>

                    <span>
                        ${
                            hp > 0
                                ? `${hp} hp`
                                : "N/A hp"
                        }
                    </span>

                    <span>
                        ${escapeHTML(seating)}
                    </span>

                </div>


                <a
                    href="${escapeHTML(url)}"
                    class="car-card-link"
                >
                    View Details →
                </a>

                <button
                    type="button"
                    class="compare-button"
                    data-compare-id="${escapeHTML(car?.id ?? car?.vehicle_id ?? '')}"
                    onclick="window.MotorNationCompare && window.MotorNationCompare.toggle('${escapeHTML(car?.id ?? car?.vehicle_id ?? '')}')"
                >
                    + Compare
                </button>

            </div>

        </article>
    `;
}


/* =========================================================
   IMAGE
========================================================= */

function getImage(car) {

    if (
        typeof car?.image === "string" &&
        car.image.trim()
    ) {
        return car.image.trim();
    }

    if (
        Array.isArray(car?.images) &&
        car.images.length
    ) {
        return car.images[0];
    }

    return "";
}


/* =========================================================
   PRICE
========================================================= */

function getPrice(car) {

    let value = 0;

    if (
        car?.price &&
        typeof car.price === "object"
    ) {
        value =
            car.price.msrp ??
            car.price.value ??
            0;
    }

    else {
        value =
            car?.msrp ??
            car?.startingPrice ??
            car?.price ??
            0;
    }

    if (typeof value === "number") {
        return Number.isFinite(value)
            ? value
            : 0;
    }

    const parsed =
        Number(
            String(value)
                .replace(/[$,]/g, "")
                .trim()
        );

    return Number.isFinite(parsed)
        ? parsed
        : 0;
}


function formatPrice(value) {

    return new Intl.NumberFormat(
        "en-US",
        {
            style: "currency",
            currency: "USD",
            maximumFractionDigits: 0
        }
    ).format(value);
}


/* =========================================================
   HORSEPOWER
========================================================= */

function getHorsepower(car) {

    const value =
        car?.horsepower ??
        car?.performance?.horsepower ??
        0;

    const parsed =
        Number(
            String(value)
                .replace(/[^0-9.]/g, "")
        );

    return Number.isFinite(parsed)
        ? parsed
        : 0;
}


/* =========================================================
   VEHICLE NAME
========================================================= */

function getVehicleName(car) {

    const make =
        String(car?.make || "").trim();

    const model =
        String(car?.model || "").trim();

    return [make, model]
        .filter(Boolean)
        .join(" ") || "Vehicle";
}


function getVehicleTrim(car) {

    return String(
        car?.variant ??
        car?.trim ??
        ""
    ).trim();
}


/* =========================================================
   COUNTS
========================================================= */

function updateCounts(count) {

    if (elements.resultCount) {
        elements.resultCount.textContent =
            count.toLocaleString();
    }

    if (elements.toolbarCount) {

        elements.toolbarCount.textContent =
            `${count.toLocaleString()} ${
                count === 1
                    ? "vehicle"
                    : "vehicles"
            }`;
    }
}


/* =========================================================
   ACTIVE FILTERS
========================================================= */

function updateActiveFilters() {

    if (
        !elements.activeFilters ||
        !elements.activeFilterList
    ) {
        return;
    }

    const filters = [];

    if (elements.search?.value.trim()) {
        filters.push(
            `Search: ${elements.search.value.trim()}`
        );
    }

    if (elements.make?.value) {
        filters.push(
            `Make: ${elements.make.value}`
        );
    }

    if (elements.body?.value) {
        filters.push(
            `Body: ${elements.body.value}`
        );
    }

    if (elements.fuel?.value) {
        filters.push(
            `Fuel: ${elements.fuel.value}`
        );
    }

    if (elements.minPrice?.value && elements.maxPrice?.value) {
        filters.push(
            `Price: ${formatPrice(Number(elements.minPrice.value))} – ${formatPrice(Number(elements.maxPrice.value))}`
        );
    } else if (elements.minPrice?.value) {
        filters.push(
            `Price: Over ${formatPrice(Number(elements.minPrice.value))}`
        );
    } else if (elements.maxPrice?.value || elements.price?.value) {
        filters.push(
            `Price: Under ${formatPrice(
                Number(elements.maxPrice?.value || elements.price?.value)
            )}`
        );
    }

    if (!filters.length) {

        elements.activeFilters.hidden = true;

        elements.activeFilterList.innerHTML = "";

        return;
    }

    elements.activeFilters.hidden = false;

    elements.activeFilterList.innerHTML =
        filters
            .map(
                filter =>
                    `<span class="active-filter">
                        ${escapeHTML(filter)}
                    </span>`
            )
            .join("");
}


/* =========================================================
   CLEAR
========================================================= */

function clearFilters() {

    if (elements.search) {
        elements.search.value = "";
    }

    if (elements.make) {
        elements.make.value = "";
    }

    if (elements.body) {
        elements.body.value = "";
    }

    if (elements.fuel) {
        elements.fuel.value = "";
    }

    if (elements.price) {
        elements.price.value = "";
    }

    if (elements.minPrice) {
        elements.minPrice.value = "";
    }

    if (elements.maxPrice) {
        elements.maxPrice.value = "";
    }

    document.querySelectorAll(".budget-chip").forEach(c => c.classList.remove("active"));

    if (elements.sort) {
        elements.sort.value = "";
    }

    applyFilters();
}


/* =========================================================
   STATES
========================================================= */

function showLoading() {

    elements.loading?.removeAttribute("hidden");

    if (elements.results) {
        elements.results.innerHTML = Array.from({ length: 6 }, () => `
            <article class="skeleton-card">
                <div class="skeleton-thumb skeleton-shimmer"></div>
                <div class="skeleton-body">
                    <div class="skeleton-pill skeleton-shimmer"></div>
                    <div class="skeleton-title skeleton-shimmer"></div>
                    <div class="skeleton-price skeleton-shimmer"></div>
                    <div class="skeleton-specs">
                        <div class="skeleton-spec-item skeleton-shimmer"></div>
                        <div class="skeleton-spec-item skeleton-shimmer"></div>
                        <div class="skeleton-spec-item skeleton-shimmer"></div>
                    </div>
                    <div class="skeleton-btn skeleton-shimmer"></div>
                </div>
            </article>
        `).join("");
    }

    if (elements.error) {
        elements.error.hidden = true;
    }

    if (elements.noResults) {
        elements.noResults.hidden = true;
    }
}


function hideLoading() {

    if (elements.loading) {
        elements.loading.hidden = true;
    }
}


function showError() {

    hideLoading();

    if (elements.error) {
        elements.error.hidden = false;
    }

    if (elements.noResults) {
        elements.noResults.hidden = true;
    }
}


function showNoResults() {

    if (elements.noResults) {
        elements.noResults.hidden = false;
    }
}


function hideNoResults() {

    if (elements.noResults) {
        elements.noResults.hidden = true;
    }
}


/* =========================================================
   UTILITIES
========================================================= */

function unique(values) {

    return [
        ...new Set(
            values
                .filter(Boolean)
                .map(value => String(value).trim())
                .filter(Boolean)
        )
    ];
}


function escapeHTML(value) {

    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
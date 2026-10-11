/* =========================================================
   MotorNation — Homepage JavaScript
   Database-driven:
   - Featured Cars
   - Reviews & Insights
   - Electric Vehicles
========================================================= */

document.addEventListener("DOMContentLoaded", () => {
    loadHomepageCars();
});


/* =========================================================
   GLOBAL HELPERS
========================================================= */

function getCarsFromResponse(data) {
    if (Array.isArray(data)) {
        return data;
    }

    if (data && Array.isArray(data.cars)) {
        return data.cars;
    }

    return [];
}


function getImage(car) {
    if (!car) {
        return "";
    }

    if (
        typeof car.image === "string" &&
        car.image.trim() !== ""
    ) {
        return car.image.trim();
    }

    if (
        Array.isArray(car.images) &&
        car.images.length > 0 &&
        typeof car.images[0] === "string"
    ) {
        return car.images[0].trim();
    }

    if (
        typeof car.imageUrl === "string" &&
        car.imageUrl.trim() !== ""
    ) {
        return car.imageUrl.trim();
    }

    if (
        typeof car.image_url === "string" &&
        car.image_url.trim() !== ""
    ) {
        return car.image_url.trim();
    }

    return "";
}


function getPrice(car) {
    if (!car) {
        return 0;
    }

    let raw = 0;

    /*
     * IMPORTANT:
     * The API returns:
     *
     * price: {
     *     msrp: 38000
     * }
     *
     * So we must check price.msrp BEFORE
     * treating price as a normal number.
     */

    if (
        car.price &&
        typeof car.price === "object" &&
        car.price.msrp !== undefined &&
        car.price.msrp !== null
    ) {
        raw = car.price.msrp;
    } else if (car.msrp !== undefined && car.msrp !== null) {
        raw = car.msrp;
    } else if (
        car.startingPrice !== undefined &&
        car.startingPrice !== null
    ) {
        raw = car.startingPrice;
    } else if (
        car.price !== undefined &&
        car.price !== null
    ) {
        raw = car.price;
    }

    if (typeof raw === "number") {
        return Number.isFinite(raw) ? raw : 0;
    }

    const numeric = Number(
        String(raw)
            .replace(/[$,]/g, "")
            .trim()
    );

    return Number.isFinite(numeric) ? numeric : 0;
}


function formatPrice(value) {
    const price = Number(value);

    if (!Number.isFinite(price) || price <= 0) {
        return "Price unavailable";
    }

    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0
    }).format(price);
}


function getText(value, fallback = "") {
    if (
        value === undefined ||
        value === null
    ) {
        return fallback;
    }

    const text = String(value).trim();

    return text !== "" ? text : fallback;
}


function escapeHTML(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function getVehicleName(car) {
    const make = getText(car?.make);
    const model = getText(car?.model);

    if (make && model) {
        return `${make} ${model}`;
    }

    return make || model || "Vehicle";
}


function getVehicleUrl(car) {
    const id =
        car?.id ??
        car?.vehicle_id ??
        car?.vehicleId;

    if (
        id === undefined ||
        id === null ||
        id === ""
    ) {
        return "#";
    }

    return `/car/${encodeURIComponent(id)}`;
}


function getBodyType(car) {
    return getText(
        car?.bodyType ??
        car?.body ??
        car?.body_type,
        "Vehicle"
    );
}


function getFuelType(car) {
    return getText(
        car?.fuelType ??
        car?.fuel_type,
        ""
    );
}


function getHorsepower(car) {
    const hp =
        car?.horsepower ??
        car?.performance?.horsepower ??
        "";

    return getText(hp, "");
}


function isElectric(car) {
    const fuel = getFuelType(car).toLowerCase();

    return (
        fuel.includes("electric") ||
        fuel === "ev" ||
        fuel.includes("battery")
    );
}


/* =========================================================
   IMAGE ERROR HANDLING
========================================================= */

function createImageHTML(car, className = "car-card-image") {
    const image = getImage(car);
    const name = getVehicleName(car);

    if (!image) {
        return `
            <div class="${className} car-image-placeholder">
                <span>No Image Available</span>
            </div>
        `;
    }

    return `
        <img
            class="${className}"
            src="${escapeHTML(image)}"
            alt="${escapeHTML(name)}"
            loading="lazy"
            onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"
        >

        <div
            class="${className} car-image-placeholder"
            style="display:none;"
            aria-hidden="true"
        >
            <span>No Image Available</span>
        </div>
    `;
}


/* =========================================================
   FEATURED CAR CARD
========================================================= */

function createFeaturedCard(car) {
    const name = getVehicleName(car);
    const year = getText(car?.year, "2026");
    const price = formatPrice(getPrice(car));
    const body = getBodyType(car);
    const fuel = getFuelType(car);
    const horsepower = getHorsepower(car);
    const url = getVehicleUrl(car);

    return `
        <article class="car-card">

            <a
                href="${escapeHTML(url)}"
                class="car-card-image-wrapper"
                aria-label="View ${escapeHTML(name)}"
            >

                ${createImageHTML(car)}

                <span class="car-card-year">
                    ${escapeHTML(year)}
                </span>

            </a>

            <div class="car-card-content">

                <span class="car-card-category">
                    ${escapeHTML(body)}
                </span>

                <h3 class="car-card-title">
                    <a href="${escapeHTML(url)}">
                        ${escapeHTML(name)}
                    </a>
                </h3>

                <div class="car-card-price">
                    ${escapeHTML(price)}
                </div>

                <div class="car-card-specs">

                    <span>
                        ${escapeHTML(fuel || "N/A")}
                    </span>

                    ${
                        horsepower
                            ? `<span>${escapeHTML(horsepower)} hp</span>`
                            : `<span>N/A hp</span>`
                    }

                    <span>
                        ${escapeHTML(body)}
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
   REVIEW CARD
========================================================= */

function createReviewCard(car) {
    const name = getVehicleName(car);
    const url = getVehicleUrl(car);
    const body = getBodyType(car);
    const fuel = getFuelType(car);
    const price = formatPrice(getPrice(car));

    const description =
        getText(
            car?.finalWord ??
            car?.reviewSummary ??
            car?.description,
            ""
        );

    const shortDescription =
        description.length > 150
            ? `${description.substring(0, 147)}...`
            : description;

    let category = body;

    if (fuel) {
        category = fuel;
    }

    return `
        <article class="review-card">

            <a
                href="${escapeHTML(url)}"
                class="review-image"
            >

                ${createImageHTML(car, "review-card-image")}

            </a>

            <div class="review-content">

                <span class="review-category">
                    ${escapeHTML(category)}
                </span>

                <h3>
                    <a href="${escapeHTML(url)}">
                        ${escapeHTML(name)}
                    </a>
                </h3>

                <div class="review-price">
                    ${escapeHTML(price)}
                </div>

                <p>
                    ${
                        shortDescription
                            ? escapeHTML(shortDescription)
                            : `Explore the ${escapeHTML(name)}, including its specifications, strengths, weaknesses and everyday practicality.`
                    }
                </p>

                <a
                    href="${escapeHTML(url)}"
                    class="review-link"
                >
                    Read Review →
                </a>

            </div>

        </article>
    `;
}


/* =========================================================
   EV CARD
========================================================= */

function createEVCard(car) {
    const name = getVehicleName(car);
    const year = getText(car?.year, "2026");
    const price = formatPrice(getPrice(car));
    const horsepower = getHorsepower(car);
    const url = getVehicleUrl(car);

    return `
        <article class="car-card ev-car-card">

            <a
                href="${escapeHTML(url)}"
                class="car-card-image-wrapper"
                aria-label="View ${escapeHTML(name)}"
            >

                ${createImageHTML(car)}

                <span class="car-card-year">
                    ${escapeHTML(year)}
                </span>

            </a>

            <div class="car-card-content">

                <span class="car-card-category">
                    ELECTRIC
                </span>

                <h3 class="car-card-title">
                    <a href="${escapeHTML(url)}">
                        ${escapeHTML(name)}
                    </a>
                </h3>

                <div class="car-card-price">
                    ${escapeHTML(price)}
                </div>

                <div class="car-card-specs">

                    <span>
                        Electric
                    </span>

                    ${
                        horsepower
                            ? `<span>${escapeHTML(horsepower)} hp</span>`
                            : `<span>EV</span>`
                    }

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
   LOAD HOMEPAGE DATA
========================================================= */

async function loadHomepageCars() {
    try {

        const response = await fetch(
            "/api/cars",
            {
                method: "GET",
                headers: {
                    "Accept": "application/json"
                },
                cache: "no-store"
            }
        );

        if (!response.ok) {
            throw new Error(
                `Vehicle API returned ${response.status}`
            );
        }

        const data = await response.json();

        const cars = getCarsFromResponse(data);

        console.log(
            "MotorNation homepage vehicles:",
            cars.length
        );

        if (!cars.length) {
            showHomepageEmptyStates();
            return;
        }

        /*
         * Featured Cars
         */
        renderFeaturedCars(cars);


        /*
         * Reviews & Insights
         */
        renderHomepageReviews(cars);


        /*
         * Electric Vehicles
         */
        renderElectricCars(cars);

    } catch (error) {

        console.error(
            "MotorNation homepage vehicle loading error:",
            error
        );

        showHomepageEmptyStates();
    }
}


/* =========================================================
   FEATURED CARS
========================================================= */

function renderFeaturedCars(cars) {
    const container =
        document.getElementById("featured-cars");

    const empty =
        document.getElementById("featured-empty");

    if (!container) {
        return;
    }

    /*
     * Take the first 6 vehicles from the database.
     */
    const featured = cars.slice(0, 6);

    if (!featured.length) {

        container.innerHTML = "";

        if (empty) {
            empty.hidden = false;
        }

        return;
    }

    container.innerHTML = featured
        .map(createFeaturedCard)
        .join("");

    if (window.MotorNationCompare) {
        window.MotorNationCompare.updateAllButtons();
    }

    if (empty) {
        empty.hidden = true;
    }
}


/* =========================================================
   REVIEWS & INSIGHTS
========================================================= */

function renderHomepageReviews(cars) {
    const container =
        document.getElementById("home-reviews");

    const empty =
        document.getElementById("reviews-empty");

    if (!container) {
        return;
    }

    /*
     * Prefer cars that actually contain review information.
     */
    let reviewCars = cars.filter(car => {

        const hasReview =
            getText(car?.reviewSummary) !== "" ||
            getText(car?.finalWord) !== "" ||
            getText(car?.description) !== "" ||
            getText(car?.pros) !== "" ||
            getText(car?.cons) !== "";

        return hasReview;
    });


    /*
     * If the dataset doesn't contain enough review fields,
     * still show vehicles instead of leaving the section empty.
     */
    if (reviewCars.length < 3) {
        reviewCars = cars;
    }


    /*
     * Show 3 review cards on the homepage.
     */
    reviewCars = reviewCars.slice(0, 3);


    if (!reviewCars.length) {

        container.innerHTML = "";

        if (empty) {
            empty.hidden = false;
        }

        return;
    }


    container.innerHTML = reviewCars
        .map(createReviewCard)
        .join("");


    if (empty) {
        empty.hidden = true;
    }
}


/* =========================================================
   ELECTRIC VEHICLES
========================================================= */

function renderElectricCars(cars) {
    const container =
        document.getElementById("ev-cars");

    const empty =
        document.getElementById("ev-empty");

    if (!container) {
        return;
    }


    const electricCars = cars
        .filter(isElectric)
        .slice(0, 4);


    if (!electricCars.length) {

        container.innerHTML = "";

        if (empty) {
            empty.hidden = false;
        }

        return;
    }


    container.innerHTML = electricCars
        .map(createEVCard)
        .join("");

    if (window.MotorNationCompare) {
        window.MotorNationCompare.updateAllButtons();
    }

    if (empty) {
        empty.hidden = true;
    }
}


/* =========================================================
   EMPTY STATES
========================================================= */

function showHomepageEmptyStates() {

    const sections = [
        "featured-empty",
        "reviews-empty",
        "ev-empty"
    ];

    sections.forEach(id => {

        const element =
            document.getElementById(id);

        if (element) {
            element.hidden = false;
        }

    });
}


/* =========================================================
   OPTIONAL GLOBAL DEBUG
========================================================= */

window.MotorNationHome = {
    reload: loadHomepageCars
};
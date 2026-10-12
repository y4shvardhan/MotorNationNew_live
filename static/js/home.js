/* =========================================================
   MotorNation — Homepage JavaScript
   Database-driven:
   - Featured Cars
   - Reviews & Insights
   - Electric Vehicles
========================================================= */

document.addEventListener("DOMContentLoaded", () => {
    renderSkeletonCards("featured-cars", 6);
    renderSkeletonCards("ev-cars", 4);
    initHeroSearch();
    loadHomepageCars();
    initEngineSound();
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
    const carId = car?.id ?? car?.vehicle_id ?? "";
    const name = getVehicleName(car);
    const year = getText(car?.year, "2026");
    const price = formatPrice(getPrice(car));
    const body = getBodyType(car);
    const seating = car?.seating ? `${car.seating} Seats` : (car?.sourceData?.Seating ? `${car.sourceData.Seating} Seats` : "5 Seats");
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

                <span class="car-badge-chip">
                    ★ FEATURED
                </span>

                <button
                    type="button"
                    class="card-favorite-btn"
                    data-favorite-id="${escapeHTML(carId)}"
                    onclick="event.preventDefault(); event.stopPropagation(); window.MotorNationFavorites && window.MotorNationFavorites.toggle('${escapeHTML(carId)}')"
                    aria-label="Save vehicle"
                    title="Save vehicle"
                >
                    ♡
                </button>

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
    const carId = car?.id ?? car?.vehicle_id ?? "";
    const name = getVehicleName(car);
    const year = getText(car?.year, "2026");
    const price = formatPrice(getPrice(car));
    const horsepower = getHorsepower(car);
    const body = getBodyType(car);
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

                <span class="ev-badge-chip">
                    ⚡ 100% Electric
                </span>

                <button
                    type="button"
                    class="card-favorite-btn"
                    data-favorite-id="${escapeHTML(carId)}"
                    onclick="event.preventDefault(); event.stopPropagation(); window.MotorNationFavorites && window.MotorNationFavorites.toggle('${escapeHTML(carId)}')"
                    aria-label="Save vehicle"
                    title="Save vehicle"
                >
                    ♡
                </button>

            </a>

            <div class="car-card-content">

                <span class="car-card-category" style="color: var(--primary); font-weight: 800;">
                    ${escapeHTML(body || "ELECTRIC")}
                </span>

                <h3 class="car-card-title">
                    <a href="${escapeHTML(url)}">
                        ${escapeHTML(name)}
                    </a>
                </h3>

                <div class="car-card-price" style="color: var(--primary); font-weight: 900;">
                    ${escapeHTML(price)}
                </div>

                <div class="car-card-specs">

                    <span>
                        Electric
                    </span>

                    ${
                        horsepower
                            ? `<span>${escapeHTML(horsepower)} hp</span>`
                            : `<span>Dual Motor</span>`
                    }

                    <span>
                        Zero Emissions
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
   SKELETON SHIMMER LOADERS
========================================================= */

function renderSkeletonCards(containerId, count = 6) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = Array.from({ length: count }, () => `
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


/* =========================================================
   HERO SEARCH AUTOCOMPLETE
========================================================= */

function initHeroSearch() {
    const input = document.getElementById("heroSearchInput");
    const dropdown = document.getElementById("heroSearchDropdown");
    const form = document.getElementById("heroSearchForm");

    if (!input || !dropdown) return;

    let debounceTimer = null;

    input.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            const query = input.value.trim().toLowerCase();
            if (query.length < 2) {
                dropdown.hidden = true;
                dropdown.innerHTML = "";
                return;
            }

            const cars = await (window.fetchMnCars ? window.fetchMnCars() : []);
            if (!cars || !cars.length) {
                dropdown.hidden = true;
                return;
            }

            const matches = cars.filter(car => {
                const make = String(car.make || "").toLowerCase();
                const model = String(car.model || "").toLowerCase();
                const body = String(car.bodyType || car.body || "").toLowerCase();
                const fuel = String(car.fuelType || car.fuel || "").toLowerCase();
                return make.includes(query) || model.includes(query) || body.includes(query) || fuel.includes(query);
            }).slice(0, 5);

            if (!matches.length) {
                dropdown.innerHTML = `<div class="hero-dropdown-empty">No vehicles found matching "${escapeHTML(query)}"</div>`;
                dropdown.hidden = false;
                return;
            }

            dropdown.innerHTML = matches.map(car => {
                const name = getVehicleName(car);
                const url = getVehicleUrl(car);
                const img = getImage(car);
                const price = formatPrice(getPrice(car));
                const year = getText(car.year, "2026");
                const body = getBodyType(car);
                const fuel = getFuelType(car);

                return `
                    <a href="${escapeHTML(url)}" class="hero-dropdown-item">
                        ${img ? `<img src="${escapeHTML(img)}" alt="${escapeHTML(name)}" class="hero-dropdown-thumb">` : `<div class="hero-dropdown-thumb-placeholder">🚗</div>`}
                        <div class="hero-dropdown-meta">
                            <div class="hero-dropdown-title">${escapeHTML(name)}</div>
                            <div class="hero-dropdown-sub">
                                <span>${escapeHTML(year)}</span>
                                <span>·</span>
                                <span>${escapeHTML(body)}</span>
                                ${fuel ? `<span>·</span><span>${escapeHTML(fuel)}</span>` : ""}
                            </div>
                        </div>
                        <div class="hero-dropdown-price">${escapeHTML(price)}</div>
                    </a>
                `;
            }).join("");

            dropdown.hidden = false;
        }, 160);
    });

    // Close when clicking outside
    document.addEventListener("click", (e) => {
        if (form && !form.contains(e.target)) {
            dropdown.hidden = true;
        }
    });

    // Close on Escape key
    input.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            dropdown.hidden = true;
        }
    });
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
    if (window.MotorNationFavorites) {
        window.MotorNationFavorites.updateAllButtons();
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


    // Premier marquee EVs: Porsche Taycan, Tesla Cybertruck, Rivian R1S, Hyundai Ioniq 5 N, Lucid Air, Porsche Macan EV
    const PREMIER_EV_IDS = [287, 322, 300, 161, 220, 291];
    const carMap = new Map();
    cars.forEach(c => {
        const cid = Number(c.id ?? c.vehicle_id);
        if (cid) carMap.set(cid, c);
    });

    let electricCars = [];
    for (const pid of PREMIER_EV_IDS) {
        if (carMap.has(pid)) {
            electricCars.push(carMap.get(pid));
        }
    }

    if (electricCars.length < 4) {
        const fallbackEVs = cars.filter(isElectric).filter(c => !electricCars.includes(c));
        electricCars = electricCars.concat(fallbackEVs);
    }

    electricCars = electricCars.slice(0, 4);

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
    if (window.MotorNationFavorites) {
        window.MotorNationFavorites.updateAllButtons();
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


/* =========================================================
   ENGINE ACCELERATION SOUND & TORQUE ENTRANCE ANIMATION
========================================================= */

let hasPlayedEntranceSound = false;

function triggerTorqueAnimation() {
    const overlay = document.getElementById("torqueOverlay");
    if (!overlay) return;
    overlay.classList.remove("torque-acceleration-active");
    void overlay.offsetWidth; // force DOM reflow
    overlay.classList.add("torque-acceleration-active");
    setTimeout(() => {
        overlay.classList.remove("torque-acceleration-active");
    }, 1600);
}

function playArrivalSound() {
    const audio = document.getElementById("engineAudio");
    if (!audio) return;

    triggerTorqueAnimation();
    audio.currentTime = 0;

    // Enforce 5-second max duration
    const onTimeUpdate = () => {
        if (audio.currentTime >= 5.0) {
            audio.pause();
            audio.removeEventListener("timeupdate", onTimeUpdate);
        }
    };
    audio.addEventListener("timeupdate", onTimeUpdate);

    const playPromise = audio.play();
    if (playPromise !== undefined) {
        playPromise.catch((err) => {
            console.log("Arrival audio waiting for interaction:", err);
        });
    }
}

function initEngineSound() {
    const tryEntranceSound = () => {
        if (hasPlayedEntranceSound) return;
        hasPlayedEntranceSound = true;
        playArrivalSound();
        removeUserGestureListeners();
    };

    const removeUserGestureListeners = () => {
        window.removeEventListener("click", tryEntranceSound);
        window.removeEventListener("scroll", tryEntranceSound);
        window.removeEventListener("keydown", tryEntranceSound);
        window.removeEventListener("touchstart", tryEntranceSound);
    };

    // Try playing immediately upon page entry
    setTimeout(() => {
        const audio = document.getElementById("engineAudio");
        if (audio) {
            audio.currentTime = 0;
            const p = audio.play();
            if (p !== undefined) {
                p.then(() => {
                    hasPlayedEntranceSound = true;
                    triggerTorqueAnimation();
                    const onTimeUpdate = () => {
                        if (audio.currentTime >= 5.0) {
                            audio.pause();
                            audio.removeEventListener("timeupdate", onTimeUpdate);
                        }
                    };
                    audio.addEventListener("timeupdate", onTimeUpdate);
                }).catch(() => {
                    // Browser requires user interaction: listen for first touch/click/scroll
                    window.addEventListener("click", tryEntranceSound, { once: true });
                    window.addEventListener("scroll", tryEntranceSound, { once: true });
                    window.addEventListener("keydown", tryEntranceSound, { once: true });
                    window.addEventListener("touchstart", tryEntranceSound, { once: true });
                });
            }
        }
    }, 300);
}
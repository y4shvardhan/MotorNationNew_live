document.addEventListener("DOMContentLoaded", function () {
    "use strict";

    /* =========================================================
       MOTORNATION — CAR COMPARISON
       ========================================================= */

    const compareContainer =
        document.getElementById(
            "compare-container"
        );

    const compareCount =
        document.getElementById(
            "compare-count"
        );


    if (!compareContainer) {
        return;
    }


    const STORAGE_KEY =
        "motorNationCompare";

    const MAX_COMPARE = 3;


    /* =========================================================
       HELPERS
       ========================================================= */

    function escapeHTML(value) {

        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }


    function getCompareIds() {
        let storedList = [];
        try {
            const value = JSON.parse(
                localStorage.getItem(STORAGE_KEY) || "[]"
            );
            if (Array.isArray(value)) {
                storedList = value.map(String);
            }
        } catch (error) {
            console.warn("MotorNation: invalid comparison storage.", error);
        }

        // Support direct comparison links via query params: ?car1=<id>&car2=<id>
        try {
            const params = new URLSearchParams(window.location.search);
            const urlIds = [];
            ["car1", "car2", "car3", "id"].forEach(function(k) {
                const val = params.get(k);
                if (val && val.trim()) urlIds.push(val.trim());
            });
            const carsParam = params.get("cars");
            if (carsParam) {
                carsParam.split(",").forEach(function(s) {
                    if (s.trim()) urlIds.push(s.trim());
                });
            }

            if (urlIds.length > 0) {
                urlIds.forEach(function(id) {
                    if (!storedList.includes(id)) {
                        storedList.unshift(id);
                    }
                });
                storedList = [...new Set(storedList)].slice(0, MAX_COMPARE);
                saveCompareIds(storedList);
                if (window.history && window.history.replaceState) {
                    window.history.replaceState({}, document.title, window.location.pathname);
                }
            }
        } catch (e) {
            console.warn("MotorNation: URL compare parameter read failed.", e);
        }

        return [...new Set(storedList)].slice(0, MAX_COMPARE);
    }


    function saveCompareIds(ids) {

        localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify(
                [
                    ...new Set(
                        ids.map(String)
                    )
                ].slice(
                    0,
                    MAX_COMPARE
                )
            )
        );
    }


    function updateCount(count) {

        if (compareCount) {

            compareCount.textContent =
                `${count} of ${MAX_COMPARE} cars selected`;
        }

        if (window.MotorNationCompare) {
            window.MotorNationCompare.updateAllButtons();
        }
    }


    function getPrice(car) {

        const raw =
            car?.price ??
            car?.msrp ??
            car?.startingPrice ??
            car?.price?.msrp ??
            0;


        const numeric =
            Number(
                String(raw)
                    .replace(
                        /[$,]/g,
                        ""
                    )
            );


        return Number.isFinite(
            numeric
        )
            ? numeric
            : 0;
    }


    function getHorsepower(car) {

        const value =
            car?.horsepower ??
            car?.specifications?.horsepower ??
            car?.performance?.horsepower ??
            car?.powertrain?.engine?.horsepower ??
            0;


        const numeric =
            Number(
                String(value)
                    .replace(
                        /[^\d.]/g,
                        ""
                    )
            );


        return Number.isFinite(
            numeric
        )
            ? numeric
            : 0;
    }


    function getFuel(car) {

        const value =
            car?.fuelType ??
            car?.fuelTypes ??
            "—";


        return Array.isArray(
            value
        )
            ? value.join(", ")
            : value || "—";
    }


    function getImage(car) {

        return (
            car?.image ||
            car?.imageUrl ||
            car?.images?.[0] ||
            ""
        );
    }


    function getValue(
        car,
        keys,
        fallback = "—"
    ) {

        for (
            const key of keys
        ) {

            const value =
                car?.[key];


            if (
                value !==
                    undefined &&
                value !==
                    null &&
                value !== ""
            ) {

                return value;
            }
        }


        return fallback;
    }


    /* =========================================================
       EMPTY STATE
       ========================================================= */

    function showEmptyState() {

        updateCount(0);

        const toggleDiffBtn = document.getElementById("toggle-diff-btn");
        if (toggleDiffBtn) {
            toggleDiffBtn.style.display = "none";
        }


        compareContainer.innerHTML = `
            <div class="compare-empty">

                <h2>
                    No cars selected
                </h2>

                <p>
                    Select up to 3 cars from
                    the Explore Cars page
                    to compare their
                    specifications side by side.
                </p>

                <a
                    href="/cars"
                    class="primary-btn"
                >
                    Explore Cars
                </a>

            </div>
        `;
    }


    /* =========================================================
       ERROR STATE
       ========================================================= */

    function showError(message) {

        compareContainer.innerHTML = `
            <div class="api-error">

                <h3>
                    Unable to load comparison
                </h3>

                <p>
                    ${escapeHTML(
                        message ||
                        "Something went wrong."
                    )}
                </p>

                <button
                    type="button"
                    class="secondary-btn"
                    id="retry-comparison"
                >
                    Try Again
                </button>

            </div>
        `;


        const retryButton =
            document.getElementById(
                "retry-comparison"
            );


        if (retryButton) {

            retryButton.addEventListener(
                "click",
                loadComparison
            );
        }
    }


    /* =========================================================
       LOAD COMPARISON
       ========================================================= */

    async function loadComparison() {

        const compareIds =
            getCompareIds();


        updateCount(
            compareIds.length
        );


        if (
            !compareIds.length
        ) {

            showEmptyState();

            return;
        }


        try {

            const response =
                await fetch(
                    "/api/cars",
                    {
                        headers: {
                            "Accept":
                                "application/json"
                        }
                    }
                );


            if (!response.ok) {

                throw new Error(
                    `Server returned ${response.status}.`
                );
            }


            const data =
                await response.json();


            if (
                !data ||
                !Array.isArray(
                    data.cars
                )
            ) {

                throw new Error(
                    "Invalid API response."
                );
            }


            const selectedCars =
                compareIds
                    .map(
                        function (id) {

                            return data.cars.find(
                                function (car) {

                                    return (
                                        String(
                                            car.id
                                        ) ===
                                        String(id)
                                    );
                                }
                            );
                        }
                    )
                    .filter(Boolean);


            /*
             * Remove comparison IDs that
             * no longer exist in the API.
             */

            if (
                selectedCars.length !==
                compareIds.length
            ) {

                saveCompareIds(
                    selectedCars.map(
                        function (car) {
                            return String(
                                car.id
                            );
                        }
                    )
                );
            }


            if (
                !selectedCars.length
            ) {

                showEmptyState();

                return;
            }


            renderComparison(
                selectedCars
            );

        } catch (error) {

            console.error(
                "MotorNation Compare Error:",
                error
            );


            showError(
                error.message
            );
        }
    }


    /* =========================================================
       RENDER COMPARISON
       ========================================================= */

    function renderComparison(
        cars
    ) {

        updateCount(
            cars.length
        );


        let html = `

            <div class="compare-table-wrapper">

                <table class="compare-table">

                    <thead>

                        <tr>

                            <th scope="col">
                                Specification
                            </th>

        `;


        cars.forEach(
            function (car) {

                const make =
                    escapeHTML(
                        car.make ||
                        "Unknown"
                    );


                const model =
                    escapeHTML(
                        car.model ||
                        ""
                    );


                const year =
                    escapeHTML(
                        car.year ||
                        ""
                    );


                const image =
                    getImage(car);


                const imageMarkup =
                    image
                        ? `
                            <img
                                src="${escapeHTML(
                                    image
                                )}"
                                alt="${make} ${model}"
                                loading="lazy"
                            >
                        `
                        : `
                            <div
                                class="car-image-placeholder"
                            >
                                <span>
                                    No image
                                </span>
                            </div>
                        `;


                html += `

                    <th scope="col">

                        <div
                            class="compare-car"
                        >

                            <button
                                type="button"
                                class="remove-compare"
                                data-id="${escapeHTML(
                                    car.id
                                )}"
                                aria-label="
                                    Remove
                                    ${make}
                                    ${model}
                                "
                                title="
                                    Remove
                                    ${make}
                                    ${model}
                                "
                            >
                                ×
                            </button>


                            ${imageMarkup}


                            <h3>
                                ${make}
                                ${model}
                            </h3>


                            <span>
                                ${year}
                            </span>

                        </div>

                    </th>

                `;
            }
        );


        html += `

                        </tr>

                    </thead>

                    <tbody>

        `;


        html += createRow(
            "Starting MSRP",
            cars,
            function (car) {

                const price =
                    getPrice(car);


                return price
                    ? "$" +
                      price.toLocaleString()
                    : "—";
            }
        );


        html += createRow(
            "Horsepower",
            cars,
            function (car) {

                const hp =
                    getHorsepower(car);


                return hp
                    ? hp + " hp"
                    : "—";
            }
        );


        html += createRow(
            "Engine",
            cars,
            function (car) {

                return getValue(
                    car,
                    ["engine"]
                );
            }
        );


        html += createRow(
            "Body Type",
            cars,
            function (car) {

                return getValue(
                    car,
                    ["bodyType"]
                );
            }
        );


        html += createRow(
            "Fuel Type",
            cars,
            function (car) {

                return getFuel(
                    car
                );
            }
        );


        html += createRow(
            "Transmission",
            cars,
            function (car) {

                return getValue(
                    car,
                    ["transmission"]
                );
            }
        );


        html += createRow(
            "Drivetrain",
            cars,
            function (car) {

                return getValue(
                    car,
                    ["drivetrain"]
                );
            }
        );


        html += createRow(
            "Seating",
            cars,
            function (car) {

                return getValue(
                    car,
                    ["seating"]
                );
            }
        );


        html += createRow(
            "Cargo",
            cars,
            function (car) {

                return getValue(
                    car,
                    ["cargo"]
                );
            }
        );


        html += createRow(
            "Efficiency",
            cars,
            function (car) {

                return getValue(
                    car,
                    [
                        "mpg",
                        "fuelEconomy",
                        "efficiency"
                    ]
                );
            }
        );


        html += `

                    </tbody>

                </table>

            </div>


            <div class="compare-actions">

                <button
                    type="button"
                    class="secondary-btn"
                    id="clear-comparison"
                >
                    Clear Comparison
                </button>


                <a
                    href="/cars"
                    class="primary-btn"
                >
                    Add More Cars
                </a>

            </div>

        `;


        compareContainer.innerHTML =
            html;

        const toggleDiffBtn = document.getElementById("toggle-diff-btn");
        if (toggleDiffBtn) {
            toggleDiffBtn.style.display = cars.length > 1 ? "inline-flex" : "none";
        }

        applyDiffHighlighting();

        bindComparisonActions();
    }


    /* =========================================================
       CREATE COMPARISON ROW
       ========================================================= */

    function createRow(
        label,
        cars,
        valueFunction
    ) {

        let row = `

            <tr>

                <th scope="row">
                    ${escapeHTML(label)}
                </th>

        `;


        cars.forEach(
            function (car) {

                row += `

                    <td>
                        ${escapeHTML(
                            valueFunction(
                                car
                            )
                        )}
                    </td>

                `;
            }
        );


        row += `

            </tr>

        `;


        return row;
    }


    /* =========================================================
       DIFFERENCE HIGHLIGHTING
       ========================================================= */

    let diffHighlightActive = false;

    function applyDiffHighlighting() {
        const table = document.querySelector(".compare-table");
        if (!table) return;

        const rows = table.querySelectorAll("tbody tr");
        rows.forEach(function (row) {
            const cells = Array.from(row.querySelectorAll("td"));
            if (cells.length < 2) return;

            const values = cells.map(function (td) {
                return td.textContent.trim().toLowerCase();
            });
            const hasDiff = values.some(function (v) {
                return v !== values[0];
            });

            if (hasDiff && diffHighlightActive) {
                row.classList.add("diff-row");
            } else {
                row.classList.remove("diff-row");
            }
        });
    }


    /* =========================================================
       COMPARISON ACTIONS
       ========================================================= */

    function bindComparisonActions() {

        const toggleDiffBtn = document.getElementById("toggle-diff-btn");
        if (toggleDiffBtn) {
            toggleDiffBtn.onclick = function () {
                diffHighlightActive = !diffHighlightActive;
                toggleDiffBtn.classList.toggle("active", diffHighlightActive);
                applyDiffHighlighting();
            };
        }

        document
            .querySelectorAll(
                ".remove-compare"
            )
            .forEach(
                function (button) {

                    button.addEventListener(
                        "click",
                        function () {

                            const id =
                                String(
                                    button.dataset.id
                                );


                            const ids =
                                getCompareIds()
                                    .filter(
                                        function (
                                            item
                                        ) {

                                            return (
                                                item !==
                                                id
                                            );
                                        }
                                    );


                            saveCompareIds(
                                ids
                            );


                            loadComparison();
                        }
                    );
                }
            );


        const clearButton =
            document.getElementById(
                "clear-comparison"
            );


        if (clearButton) {

            clearButton.addEventListener(
                "click",
                function () {

                    localStorage.removeItem(
                        STORAGE_KEY
                    );


                    loadComparison();
                }
            );
        }
    }


    /* =========================================================
       START
       ========================================================= */

    loadComparison();

});
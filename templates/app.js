/* ================================================================
   INDIGENOUS ART FINDER
   Main application JavaScript
   ================================================================ */


/* ================================================================
   1. APPLICATION DATA
   ================================================================
   These variables store information downloaded from the Flask API
   and keep track of what the user is currently looking at.
   ================================================================ */

let works = [];
let places = [];

let selectedPlaceState = "ALL";

const regions = [
    ["NSW", "New South Wales"],
    ["VIC", "Victoria"],
    ["QLD", "Queensland"],
    ["SA", "South Australia"],
    ["WA", "Western Australia"],
    ["TAS", "Tasmania"],
    ["NT", "Northern Territory"]
];


/* ================================================================
   2. DOM ELEMENTS
   ================================================================
   These variables provide easy access to important HTML elements.
   ================================================================ */

const status = document.querySelector("#app-status");

const worksSearch = document.querySelector("#works-search");
const placesSearch = document.querySelector("#places-search");


/* ================================================================
   3. GENERAL HELPER FUNCTIONS
   ================================================================ */


/**
 * Makes sure empty or missing data is displayed consistently.
 *
 * If the API gives us an empty value, the user sees
 * "Not recorded" instead of a blank space.
 */
function text(value) {
    const cleanValue = String(value ?? "").trim();

    return cleanValue || "Not recorded";
}


/**
 * Sends a request to the Flask API and returns the JSON response.
 *
 * This keeps the fetch/error-handling code in one place instead
 * of repeating it throughout the application.
 */
async function requestJson(url, options = {}) {

    const response = await fetch(url, options);

    const payload = await response.json();

    if (!response.ok) {

        const error = new Error(
            payload.error || "The request could not be completed."
        );

        error.status = response.status;

        throw error;
    }

    return payload;
}


/**
 * Creates a labelled information field for the detail panel.
 *
 * Example:
 *
 * Address
 * 15 Example Street, Perth
 *
 * The "wide" option allows a field to stretch across both columns.
 */
function field(label, value, wide = false) {

    const wrapper = document.createElement("div");

    if (wide) {
        wrapper.className = "field-wide";
    }

    const heading = document.createElement("span");

    heading.className = "field-label";
    heading.textContent = label;

    const content = document.createElement("span");

    content.className = "field-value";
    content.textContent = text(value);

    wrapper.append(heading, content);

    return wrapper;
}


/* ================================================================
   4. WELCOME MESSAGE
   ================================================================
   The welcome message is shown the first time someone visits the
   application. localStorage remembers that they have already
   dismissed it.
   ================================================================ */

function setupWelcomeDialog() {

    const welcomeDialog = document.querySelector("#welcome-dialog");

    if (!welcomeDialog) {
        return;
    }

    welcomeDialog.addEventListener("close", () => {

        localStorage.setItem(
            "opening-message-seen",
            "true"
        );

    });


    window.addEventListener("load", () => {

        const hasSeenMessage =
            localStorage.getItem("opening-message-seen");

        if (!hasSeenMessage) {
            welcomeDialog.showModal();
        }

    });
}


/* ================================================================
   5. WORKS
   ================================================================
   These functions control the artwork catalogue:
   - displaying works
   - searching works
   - selecting a work
   ================================================================ */


/**
 * Displays the list of artworks that match the search query.
 */
function renderWorkList(query = "") {

    const normalizedQuery =
        query.trim().toLocaleLowerCase();


    // Search every field in each artwork record.
    const matches = works.filter((work) => {

        return Object
            .values(work)
            .join(" ")
            .toLocaleLowerCase()
            .includes(normalizedQuery);

    });


    const list = document.querySelector("#works-list");

    if (!list) {
        return;
    }


    list.replaceChildren();


    // Update the result counter.
    document.querySelector("#works-count").textContent =
        `${matches.length} / ${works.length}`;


    // Display a message if there are no matches.
    if (!matches.length) {

        list.innerHTML =
            '<div class="empty-state">No works match that search.</div>';

        return;
    }


    // Create one button for every matching artwork.
    matches.forEach((work) => {

        const button = document.createElement("button");

        button.type = "button";
        button.className = "record-button";


        // Highlight the currently selected artwork.
        button.setAttribute(
            "aria-current",
            String(
                document.querySelector("#work-detail")
                    .dataset.title === work.title
            )
        );


        const title = document.createElement("span");

        title.className = "record-title";
        title.textContent = text(work.title);


        const author = document.createElement("span");

        author.className = "record-subtitle";
        author.textContent = text(work.author);


        const type = document.createElement("span");

        type.className = "record-tag";
        type.textContent = text(work.type);


        button.append(title, author, type);


        // Show the selected artwork when clicked.
        button.addEventListener("click", () => {
            showWork(work);
        });


        list.append(button);

    });
}


/**
 * Displays all available information about a selected artwork.
 */
function showWork(work) {

    const detail = document.querySelector("#work-detail");

    if (!detail) {
        return;
    }


    // Remember which artwork is currently selected.
    detail.dataset.title = work.title;

    detail.replaceChildren();


    const kicker = document.createElement("div");

    kicker.className = "detail-kicker";
    kicker.textContent = text(work.type);


    const title = document.createElement("h3");

    title.textContent = text(work.title);


    const byline = document.createElement("p");

    byline.className = "detail-byline";
    byline.textContent = text(work.author);


    const rule = document.createElement("div");

    rule.className = "detail-rule";


    const grid = document.createElement("div");

    grid.className = "detail-grid";


    // Add artwork information to the detail panel.
    grid.append(

        field("Type of work", work.type),

        field(
            "Aboriginal heritage",
            work.heritage
        ),

        field(
            "Work medium",
            work.medium
        ),

        field(
            "Aboriginal group location",
            work.groupLocationAndState
        ),

        field(
            "Date created",
            work.dateCreated
        ),

        field(
            "Collection",
            work.collection,
            true
        ),

        field(
            "Where the work is housed",
            work.housedAt,
            true
        ),

        field(
            "Information sourced from",
            work.source,
            true
        )

    );


    detail.append(
        kicker,
        title,
        byline,
        rule,
        grid
    );


    // Re-render the list so the selected work is highlighted.
    renderWorkList(
        document.querySelector("#works-search").value
    );
}


/* ================================================================
   6. PLACES
   ================================================================
   These functions control the cultural places/art centres section.
   ================================================================ */


/**
 * Displays places based on:
 * - search text
 * - selected state
 */
function renderPlaceList(query = "") {

    const normalizedQuery =
        query.trim().toLocaleLowerCase();


    const matches = places.filter((place) => {

        const matchesState =
            selectedPlaceState === "ALL" ||
            place.state === selectedPlaceState;


        const matchesSearch =
            Object
                .values(place)
                .join(" ")
                .toLocaleLowerCase()
                .includes(normalizedQuery);


        return matchesState && matchesSearch;
    });


    const list = document.querySelector("#places-list");

    if (!list) {
        return;
    }


    list.replaceChildren();


    document.querySelector("#places-count").textContent =
        `${matches.length} / ${places.length}`;


    if (!matches.length) {

        list.textContent =
            "No places match that search.";

        list.className =
            "record-list empty-state";

        return;
    }


    list.className = "record-list";


    matches.forEach((place) => {

        const button = document.createElement("button");

        button.type = "button";
        button.className = "record-button";


        const detail =
            document.querySelector("#place-detail");


        button.setAttribute(
            "aria-current",
            String(
                detail?.dataset.name === place.name
            )
        );


        const name = document.createElement("span");

        name.className = "record-title";
        name.textContent = text(place.name);


        const location = document.createElement("span");

        location.className = "record-subtitle";

        location.textContent =
            [
                place.state,
                place.address
            ]
            .filter(Boolean)
            .join(" · ") ||
            "Location not recorded";


        const category = document.createElement("span");

        category.className = "record-tag";
        category.textContent = text(place.category);


        button.append(
            name,
            location,
            category
        );


        button.addEventListener("click", () => {
            showPlace(place);
        });


        list.append(button);

    });
}


/**
 * Creates the state filter buttons.
 *
 * Users can select "Nationwide" or an individual state.
 */
function renderRegionFilters() {

    const filters =
        document.querySelector("#region-filters");

    if (!filters) {
        return;
    }


    filters.replaceChildren();


    const allRegions = [
        ["ALL", "Nationwide"],
        ...regions
    ];


    allRegions.forEach(([code, label]) => {

        const button =
            document.createElement("button");

        button.type = "button";
        button.className = "region-button";

        button.textContent = label;


        button.setAttribute(
            "aria-pressed",
            String(selectedPlaceState === code)
        );


        button.addEventListener("click", () => {

            selectedPlaceState = code;

            renderRegionFilters();

            renderPlaceList(
                document.querySelector("#places-search").value
            );

        });


        filters.append(button);

    });
}


/**
 * Displays detailed information about a selected place.
 */
function showPlace(place) {

    const detail =
        document.querySelector("#place-detail");

    if (!detail) {
        return;
    }


    detail.dataset.name = place.name;

    detail.replaceChildren();


    const kicker =
        document.createElement("div");

    kicker.className = "detail-kicker";
    kicker.textContent = text(place.category);


    const title =
        document.createElement("h3");

    title.textContent = text(place.name);


    const byline =
        document.createElement("p");

    byline.className = "detail-byline";

    byline.textContent =
        [
            place.state,
            place.address
        ]
        .filter(Boolean)
        .join(" · ") ||
        "Address not recorded";


    const rule =
        document.createElement("div");

    rule.className = "detail-rule";


    const grid =
        document.createElement("div");

    grid.className = "detail-grid";


    /*
        Place information is displayed as labelled fields.
    */
    grid.append(

        field(
            "Address",
            place.address,
            true
        ),

        field(
            "Category",
            place.category
        ),

        field(
            "Aboriginal group",
            place.aboriginalGroup
        ),

        field(
            "Indigenous exclusive content",
            place.exclusiveContent
        ),

        field(
            "Indigenous owned and run",
            place.aboriginalOwned
        ),

        field(
            "Type of interaction",
            place.interactions
        ),

        field(
            "Year founded",
            place.yearFounded
        ),

        field(
            "Information source",
            place.source,
            true
        )

    );


    // Only display this field when the data exists.
    if (place.associatedWith?.trim()) {

        grid.append(
            field(
                "Associated with",
                place.associatedWith,
                true
            )
        );

    }


    /*
        If a valid website URL exists, create a clickable link.
        Otherwise display the value as normal text.
    */
    if (
        place.website &&
        /^https?:\/\//i.test(place.website)
    ) {

        const websiteField =
            document.createElement("div");

        websiteField.className = "field-wide";


        const label =
            document.createElement("span");

        label.className = "field-label";
        label.textContent = "Website";


        const link =
            document.createElement("a");

        link.className = "field-value";

        link.href = place.website;

        link.target = "_blank";

        link.rel =
            "noopener noreferrer";

        link.textContent =
            place.website;


        websiteField.append(
            label,
            link
        );

        grid.append(websiteField);

    } else {

        grid.append(
            field(
                "Website",
                place.website,
                true
            )
        );

    }


    detail.append(
        kicker,
        title,
        byline,
        rule,
        grid
    );


    renderPlaceList(
        document.querySelector("#places-search").value
    );
}


/* ================================================================
   7. ANALYTICS / CHARTS
   ================================================================
   These functions create the graphs shown on the Development of
   Art Centres page.
   ================================================================ */


/**
 * Creates horizontal bar charts from a list of values.
 *
 * Example data:
 *
 * [
 *     ["WA", 15],
 *     ["QLD", 10],
 *     ["NSW", 8]
 * ]
 */
function renderBars(target, entries) {

    const element =
        document.querySelector(target);

    if (!element) {
        return;
    }


    element.replaceChildren();


    const maximum =
        Math.max(
            1,
            ...entries.map(([, count]) => count)
        );


    entries.forEach(([label, count]) => {

        const row =
            document.createElement("div");

        row.className = "bar-row";


        const name =
            document.createElement("span");

        name.className = "bar-label";

        name.textContent = label;

        name.title = label;


        const track =
            document.createElement("div");

        track.className = "bar-track";

        track.setAttribute(
            "aria-label",
            `${label}: ${count}`
        );


        const fill =
            document.createElement("div");

        fill.className = "bar-fill";


        const width =
            count
                ? Math.max(
                    3,
                    count / maximum * 100
                )
                : 0;


        fill.style.width = `${width}%`;


        track.append(fill);


        const value =
            document.createElement("span");

        value.className = "bar-count";

        value.textContent = count;


        row.append(
            name,
            track,
            value
        );


        element.append(row);

    });
}


/**
 * Creates the SVG line chart showing the development of places
 * over time.
 */
function renderFoundedChart(entries) {

    const container =
        document.querySelector("#founded-chart");

    if (!container) {
        return;
    }


    container.replaceChildren();


    if (!entries.length) {

        const empty =
            document.createElement("div");

        empty.className = "empty-state";

        empty.textContent =
            "No founding years are recorded in the source CSV yet.";

        container.append(empty);

        return;
    }


    /*
        SVG is used rather than an external charting library.
        This keeps the project lightweight and means the graph
        is generated directly from the supplied data.
    */

    const svg =
        document.createElementNS(
            "http://www.w3.org/2000/svg",
            "svg"
        );


    svg.setAttribute(
        "viewBox",
        "0 0 720 250"
    );

    svg.setAttribute(
        "role",
        "img"
    );

    svg.setAttribute(
        "aria-label",
        "Cumulative number of places by founding year"
    );

    svg.classList.add("line-chart");


    const maximum =
        Math.max(
            1,
            ...entries.map(
                (entry) => entry.total
            )
        );


    const left = 54;
    const right = 698;
    const top = 24;
    const bottom = 204;


    // Draw the chart axes.
    const axis =
        document.createElementNS(
            svg.namespaceURI,
            "path"
        );

    axis.setAttribute(
        "d",
        `M${left} ${top}V${bottom}H${right}`
    );

    axis.classList.add("chart-axis");

    svg.append(axis);


    /*
        Convert each data value into an x/y position on the graph.
    */
    const points =
        entries.map((entry, index) => {

            const x =
                entries.length === 1
                    ? (left + right) / 2
                    : left +
                        index /
                        (entries.length - 1) *
                        (right - left);


            const y =
                bottom -
                entry.total /
                maximum *
                (bottom - top);


            return {
                ...entry,
                x,
                y
            };

        });


    // Draw the line connecting the points.
    const line =
        document.createElementNS(
            svg.namespaceURI,
            "polyline"
        );


    line.setAttribute(
        "points",
        points
            .map(
                ({ x, y }) => `${x},${y}`
            )
            .join(" ")
    );

    line.classList.add("chart-line");

    svg.append(line);


    // Draw a point for every year.
    points.forEach((point, index) => {

        const dot =
            document.createElementNS(
                svg.namespaceURI,
                "circle"
            );


        dot.setAttribute(
            "cx",
            point.x
        );

        dot.setAttribute(
            "cy",
            point.y
        );

        dot.setAttribute(
            "r",
            "5"
        );

        dot.classList.add(
            "chart-point"
        );


        const title =
            document.createElementNS(
                svg.namespaceURI,
                "title"
            );


        title.textContent =
            `${point.year}: ${point.total} places total (${point.count} founded)`;


        dot.append(title);

        svg.append(dot);


        /*
            Only display selected year labels so the chart does not
            become overcrowded when there are many years.
        */
        if (
            index === 0 ||
            index === points.length - 1 ||
            index === Math.floor(points.length / 2)
        ) {

            const label =
                document.createElementNS(
                    svg.namespaceURI,
                    "text"
                );


            label.setAttribute(
                "x",
                point.x
            );

            label.setAttribute(
                "y",
                "228"
            );

            label.setAttribute(
                "text-anchor",
                "middle"
            );

            label.classList.add(
                "chart-label"
            );

            label.textContent =
                point.year;


            svg.append(label);

        }

    });


    container.append(svg);
}


/**
 * Updates the three summary statistics and both analytics sections.
 */
function renderOverview(data) {

    const metrics =
        document.querySelector("#metrics");

    if (!metrics) {
        return;
    }


    metrics.replaceChildren();


    // Count how many states have at least one place.
    const statesWithPlaces =
        Object
            .values(data.placesByState)
            .filter(
                (count) => count > 0
            )
            .length;


    const metricData = [

        [
            "Art centres & places",
            data.placeCount
        ],

        [
            "First Art Centre Founded",
            data.FirstArtCentreFounded ?? "—"
        ],

        [
            "States represented",
            statesWithPlaces
        ]

    ];


    metricData.forEach(([label, value]) => {

        const item =
            document.createElement("div");

        item.className = "metric";


        const number =
            document.createElement("span");

        number.className = "metric-value";

        number.textContent = value;


        const caption =
            document.createElement("span");

        caption.className = "metric-label";

        caption.textContent = label;


        item.append(
            number,
            caption
        );


        metrics.append(item);

    });


    // Create the state comparison chart.
    renderBars(
        "#state-chart",
        Object.entries(data.placesByState)
    );


    // Create the founding-year line chart.
    renderFoundedChart(
        data.foundedTimeline
    );


    // Create the timeline cards.
    const timeline =
        document.querySelector("#timeline");

    timeline.replaceChildren();


    data.foundedTimeline.forEach((entry) => {

        const item =
            document.createElement("div");

        item.className =
            "timeline-item";


        const year =
            document.createElement("span");

        year.className =
            "timeline-year";

        year.textContent =
            entry.year;


        const count =
            document.createElement("span");

        count.className =
            "timeline-count";

        count.textContent =
            `${entry.count} founded · ${entry.total} total`;


        item.append(
            year,
            count
        );

        timeline.append(item);

    });


    // Explain how missing founding-year data affects the graph.
    const archiveNote =
        document.querySelector("#archive-note");


    if (data.unrecordedFoundedCount) {

        archiveNote.textContent =
            `${data.unrecordedFoundedCount} places have no recognizable founding year in the source CSV and are not plotted.`;

    } else {

        archiveNote.textContent =
            `Founding totals are cumulative; yearly additions are shown in the graph.
Note: Institutions that have shutdown or are not in our dataset are not included`;

    }
}


/* ================================================================
   8. EVENT LISTENERS
   ================================================================
   Event listeners connect user actions to the functions above.
   ================================================================ */


/* Artwork search */
if (worksSearch) {

    worksSearch.addEventListener(
        "input",
        (event) => {

            renderWorkList(
                event.target.value
            );

        }
    );
}


/* Place search */
if (placesSearch) {

    placesSearch.addEventListener(
        "input",
        (event) => {

            renderPlaceList(
                event.target.value
            );

        }
    );
}


/* ================================================================
   9. LOAD DATA FROM FLASK
   ================================================================
   These functions request catalogue data from the Python/Flask
   backend when the page loads.
   ================================================================ */


/**
 * Loads artwork, place and analytics data from Flask.
 */
async function loadCatalogue() {

    try {

        /* --------------------------------------------------------
           Load artworks
           -------------------------------------------------------- */

        if (worksSearch) {

            const response =
                await fetch("/api/works");


            if (!response.ok) {
                throw new Error(
                    "The works catalogue could not be loaded."
                );
            }


            works =
                await response.json();


            document.querySelector(
                "#works-summary"
            ).textContent =
                `Explore ${works.length} works`;


            renderWorkList();
        }


        /* --------------------------------------------------------
           Load places
           -------------------------------------------------------- */

        if (placesSearch) {

            const response =
                await fetch("/api/places");


            if (!response.ok) {
                throw new Error(
                    "The places catalogue could not be loaded."
                );
            }


            places =
                await response.json();


            document.querySelector(
                "#places-summary"
            ).textContent =
                `Explore ${places.length} cultural places`;


            renderRegionFilters();

            renderPlaceList();
        }


        /* --------------------------------------------------------
           Load analytics
           -------------------------------------------------------- */

        if (
            document.querySelector("#metrics")
        ) {

            const response =
                await fetch("/api/overview");


            if (!response.ok) {
                throw new Error(
                    "The catalogue overview could not be loaded."
                );
            }


            const data =
                await response.json();


            renderOverview(data);
        }


    } catch (error) {

        status.textContent =
            `${error.message} Start the application with python main.py.`;

    }
}


/* ================================================================
   10. START APPLICATION
   ================================================================
   These functions are called when the JavaScript file loads.
   ================================================================ */

setupWelcomeDialog();

loadCatalogue();
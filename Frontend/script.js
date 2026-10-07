let works = [];
let places = [];
let overview = {};

const states = ["WA", "NSW", "VIC", "QLD", "SA", "TAS", "NT"];


/* PAGE NAVIGATION */

function showPage(page, button) {

    document
        .querySelectorAll("section")
        .forEach(section => {
            section.classList.add("hidden");
        });


    document
        .getElementById(page)
        .classList.remove("hidden");


    document
        .querySelectorAll(".tab")
        .forEach(tab => {
            tab.classList.remove("active");
        });


    button.classList.add("active");
}


/* LOAD DATA FROM PYTHON */

async function loadData() {

    try {

        const [w, p, o] = await Promise.all([

            fetch("/api/works")
                .then(response => response.json()),

            fetch("/api/places")
                .then(response => response.json()),

            fetch("/api/overview")
                .then(response => response.json())

        ]);


        works = w;
        places = p;
        overview = o;


        displayWorks(works);
        displayPlaces(places);
        createFilters();
        createCharts();


    } catch (error) {

        console.error(error);


        document.getElementById("workList").innerHTML =
            "<p>Unable to load data. Make sure the Python server is running.</p>";
    }
}


/* COLLECTIONS */

function displayWorks(data) {

    const list = document.getElementById("workList");

    list.innerHTML = "";


    data.forEach((work, index) => {

        const button = document.createElement("button");

        button.className = "item";


        button.innerHTML = `

            <strong>
                ${work.title || "Untitled"}
            </strong>

            <span>
                ${work.author || "Author unknown"}
            </span>

            <span>
                ${work.type || "Artwork"}
            </span>

        `;


        button.onclick = () => showWork(work, button);


        list.appendChild(button);


        if (index === 0) {
            showWork(work, button);
        }

    });
}


function showWork(work, button) {

    document
        .querySelectorAll("#workList .item")
        .forEach(item => {
            item.classList.remove("selected");
        });


    if (button) {
        button.classList.add("selected");
    }


    document.getElementById("workDetail").innerHTML = `

        <small>
            ${work.type || "Artwork"}
        </small>

        <h2>
            ${work.title || "Untitled"}
        </h2>

        <p class="author">
            ${work.author || "Author not recorded"}
        </p>


        <div class="info">

            ${field(
                "Aboriginal Group",
                work.heritage
            )}

            ${field(
                "Aboriginal Group Location",
                work.groupLocationAndState
            )}

            ${field(
                "State",
                work.state
            )}

            ${field(
                "Medium",
                work.medium
            )}

            ${field(
                "Date Made",
                work.dateCreated
            )}

            ${field(
                "Collection",
                work.collection
            )}

            ${field(
                "Location",
                work.housedAt
            )}

            ${field(
                "Source",
                work.source
            )}

        </div>

    `;
}


function field(label, value) {

    return `

        <div>

            <b>
                ${label}
            </b>

            ${value || "Not recorded"}

        </div>

    `;
}


function searchWorks() {

    const search = document
        .getElementById("workSearch")
        .value
        .toLowerCase();


    const results = works.filter(work =>

        Object.values(work)
            .join(" ")
            .toLowerCase()
            .includes(search)

    );


    displayWorks(results);
}


/* PLACES */

function displayPlaces(data) {

    const search = document
        .getElementById("placeSearch")
        .value
        .toLowerCase();


    const state =
        document
            .querySelector("#stateFilters .active")
            ?.dataset.state || "ALL";


    const filtered = data.filter(place =>

        (state === "ALL" || place.state === state) &&

        Object.values(place)
            .join(" ")
            .toLowerCase()
            .includes(search)

    );


    const list = document.getElementById("placeList");

    list.innerHTML = "";


    filtered.forEach((place, index) => {

        const button = document.createElement("button");

        button.className = "item";


        button.innerHTML = `

            <strong>
                ${place.name}
            </strong>

            <span>
                ${place.state || ""}
            </span>

            <span>
                ${place.category || ""}
            </span>

        `;


        button.onclick = () => showPlace(place, button);


        list.appendChild(button);


        if (index === 0) {
            showPlace(place, button);
        }

    });
}


function showPlace(place, button) {

    document
        .querySelectorAll("#placeList .item")
        .forEach(item => {
            item.classList.remove("selected");
        });


    if (button) {
        button.classList.add("selected");
    }


    document.getElementById("placeDetail").innerHTML = `

        <small>
            ${place.category || "Cultural Place"}
        </small>

        <h2>
            ${place.name}
        </h2>

        <p class="author">
            ${place.state || ""} ·
            ${place.address || "Address not recorded"}
        </p>


        <div class="info">

            ${field(
                "Aboriginal Group",
                place.aboriginalGroup
            )}

            ${field(
                "Indigenous Owned",
                place.aboriginalOwned
            )}

            ${field(
                "Indigenous Content",
                place.exclusiveContent
            )}

            ${field(
                "Interaction",
                place.interactions
            )}

            ${field(
                "Year Founded",
                place.yearFounded
            )}

            ${field(
                "Source",
                place.source
            )}

            ${field(
                "Associated With",
                place.associatedWith
            )}

            ${field(
                "Website",
                place.website
            )}

        </div>

    `;
}


function searchPlaces() {

    displayPlaces(places);

}


/* STATE FILTERS */

function createFilters() {

    const container =
        document.getElementById("stateFilters");


    container.innerHTML = "";


    ["ALL", ...states].forEach(state => {

        const button =
            document.createElement("button");


        button.textContent =
            state === "ALL" ? "All" : state;


        button.dataset.state = state;


        if (state === "ALL") {
            button.classList.add("active");
        }


        button.onclick = () => {

            container
                .querySelectorAll("button")
                .forEach(button => {
                    button.classList.remove("active");
                });


            button.classList.add("active");


            displayPlaces(places);

        };


        container.appendChild(button);

    });

}


/* CHARTS */

function createCharts() {

    const data =
        overview.placesByState || {};


    const total =
        overview.placeCount || 0;


    document.getElementById("metrics").innerHTML = `

        <div class="metric">

            <strong>
                ${total}
            </strong>

            <span>
                Art centres & places
            </span>

        </div>


        <div class="metric">

            <strong>
                ${overview.datedPlaceCount || 0}
            </strong>

            <span>
                Places with founding year
            </span>

        </div>


        <div class="metric">

            <strong>
                ${Object.keys(data).length}
            </strong>

            <span>
                States & territories
            </span>

        </div>

    `;


    const chart =
        document.getElementById("stateChart");


    chart.innerHTML = "";


    const max =
        Math.max(...Object.values(data), 1);


    Object.entries(data).forEach(([state, count]) => {

        chart.innerHTML += `

            <div class="bar">

                <label>

                    <span>
                        ${state}
                    </span>

                    <strong>
                        ${count}
                    </strong>

                </label>


                <div class="bar-track">

                    <div
                        class="bar-fill"
                        style="width:${count / max * 100}%">
                    </div>

                </div>

            </div>

        `;

    });


    createLineChart(
        overview.foundedTimeline || []
    );

}


/* LINE GRAPH */

function createLineChart(data) {

    const svg =
        document.getElementById("lineChart");


    svg.innerHTML = "";


    if (!data.length) {
        return;
    }


    const max =
        Math.max(
            ...data.map(item => item.total),
            1
        );


    const points =
        data
            .map((item, index) => {

                const x =
                    30 +
                    (index / (data.length - 1 || 1)) *
                    440;


                const y =
                    190 -
                    (item.total / max) *
                    160;


                return `${x},${y}`;

            })
            .join(" ");


    svg.innerHTML = `

        <line
            x1="30"
            y1="190"
            x2="470"
            y2="190"
            stroke="#d9ddd3"
        />


        <polyline
            points="${points}"
            fill="none"
            stroke="#1d493a"
            stroke-width="3"
        />


        ${data.map((item, index) => {

            const x =
                30 +
                (index / (data.length - 1 || 1)) *
                440;


            const y =
                190 -
                (item.total / max) *
                160;


            return `

                <circle
                    cx="${x}"
                    cy="${y}"
                    r="5"
                    fill="#bd583c"
                />

            `;

        }).join("")}

    `;


    document.getElementById("timeline").innerHTML =

        data.map(item => `

            <p>

                <strong>
                    ${item.year}
                </strong>

                –
                ${item.count} founded,
                ${item.total} total

            </p>

        `).join("");

}


/* START APPLICATION */

loadData();
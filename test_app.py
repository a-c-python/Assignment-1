# Import necessary modules for testing
import csv
import hashlib
import sqlite3
from urllib import response
import pytest
import app


# Testing incomplete csv entries
@pytest.mark.parametrize(
    ("endpoint", "csv_filename", "headers", "row_key", "partial_value"),
    [
        (
            "/api/works",
            "Draft collection works.csv",
            ["Title", "Author", "Type", "Date made"],
            "title",
            "Incomplete artwork",
        ),
        (
            "/api/places",
            "Draft places.csv",
            ["Location", "Category", "State"],
            "name",
            "Incomplete place",
        ),
    ],
)
def test_app_handles_missing_or_incomplete_csv_entry(
    tmp_path, monkeypatch, endpoint, csv_filename, headers, row_key, partial_value
):
    data_directory = tmp_path / "data"
    data_directory.mkdir()
    csv_path = data_directory / csv_filename

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(headers)
        writer.writerow([partial_value])
        writer.writerow(["", "Partially recorded"])

    monkeypatch.setattr(app, "BASE_DIR", str(tmp_path))

    response = app.app.test_client().get(endpoint)

    assert response.status_code == 200
    records = response.get_json()
    assert len(records) == 2
    assert records[0][row_key] == partial_value
    assert records[1][row_key] == ""

@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    database_path = tmp_path / "accounts.sqlite3"
    monkeypatch.setitem(app.app.config, "DATABASE", str(database_path))
    monkeypatch.setitem(app.app.config, "TESTING", True)
    app.init_database()
    return app.app.test_client()
#testing registration with recovery email and normalization of email address
def test_register_accepts_and_normalizes_optional_recovery_email(auth_client):
    response = auth_client.post(
        "/api/register",
        json={
            "username": "recovery_user",
            "password": "secure-password",
            "recovery_email": "  Example@Email.com ",
        },
    )

    assert response.status_code == 201
    with app.database_connection() as connection:
        user = connection.execute(
            "SELECT recovery_email FROM users WHERE username = ?",
            ("recovery_user",),
        ).fetchone()
    assert user[0] == "example@email.com"


def test_auth_session_cookie_uses_secure_attributes_by_default(auth_client):
    response = auth_client.post(
        "/api/register",
        json={"username": "cookie_user", "password": "secure-password"},
    )

    cookie = response.headers["Set-Cookie"]
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_register_still_allows_account_without_recovery_email(auth_client):
    response = auth_client.post(
        "/api/register",
        json={"username": "no_recovery", "password": "secure-password"},
    )

    assert response.status_code == 201
    with app.database_connection() as connection:
        user = connection.execute(
            "SELECT recovery_email FROM users WHERE username = ?",
            ("no_recovery",),
        ).fetchone()
    assert user[0] is None


def test_password_reset_email_token_changes_password_once(auth_client, monkeypatch):
    sent = {}
    monkeypatch.setattr(app, "get_smtp_configuration", lambda: {
        "host": "smtp.example.com",
        "port": 587,
        "username": "",
        "password": "",
        "sender": "noreply@example.com",
        "base_url": "https://example.com",
        "use_ssl": False,
        "use_tls": True,
    })
    monkeypatch.setattr(
        app,
        "send_password_reset_email",
        lambda email, token, configuration: sent.update(email=email, token=token),
    )
    auth_client.post(
        "/api/register",
        json={
            "username": "reset_user",
            "password": "old-password",
            "recovery_email": "reset@example.com",
        },
    )

    request_response = auth_client.post(
        "/api/forgot-password",
        json={"email": "reset@example.com"},
    )
    reset_response = auth_client.post(
        "/api/reset-password",
        json={"token": sent["token"], "password": "new-password"},
    )
    reused_token_response = auth_client.post(
        "/api/reset-password",
        json={"token": sent["token"], "password": "another-password"},
    )

    assert request_response.status_code == 200
    assert reset_response.status_code == 200
    assert reused_token_response.status_code == 400
    assert auth_client.post(
        "/api/login",
        json={"username": "reset_user", "password": "old-password"},
    ).status_code == 401
    assert auth_client.post(
        "/api/login",
        json={"username": "reset_user", "password": "new-password"},
    ).status_code == 200


def test_forgot_password_response_does_not_reveal_unknown_email(auth_client, monkeypatch):
    monkeypatch.setattr(app, "get_smtp_configuration", lambda: {})
    monkeypatch.setattr(app, "send_password_reset_email", lambda *args: None)
    auth_client.post(
        "/api/register",
        json={
            "username": "known_email",
            "password": "secure-password",
            "recovery_email": "known@example.com",
        },
    )

    known_response = auth_client.post(
        "/api/forgot-password",
        json={"email": "known@example.com"},
    )
    unknown_response = auth_client.post(
        "/api/forgot-password",
        json={"email": "unknown@example.com"},
    )

    assert known_response.status_code == unknown_response.status_code == 200
    assert known_response.get_json() == unknown_response.get_json()


def test_expired_password_reset_token_is_rejected(auth_client):
    auth_client.post(
        "/api/register",
        json={
            "username": "expired_token",
            "password": "original-password",
            "recovery_email": "expired@example.com",
        },
    )
    token = "expired-reset-token"
    with app.database_connection() as connection:
        user_id = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            ("expired_token",),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO password_reset_tokens (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (hashlib.sha256(token.encode("utf-8")).hexdigest(), user_id, "2000-01-01T00:00:00+00:00"),
        )

    response = auth_client.post(
        "/api/reset-password",
        json={"token": token, "password": "new-password"},
    )

    assert response.status_code == 400
    assert auth_client.post(
        "/api/login",
        json={"username": "expired_token", "password": "original-password"},
    ).status_code == 200

def test_database_initialization_migrates_existing_users_table(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
        """)
    monkeypatch.setitem(app.app.config, "DATABASE", str(database_path))

    app.init_database()

    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
    assert "recovery_email" in columns


#Testing login failures
# Incorrect or non-existent username,should return invalid username or password error message
def test_login_failure_nonexistent_user(auth_client):
    response = auth_client.post(
        "/api/login",
        json={"username": "nonexistent_user", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.get_json() == {"error": "Invalid username or password."}

# Incorrect password for an existing user, should return invalid username or password error message 
def test_login_failure_incorrect_password(auth_client):
    auth_client.post(
        "/api/register",
        json={"username": "correct_user", "password": "correct-password"},
    )
    response = auth_client.post(
        "/api/login",
        json={"username": "correct_user", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.get_json() == {"error": "Invalid username or password."}

# Testing Data retrival Place (clicking a place to view more information about it)
def test_place_details_appear_when_clicked(page):
    test_place = {
        "name": "Test Place",
        "address": "123 Test St",
        "category": "Museum",
        "state": "Test State",
        "aboriginalGroup": "Test Group",
        "exclusiveContent": True,
        "aboriginalOwned": False,
        "listedSource": "ACH",
        "interactions": "engage",
        "yearFounded": 2000,
        "website": "http://testplace.com",
    }

    page.route("**/api/works", lambda route: route.fulfill(json=[])) # Puts test data in place for the test to use, so that the test can check if the place details are displayed correctly when clicked.
    page.route("**/api/places", lambda route: route.fulfill(json=[test_place]))
    page.route(
        "**/api/overview",
        lambda route: route.fulfill(json={
            "placeCount": 1,
            "datedPlaceCount": 0,
            "unrecordedFoundedCount": 1,
            "placesByState": {},
            "foundedTimeline": [],
        }),
    )
    page.route(
        "**/api/session",
        lambda route: route.fulfill(json={"authenticated": False}), # User isn't logged in
    )

    page.goto("http://127.0.0.1:5000") # Tells the test to go to the app's main page.
    page.get_by_role("button", name="Test Place").click() # Tells the test to click the button for the place named "Test Place".
    
    details = page.locator("#place-detail")

    address = details.locator(".detail-grid > div").filter(
    has_text="Address"
    )
    assert address.locator(".field-value").inner_text() == "123 Test St"

    category = details.locator(".detail-grid > div").filter(
    has_text="Category"
    )
    assert category.locator(".field-value").inner_text() == "Museum"

    group = details.locator(".detail-grid > div").filter(
    has_text="Aboriginal group"
    )
    assert group.locator(".field-value").inner_text() == "Test Group"

    indigenous_content= details.locator(".detail-grid > div").filter(
    has_text="Indigenous exclusive content"
    )
    assert indigenous_content.locator(".field-value").inner_text() == "True"

    aboriginal_owned = details.locator(".detail-grid > div").filter(
    has_text="Indigenous owned and run"
    )
    assert aboriginal_owned.locator(".field-value").inner_text() == "False"

    interaction = details.locator(".detail-grid > div").filter(
    has_text="Type of interaction"
    )
    assert interaction.locator(".field-value").inner_text() == "engage"

    year_founded = details.locator(".detail-grid > div").filter(
    has_text="Year founded"
    )
    assert year_founded.locator(".field-value").inner_text() == "2000"

    source = details.locator(".detail-grid > div").filter(
    has_text="Listed source"
    )
    assert source.locator(".field-value").inner_text() == "ACH"


    website = details.locator(".detail-grid > div").filter(
    has_text="Website"
    )
    assert website.locator(".field-value").inner_text() == "http://testplace.com"

# Testing Data retrival Work (clicking a work to view more information about it)
def test_work_details_appear_when_clicked(page):
    test_work = {
        "name": "Test Work",
        "type of work": "Artefact",
        "aboriginal heritage": "Unknown",
        "work medium": "egg",
        "aboriginal group location": "WA",
        "date created": "c.1880",
        "collection": "The State Art Collection, The Art Gallery of Western Australia",
        "where the work is housed": "The Art Gallery of Western Australia",
    }

    page.route("**/api/works", lambda route: route.fulfill(json=[test_work]))
    page.route("**/api/places", lambda route: route.fulfill(json=[]))
    page.route(
            "**/api/overview",
            lambda route: route.fulfill(json={
                "placeCount": 1,
                "datedPlaceCount": 0,
                "unrecordedFoundedCount": 1,
                "placesByState": {},
                "foundedTimeline": [],
            }),
        )
    page.route(
            "**/api/session",
            lambda route: route.fulfill(json={"authenticated": False}),
        )

    page.goto("http://127.0.0.1:5000") # Tells the test to go to the app's main page.
    page.get_by_role("button", name="Test Work").click() # Tells the test to click the button for the work named "Test Work".

    details = page.locator("#work-detail")

    work_type = details.locator(".detail-grid > div").filter(
    has_text="Type of work"
    )
    assert work_type.locator(".field-value").inner_text() == "Artefact"

    work_medium = details.locator(".detail-grid > div").filter(
    has_text="Work medium"
    )
    assert work_medium.locator(".field-value").inner_text() == "egg"

    date_created = details.locator(".detail-grid > div").filter(
    has_text="Date created" 
    )  
    assert date_created.locator(".field-value").inner_text() == "c.1880"

    aboriginal_heritage = details.locator(".detail-grid > div").filter(
    has_text="Aboriginal heritage"
    )
    assert aboriginal_heritage.locator(".field-value").inner_text() == "Unknown"

    collection = details.locator(".detail-grid > div").filter(
    has_text="Collection"
    )
    assert collection.locator(".field-value").inner_text() == "The State Art Collection, The Art Gallery of Western Australia"

    housed = details.locator(".detail-grid > div").filter(
    has_text="Where the work is housed"
    )
    assert housed.locator(".field-value").inner_text() == "The Art Gallery of Western Australia"


# Testing filter for collection by state
def test_filter_places_by_state(page):
    test_places = [
        {"name": "Place A", "state": "WA"},
        {"name": "Place B", "state": "NSW"},
        {"name": "Place C", "state": "WA"},
        {"name": "Place D", "state": "VIC"},
        {"name": "Place E", "state": "NSW"}
    ]

    page.route("**/api/works", lambda route: route.fulfill(json=[]))
    page.route("**/api/places", lambda route: route.fulfill(json=test_places))
    page.route(
        "**/api/overview",
        lambda route: route.fulfill(json={
            "placeCount": 5,
            "datedPlaceCount": 0,
            "unrecordedFoundedCount": 3,
            "placesByState": {"WA": 2, "NSW": 2, "VIC": 1},
            "foundedTimeline": [],
        }),
    )
    page.route(
        "**/api/session",
        lambda route: route.fulfill(json={"authenticated": False}),
    )

    page.goto("http://127.0.0.1:5000")
    page.get_by_role("tab", name="Places").click()

    place_names = page.locator("#places-list .record-title")

    page.get_by_role("button", name="Western Australia").click()
    assert sorted(place_names.all_text_contents()) == ["Place A", "Place C"]

    page.get_by_role("button", name="New South Wales").click()
    assert sorted(place_names.all_text_contents()) == ["Place B", "Place E"]

    page.get_by_role("button", name="Victoria").click()
    assert place_names.all_text_contents() == ["Place D"]

    page.get_by_role("button", name="Nationwide").click()
    assert sorted(place_names.all_text_contents()) == ["Place A", "Place B", "Place C", "Place D", "Place E"]

# Testing filter for collection by type

#Testing saved places list - places are saved to the list and can be retrieved and edited 

# Testing visualisation - does the year filter work correctly?

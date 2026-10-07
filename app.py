#Import modules 
import csv
import hashlib
import os
import re
import secrets
import smtplib
import ssl
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import quote, urlsplit

# Import flask modules - web application framework
from flask import Flask, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask("__name__")	# Creates app
app.config["DATABASE"] = os.environ.get(
	"DATABASE_PATH",
	os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "app.sqlite3"),
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true"
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # Tells app where to find its files
REGION_CODES = ("NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT") # Gives regional codes


@contextmanager
def database_connection():
	with closing(sqlite3.connect(app.config["DATABASE"])) as connection:
		connection.execute("PRAGMA foreign_keys = ON")
		with connection:
			yield connection


def init_database():
	database_path = app.config["DATABASE"]
	if database_path == ":memory:":
		raise ValueError("Set DATABASE_PATH to a file so accounts and saved places persist.")
	os.makedirs(os.path.dirname(os.path.abspath(database_path)), exist_ok=True)
	with database_connection() as connection:
		connection.execute("""
			CREATE TABLE IF NOT EXISTS users (
				id INTEGER PRIMARY KEY,
				username TEXT NOT NULL UNIQUE,
				password_hash TEXT NOT NULL,
				recovery_email TEXT
			)
		""")
		user_columns = {
			row[1] for row in connection.execute("PRAGMA table_info(users)")
		}
		if "recovery_email" not in user_columns:
			connection.execute("ALTER TABLE users ADD COLUMN recovery_email TEXT")
		connection.execute("""
			CREATE UNIQUE INDEX IF NOT EXISTS users_recovery_email_unique
			ON users (recovery_email) WHERE recovery_email IS NOT NULL
		""")
		connection.execute("""
			CREATE TABLE IF NOT EXISTS password_reset_tokens (
				token_hash TEXT PRIMARY KEY,
				user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
				expires_at TEXT NOT NULL
			)
		""")
		connection.execute("""
			CREATE TABLE IF NOT EXISTS saved_places (
				user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
				place_name TEXT NOT NULL,
				PRIMARY KEY (user_id, place_name)
			)
		""")
		connection.execute("""
			CREATE TABLE IF NOT EXISTS app_settings (
				name TEXT PRIMARY KEY,
				value TEXT NOT NULL
			)
		""")


init_database()


def load_secret_key():
	secret_key = os.environ.get("SECRET_KEY")
	if secret_key:
		return secret_key

	with database_connection() as connection:
		connection.execute(
			"INSERT OR IGNORE INTO app_settings (name, value) VALUES (?, ?)",
			("secret_key", secrets.token_hex(32)),
		)
		return connection.execute(
			"SELECT value FROM app_settings WHERE name = ?",
			("secret_key",),
		).fetchone()[0]


app.config["SECRET_KEY"] = load_secret_key()


def current_user_id():
	return session.get("user_id")


def normalize_email(value):
	if not isinstance(value, str):
		return None
	email = value.strip().casefold()
	if not email or len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
		return None
	return email


def get_smtp_configuration():
	host = os.environ.get("SMTP_HOST", "").strip()
	sender = os.environ.get("SMTP_FROM", "").strip()
	base_url = os.environ.get("APP_BASE_URL", "").strip().rstrip("/")
	if not host or not sender or not base_url:
		raise ValueError("SMTP_HOST, SMTP_FROM, and APP_BASE_URL must be configured.")
	parsed_base_url = urlsplit(base_url)
	if parsed_base_url.scheme not in {"http", "https"} or not parsed_base_url.netloc:
		raise ValueError("APP_BASE_URL must be an absolute HTTP or HTTPS URL.")
	use_ssl = os.environ.get("SMTP_USE_SSL", "").lower() == "true"
	use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
	if use_ssl and use_tls:
		raise ValueError("Enable only one of SMTP_USE_SSL and SMTP_USE_TLS.")
	try:
		port = int(os.environ.get("SMTP_PORT", "587"))
	except ValueError as error:
		raise ValueError("SMTP_PORT must be a valid port number.") from error
	if not 1 <= port <= 65535:
		raise ValueError("SMTP_PORT must be between 1 and 65535.")
	return {
		"host": host,
		"port": port,
		"username": os.environ.get("SMTP_USERNAME", ""),
		"password": os.environ.get("SMTP_PASSWORD", ""),
		"sender": sender,
		"base_url": base_url,
		"use_ssl": use_ssl,
		"use_tls": use_tls,
	}


def send_password_reset_email(email, token, configuration):
	reset_url = f"{configuration['base_url']}/?reset_token={quote(token)}"
	message = EmailMessage()
	message["Subject"] = "Reset your Country & Collection password"
	message["From"] = configuration["sender"]
	message["To"] = email
	message.set_content(
		"Use the following link to reset your password. This link expires in 30 minutes "
		"and can only be used once:\n\n"
		f"{reset_url}\n\n"
		"If you did not request a password reset, you can ignore this email."
	)
	smtp_class = smtplib.SMTP_SSL if configuration["use_ssl"] else smtplib.SMTP
	with smtp_class(configuration["host"], configuration["port"], timeout=10) as server:
		if configuration["use_tls"]:
			server.starttls(context=ssl.create_default_context())
		if configuration["username"]:
			server.login(configuration["username"], configuration["password"])
		server.send_message(message)


def saved_places_for_user(user_id):
	with database_connection() as connection:
		connection.row_factory = sqlite3.Row
		rows = connection.execute(
			"SELECT place_name FROM saved_places WHERE user_id = ? ORDER BY rowid",
			(user_id,),
		).fetchall()
	saved_names = {row["place_name"].casefold() for row in rows}
	return [place for place in get_places() if place["name"].casefold() in saved_names]


# Reads CSV file and returns a list of dictionaries, one for each row
def read_csv_rows(filename):
	path = os.path.join(BASE_DIR, "data", filename)
	with open(path, encoding="utf-8-sig", newline="") as source:
		reader = csv.reader(source)
		headers = next(reader, [])
		seen = {}
		unique_headers = []
		for raw_header in headers:
			header = raw_header.strip()
			seen[header] = seen.get(header, 0) + 1
			unique_headers.append(header if seen[header] == 1 else f"{header}_{seen[header]}")
		return [dict(zip(unique_headers, row)) for row in reader]


# Allows python to read the csv file and convert it to a json format for the front end to read
def json_response(payload):
	return jsonify(payload)

# Reads the artworks csv file and converts it into a dictionary. The frontend will use the dictionary information in the artwork browser page.
def get_works():
	works = []
	for row in read_csv_rows("Draft collection works.csv"):
		date_created = row.get("Date made", "").strip()
		year_match = re.search(r"(?:18|19|20)\d{2}", date_created)
		works.append({												# Creates a dictionary for each row in the csv file
			"title": row.get("Title", "").strip(),					# .strip() removes any whitespace from the beginning and end of the string
			"author": row.get("Author", "").strip(),
			"type": row.get("Type", "").strip(),
			"heritage": row.get("Aboriginal group", "").strip(),
			"groupLocation": row.get("Aboriginal Group location", "").strip(),
			"groupLocationAndState": row.get("Aboriginal Group location and State", "").strip(),
			"state": row.get("State", "").strip(),
			"medium": row.get("Medium", "").strip(),
			"dateCreated": date_created,
			"year": int(year_match.group()) if year_match else None,
			"collection": row.get("Collection", "").strip(),
			"housedAt": row.get("Item Housed", "").strip(),
		})
	return works

# Reads the places csv file and converts it into a dictionary. The frontend will use the dictionary information in the place browser page.
def get_places():
	places = []
	for row in read_csv_rows("Draft places.csv"):
		founded = row.get("Year Founded", "").strip()
		year_match = re.search(r"(?:18|19|20)\d{2}", founded)   # Searches for a 4-digit year between 1800 and 2099 - used for visualisations
		places.append({											# Creates a dictionary for each row in the csv file
			"name": row.get("Location", "").strip(),			# .strip() removes any whitespace from the beginning and end of the string
			"category": row.get("Category", "").strip(),
			"interactions": row.get("Type of interaction: buy, view, learn, engage, all", "").strip(),
			"aboriginalGroup": row.get("Aboriginal Group", "").strip(),
			"exclusiveContent": row.get("Exclusively aboriginal content", "").strip(),
			"aboriginalOwned": row.get("Aboriginal Owned and Governed", "").strip(),
			"state": row.get("State", "").strip(),
			"address": row.get("Location_2", "").strip(),
			"source": row.get("Source", "").strip(),
			"associatedWith": row.get("Associated with", "").strip(),
			"website": row.get("Site address", "").strip(),
			"yearFounded": int(year_match.group()) if year_match else None,
		})
	return places

# Search function that filters records (the dictionaries made from the csv files) based on a query parameter. It checks if the query string is present in any of the values of the records, ignoring case and whitespace.
def matching_records(records):
	query = request.args.get("q", "").strip().casefold()	# Takes the user's search parameter, .strip() removes extra whitespaces, .casefold() makes it all lowercase so the lower or uppercase doesn't impact the search results
	if not query:
		return records										# returns to regular works if the user doesn't enter a search parameter
	return [												# returns a list of records that match the search parameter
		record for record in records
		if query in " ".join(str(value) for value in record.values()).casefold()
	]

# Flask routes - these are the endpoints that the frontend will use to access the data from the backend. The frontend will make requests to these endpoints and receive the data in json format.
# Pages - tells the page where to find the html files for each page and what the active page is (for the navigation bar)
@app.route("/")
def home_page():
	return render_template("works.html", active_page="works")


@app.route("/works")
def works_page():
	return render_template("works.html", active_page="works")


@app.route("/places")
def places_page():
	return render_template("places.html", active_page="places")


@app.route("/archive")
def archive_page():
	return render_template("archive.html", active_page="archive")

@app.route("/login")
def login_page():
	return render_template("login.html", active_page="login")


@app.route("/registration")
def registration_page():
	return render_template("registration.html", active_page="registration")


@app.route("/mylists")
def mylists_page():
	user_id = current_user_id()
	saved_places = saved_places_for_user(user_id) if user_id is not None else []
	return render_template(
		"mylists.html",
		active_page="mylists",
		is_authenticated=user_id is not None,
		saved_places=saved_places,
	)

# Artworks page
@app.route("/api/works")
def works():
	return json_response(matching_records(get_works()))

# Places page
@app.route("/api/places")
def places():
	return json_response(matching_records(get_places()))

# Visualisations page
@app.route("/api/overview")
def overview():
	all_places = get_places()
	places_by_state = {state: 0 for state in REGION_CODES}
	founded_by_year = {}
	for place in all_places:
		state = place["state"] or "Unspecified"
		places_by_state[state] = places_by_state.get(state, 0) + 1
		if place["yearFounded"]:
			year = place["yearFounded"]
			founded_by_year[year] = founded_by_year.get(year, 0) + 1
	total = 0
	founded_timeline = []
	for year, count in sorted(founded_by_year.items()):
		total += count
		founded_timeline.append({"year": year, "count": count, "total": total})
	return json_response({
		"placeCount": len(all_places),
		"FirstArtCentreFounded": min(founded_by_year.values()),
		"placesByState": places_by_state,
		"foundedTimeline": founded_timeline,
	})

#

@app.route("/api/session")
def session_status():
	user_id = current_user_id()
	if user_id is None:
		return json_response({"authenticated": False})
	return json_response({"authenticated": True, "username": session["username"]})


@app.route("/api/register", methods=["POST"])
def register():
	payload = request.get_json(silent=True)
	if not isinstance(payload, dict):
		return json_response({"error": "Provide a username and password."}), 400

	username = payload.get("username")
	password = payload.get("password")
	recovery_email_value = payload.get("recovery_email", "")
	if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_]{3,32}", username.strip()):
		return json_response({"error": "Username must be 3-32 characters: letters, numbers, or underscores."}), 400
	if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
		return json_response({"error": "Password must be 8-128 characters."}), 400
	if not isinstance(recovery_email_value, str):
		return json_response({"error": "Recovery email must be a valid email address."}), 400
	recovery_email = recovery_email_value.strip()
	if recovery_email and normalize_email(recovery_email) is None:
		return json_response({"error": "Recovery email must be a valid email address."}), 400

	username = username.strip().casefold()
	recovery_email = normalize_email(recovery_email) if recovery_email else None
	try:
		with database_connection() as connection:
			cursor = connection.execute(
				"INSERT INTO users (username, password_hash, recovery_email) VALUES (?, ?, ?)",
				(username, generate_password_hash(password), recovery_email),
			)
			user_id = cursor.lastrowid
	except sqlite3.IntegrityError:
		return json_response({"error": "That username or recovery email is already registered."}), 409

	session.clear()
	session["user_id"] = user_id
	session["username"] = username
	return json_response({"authenticated": True, "username": username}), 201


@app.route("/api/login", methods=["POST"])
def login():
	payload = request.get_json(silent=True)
	if not isinstance(payload, dict):
		return json_response({"error": "Provide a username and password."}), 400
	username = payload.get("username")
	password = payload.get("password")
	if not isinstance(username, str) or not isinstance(password, str):
		return json_response({"error": "Provide a username and password."}), 400

	with database_connection() as connection:
		connection.row_factory = sqlite3.Row
		user = connection.execute(
			"SELECT id, username, password_hash FROM users WHERE username = ?",
			(username.strip().casefold(),),
		).fetchone()
	if user is None or not check_password_hash(user["password_hash"], password):
		return json_response({"error": "Invalid username or password."}), 401

	session.clear()
	session["user_id"] = user["id"]
	session["username"] = user["username"]
	return json_response({"authenticated": True, "username": user["username"]})


@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
	payload = request.get_json(silent=True)
	email = normalize_email(payload.get("email")) if isinstance(payload, dict) else None
	if email is None:
		return json_response({"error": "Provide a valid recovery email address."}), 400
	try:
		smtp_configuration = get_smtp_configuration()
	except ValueError:
		app.logger.exception("Password reset email settings are invalid.")
		return json_response({"error": "Password reset email is not configured correctly."}), 503

	with database_connection() as connection:
		connection.row_factory = sqlite3.Row
		user = connection.execute(
			"SELECT id FROM users WHERE recovery_email = ?",
			(email,),
		).fetchone()
		if user is None:
			return json_response({
				"message": "If an account uses that recovery email, a reset link has been sent."
			})

		token = secrets.token_urlsafe(32)
		token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
		expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
		connection.execute(
			"DELETE FROM password_reset_tokens WHERE user_id = ?",
			(user["id"],),
		)
		connection.execute(
			"INSERT INTO password_reset_tokens (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
			(token_hash, user["id"], expires_at),
		)

	try:
		send_password_reset_email(email, token, smtp_configuration)
	except (OSError, smtplib.SMTPException, ValueError):
		app.logger.exception("Could not send password reset email.")
		with database_connection() as connection:
			connection.execute(
				"DELETE FROM password_reset_tokens WHERE token_hash = ?",
				(token_hash,),
			)
		return json_response({"error": "Could not send the reset email. Please try again later."}), 503

	return json_response({
		"message": "If an account uses that recovery email, a reset link has been sent."
	})


@app.route("/api/reset-password", methods=["POST"])
def reset_password():
	payload = request.get_json(silent=True)
	if not isinstance(payload, dict):
		return json_response({"error": "Provide a reset token and new password."}), 400
	token = payload.get("token")
	password = payload.get("password")
	if not isinstance(token, str) or not token or not isinstance(password, str):
		return json_response({"error": "Provide a reset token and new password."}), 400
	if len(password) < 8 or len(password) > 128:
		return json_response({"error": "Password must be 8-128 characters."}), 400

	token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
	now = datetime.now(timezone.utc).isoformat()
	with database_connection() as connection:
		connection.row_factory = sqlite3.Row
		connection.execute("BEGIN IMMEDIATE")
		reset = connection.execute(
			"SELECT user_id FROM password_reset_tokens WHERE token_hash = ? AND expires_at > ?",
			(token_hash, now),
		).fetchone()
		if reset is None:
			return json_response({"error": "This reset link is invalid or has expired."}), 400
		connection.execute(
			"UPDATE users SET password_hash = ? WHERE id = ?",
			(generate_password_hash(password), reset["user_id"]),
		)
		connection.execute(
			"DELETE FROM password_reset_tokens WHERE user_id = ?",
			(reset["user_id"],),
		)
	return json_response({"message": "Password reset. You can now log in."})


@app.route("/api/logout", methods=["POST"])
def logout():
	session.clear()
	return json_response({"authenticated": False})


@app.route("/api/myplaces", methods=["GET", "POST", "DELETE"])
def myplaces():
	user_id = current_user_id()
	if user_id is None:
		return json_response({"error": "Log in to access your saved places."}), 401

	if request.method == "GET":
		return json_response(saved_places_for_user(user_id))

	payload = request.get_json(silent=True)
	if not isinstance(payload, dict) or not isinstance(payload.get("name"), str) or not payload["name"].strip():
		return json_response({"error": "Provide a place name in the JSON body."}), 400

	name = payload["name"].strip().casefold()
	place = next((place for place in get_places() if place["name"].casefold() == name), None)
	if place is None:
		return json_response({"error": "Place not found."}), 404

	with database_connection() as connection:
		if request.method == "DELETE":
			connection.execute(
				"DELETE FROM saved_places WHERE user_id = ? AND place_name = ?",
				(user_id, place["name"]),
			)
			status_code = 200
		else:
			cursor = connection.execute(
				"INSERT OR IGNORE INTO saved_places (user_id, place_name) VALUES (?, ?)",
				(user_id, place["name"]),
			)
			status_code = 201 if cursor.rowcount else 200

	return json_response(saved_places_for_user(user_id)), status_code

if __name__ == "__main__":	# makes sure python runs the app only if the script is run directly, not if it is imported as a module in another script
	app.run(debug=False)

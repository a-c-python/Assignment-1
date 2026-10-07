#Import modules 
import csv
import os
import re
import secrets
import sqlite3
from contextlib import closing, contextmanager

# Import flask modules - web application framework
from flask import Flask, jsonify, request, send_file, session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask("__name__")	# Creates app
app.config["DATABASE"] = os.environ.get(
	"DATABASE_PATH",
	os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "app.sqlite3"),
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "").lower() == "true"
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
				password_hash TEXT NOT NULL
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
# homepage route - serves the index.html file to the frontend
@app.route("/")
def index():
	return send_file(os.path.join(BASE_DIR, "templates","index.html"))

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
		"datedPlaceCount": sum(founded_by_year.values()),
		"unrecordedFoundedCount": len(all_places) - sum(founded_by_year.values()),
		"placesByState": places_by_state,
		"foundedTimeline": founded_timeline,
	})

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
	if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_]{3,32}", username.strip()):
		return json_response({"error": "Username must be 3-32 characters: letters, numbers, or underscores."}), 400
	if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
		return json_response({"error": "Password must be 8-128 characters."}), 400

	username = username.strip().casefold()
	try:
		with database_connection() as connection:
			cursor = connection.execute(
				"INSERT INTO users (username, password_hash) VALUES (?, ?)",
				(username, generate_password_hash(password)),
			)
			user_id = cursor.lastrowid
	except sqlite3.IntegrityError:
		return json_response({"error": "That username is already registered."}), 409

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
	app.run(debug=True)		# runs the app in debug mode, which means that the server will automatically reload if the code changes and will provide detailed error messages if something goes wrong
							# MAKE SURE TO TURN OFF DEBUG MODE when you DEPLOY to a production environment - security risk

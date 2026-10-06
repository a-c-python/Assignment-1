#Import modules 
import csv
import os
import re

# Import flask modules - web application framework
from flask import Flask, jsonify, request, send_file

app = Flask("__name__")	# Creates app
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # Tells app where to find its files
REGION_CODES = ("NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT") # Gives regional codes

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


if __name__ == "__main__":	# makes sure python runs the app only if the script is run directly, not if it is imported as a module in another script
	app.run(debug=True)		# runs the app in debug mode, which means that the server will automatically reload if the code changes and will provide detailed error messages if something goes wrong
							# MAKE SURE TO TURN OFF DEBUG MODE when you DEPLOY to a production environment - security risk


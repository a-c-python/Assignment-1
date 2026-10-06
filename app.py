import csv
import os
import re

from flask import Flask, jsonify, request, send_file

app = Flask("Indigenous Art Finder Australia")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REGION_CODES = ("NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT")


def read_csv_rows(filename):
	path = os.path.join(BASE_DIR, filename)
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


def json_response(payload):
	return jsonify(payload)


def get_works():
	works = []
	for row in read_csv_rows("Draft collection works.csv"):
		date_created = row.get("Date made", "").strip()
		year_match = re.search(r"(?:18|19|20)\d{2}", date_created)
		works.append({
			"title": row.get("Title", "").strip(),
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


def get_places():
	places = []
	for row in read_csv_rows("Draft places.csv"):
		founded = row.get("Year Founded", "").strip()
		year_match = re.search(r"(?:18|19|20)\d{2}", founded)
		places.append({
			"name": row.get("Location", "").strip(),
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


def matching_records(records):
	query = request.args.get("q", "").strip().casefold()
	if not query:
		return records
	return [
		record for record in records
		if query in " ".join(str(value) for value in record.values()).casefold()
	]


@app.route("/")
def index():
	return send_file(os.path.join(BASE_DIR, "index.html"))


@app.route("/api/works")
def works():
	return json_response(matching_records(get_works()))


@app.route("/api/places")
def places():
	return json_response(matching_records(get_places()))


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


if __name__ == "__main__":
	app.run(debug=True)


import csv, json, os  # modules built into Python (no install needed)
from flask import Flask, jsonify, request, send_file  # tools taken from the Flask library

app = Flask("Indigenous Art Finder Australia")  # create the web application

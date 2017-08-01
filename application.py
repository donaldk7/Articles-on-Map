import os
import re
from flask import Flask, jsonify, render_template, request, url_for
from flask_jsglue import JSGlue

from cs50 import SQL
from helpers import lookup

# configure application
app = Flask(__name__)
JSGlue(app)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///mashup.db")

@app.route("/")
def index():
    """Render map."""
    if not os.environ.get("API_KEY"):
        raise RuntimeError("API_KEY not set")
    return render_template("index.html", key=os.environ.get("API_KEY"))

@app.route("/articles")
def articles():
    """Look up articles for geo."""
    
    #ensure parameters are present
    if not request.args.get("geo"):
        raise RuntimeError("missing geo argument")
        
    #ensure zipcode has 5 digits
    if not len(request.args.get("geo")) == 5:
        raise RuntimeError("zipcode should be 5 digits")
        
    result = lookup(request.args.get("geo"))

    return jsonify(result)

@app.route("/search")
def search():
    """Search for places that match query."""
    
    q = request.args.get("q")

    # if query is number (ie zip code)
    if q.isdigit():
        query = q + "%"
        result = db.execute("SELECT * FROM places WHERE postal_code LIKE :q", q=query)
    

    # else city and state
    # split and assign the city and state into 2 variables
    else:
        
        #if no comma present, replace with space first
        if not ',' in q:
            query = q.replace(' ', ',')
        else:
            query = q
            
        arr = query.split(',')
        city = arr[0]
        
        if len(arr) > 1:
            state = arr[1].strip()
            stateFull = state.capitalize()
    
            result = db.execute("SELECT * FROM places WHERE (admin_code1 LIKE :state OR admin_name1 Like :stateFull) AND (place_name LIKE :city)",
                city=city, state=state, stateFull=stateFull)
        
        #if just city
        else:
            result = db.execute("SELECT * FROM places WHERE place_name LIKE :city", city=city)
            
        #if result is 0, try combining the city name with a space in between
        if len(result) == 0 and len(arr) > 1:
            newCity = arr[0] + ' ' + arr[1]
            result = db.execute("SELECT * FROM places WHERE place_name LIKE :city", city=newCity)
    
    return jsonify(result)

@app.route("/update")
def update():
    """Find up to 10 places within view."""

    # ensure parameters are present
    if not request.args.get("sw"):
        raise RuntimeError("missing sw")
    if not request.args.get("ne"):
        raise RuntimeError("missing ne")

    # ensure parameters are in lat,lng format
    if not re.search("^-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?$", request.args.get("sw")):
        raise RuntimeError("invalid sw")
    if not re.search("^-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?$", request.args.get("ne")):
        raise RuntimeError("invalid ne")

    # explode southwest corner into two variables
    (sw_lat, sw_lng) = [float(s) for s in request.args.get("sw").split(",")]

    # explode northeast corner into two variables
    (ne_lat, ne_lng) = [float(s) for s in request.args.get("ne").split(",")]

    # find 10 cities within view, pseudorandomly chosen if more within view
    if (sw_lng <= ne_lng):

        # doesn't cross the antimeridian
        rows = db.execute("""SELECT * FROM places
            WHERE :sw_lat <= latitude AND latitude <= :ne_lat AND (:sw_lng <= longitude AND longitude <= :ne_lng)
            GROUP BY country_code, place_name, admin_code1
            ORDER BY RANDOM()
            LIMIT 10""",
            sw_lat=sw_lat, ne_lat=ne_lat, sw_lng=sw_lng, ne_lng=ne_lng)

    else:

        # crosses the antimeridian
        rows = db.execute("""SELECT * FROM places
            WHERE :sw_lat <= latitude AND latitude <= :ne_lat AND (:sw_lng <= longitude OR longitude <= :ne_lng)
            GROUP BY country_code, place_name, admin_code1
            ORDER BY RANDOM()
            LIMIT 10""",
            sw_lat=sw_lat, ne_lat=ne_lat, sw_lng=sw_lng, ne_lng=ne_lng)

    # output places as JSON
    return jsonify(rows)

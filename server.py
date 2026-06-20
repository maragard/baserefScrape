import json
import sys
import os
import sqlite3
import csv
import pickle
from django.conf import settings
from django.core.management import execute_from_command_line
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.urls import re_path
from django.core.wsgi import get_wsgi_application

DB_PATH = os.path.join(os.path.dirname(__file__), "players-temp.db")
CSV_PATH = os.path.join(os.path.dirname(__file__), "players.csv")

settings.configure(
    DEBUG=True,
    SECRET_KEY="replace-me",
    ROOT_URLCONF=__name__,
    ALLOWED_HOSTS=["*"],
    MIDDLEWARE=[],
    INSTALLED_APPS=[],
    CONN_MAX_AGE=None,
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": DB_PATH
        }
    }
)

def init_db(db_path=DB_PATH, csv_path=CSV_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Create a simple players table if not exists
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY,
            name TEXT,
            team TEXT,
            position TEXT,
            debut_year TEXT,
            retirement_year TEXT,
            plate_apps TEXT,
            avg TEXT,
            obp TEXT,
            slg TEXT
        )
        """
    )

    # If CSV exists and table is empty, import rows from CSV
    cur.execute("SELECT COUNT(1) FROM players")
    count = cur.fetchone()[0]
    if count == 0 and os.path.exists(csv_path):
        with open(csv_path, newline='', encoding='latin-1') as f:
            reader = csv.DictReader(f)
            rows = []
            for r in reader:
                # Expecting columns: id,name,team,position (non-strict)
                rows.append(
                    (
                        int(r.get('id')) if r.get('id') else None,
                        r.get('Player Name'),
                        r.get('Team(s)'),
                        r.get('Position(s)'),
                        r.get('Debut Year'),
                        r.get('Retirement Year'),
                        r.get('PA'),
                        r.get('AVG'),
                        r.get('OBP'),
                        r.get('SLG')
                    )
                )
            if rows:
                # Insert ignoring id None (will auto-increment)
                for row in rows:
                    if row[0] is None:
                        cur.execute(
                            "INSERT INTO players (name, team, position, debut_year, retirement_year, plate_apps, avg, obp, slg) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9]),
                        )
                    else:
                        cur.execute(
                            "INSERT OR REPLACE INTO players (id, name, team, position, debut_year, retirement_year, plate_apps, avg, obp, slg) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            row,
                        )
        conn.commit()
    conn.close()


init_db()

application = get_wsgi_application()

def select_new_player():
    conn = sqlite3.connect(DB_PATH)
    curr = conn.cursor()
    the_player = curr.execute("SELECT name FROM players ORDER BY RANDOM() LIMIT 1").fetchone()[0]
    conn.close()
    with open("./todaysplayer.pkl", "wb") as pick:
        pickle.dump(the_player, pick)
    return

def guess_player(request):
    """
    
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    try:
        body = request.body.decode("utf-8")
        print(body)
        data = json.loads(body) if body else {}
        print(data)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    unique_id = data.get("id")
    guess_name = data.get("name")
    if not unique_id or not guess_name:
        return HttpResponseBadRequest(f"Missing necessary fields")
    
    if guess_name and guess_name == chosen:
        return JsonResponse({"success": True, "msg": "You did it!"})
        
    elif unique_id:
        #Lookup name associated with id in db
        #Match guess from id to global chosen
        #report success or failure
        return
    else:
        return JsonResponse({"success": False, "msg": "Try again"})




def search_string(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    value = request.POST.get("value")
    print(value)
    if value is None:
        return HttpResponseBadRequest("Missing 'value' query parameter")


    # TODO: Lookup string in DB and return player
    return JsonResponse({"received_string": value})


urlpatterns = [
    re_path(r"^guess-player/$", guess_player),
    re_path(r"^get-players/$", search_string),
]


if __name__ == "__main__":
    global chosen
    if not os.path.exists('./todaysplayer.pickle'):
        select_new_player()
    with open("./todaysplayer.pkl", "rb") as pick:
        chosen  = pickle.load(pick)
    execute_from_command_line(sys.argv)

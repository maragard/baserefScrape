import json
import sys
import os
import sqlite3
import csv
from django.conf import settings
from django.core.management import execute_from_command_line
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.urls import re_path
from django.core.wsgi import get_wsgi_application

settings.configure(
    DEBUG=True,
    SECRET_KEY="replace-me",
    ROOT_URLCONF=__name__,
    ALLOWED_HOSTS=["*"],
    MIDDLEWARE=[],
    INSTALLED_APPS=[],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "players-temp.db")
CSV_PATH = os.path.join(os.path.dirname(__file__), "players.csv")


def init_db(db_path=DB_PATH, csv_path=CSV_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Create a simple players table if not exists
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY,
            name TEXT,
            team(s) TEXT,
            position(s) TEXT,

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
                        r.get('name'),
                        r.get('team'),
                        r.get('position'),
                    )
                )
            if rows:
                # Insert ignoring id None (will auto-increment)
                for row in rows:
                    if row[0] is None:
                        cur.execute(
                            "INSERT INTO players (name, team, position) VALUES (?, ?, ?)",
                            (row[1], row[2], row[3]),
                        )
                    else:
                        cur.execute(
                            "INSERT OR REPLACE INTO players (id, name, team, position) VALUES (?, ?, ?, ?)",
                            row,
                        )
        conn.commit()
    conn.close()


init_db()

application = get_wsgi_application()


def post_id(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    try:
        body = request.body.decode("utf-8")
        data = json.loads(body) if body else {}
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    unique_id = data.get("id")
    if not unique_id:
        return HttpResponseBadRequest("Missing 'id' field")

    return JsonResponse({"received_id": unique_id})


def get_string(request):
    if request.method != "GET":
        return HttpResponseBadRequest("GET required")

    value = request.GET.get("value")
    if value is None:
        return HttpResponseBadRequest("Missing 'value' query parameter")

    return JsonResponse({"received_string": value})


urlpatterns = [
    re_path(r"^post-id/$", post_id),
    re_path(r"^get-string/$", get_string),
]


if __name__ == "__main__":
    execute_from_command_line(sys.argv)

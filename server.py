import csv
import json
import os
import re
import sqlite3
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from urllib.parse import parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "players-temp.db")
CSV_PATH = os.path.join(BASE_DIR, "players.csv")
PLAYER_FILE = os.path.join(BASE_DIR, "todaysplayer.pkl")

NAME_DETECTOR = re.compile(r"\w+(\s){1}\w+")

app = FastAPI()
application = app

chosen = ""
statline = ""


def init_db(db_path=DB_PATH, csv_path=CSV_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

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

    cur.execute("SELECT COUNT(1) FROM players")
    count = cur.fetchone()[0]

    if count == 0 and os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="latin-1") as file:
            reader = csv.DictReader(file)

            for row in reader:
                player_id = int(row["id"]) if row.get("id") else None
                values = (
                    row.get("Player Name"),
                    row.get("Team(s)"),
                    row.get("Position(s)"),
                    row.get("Debut Year"),
                    row.get("Retirement Year"),
                    row.get("PA"),
                    row.get("AVG"),
                    row.get("OBP"),
                    row.get("SLG"),
                )

                if player_id is None:
                    cur.execute(
                        """
                        INSERT INTO players
                        (name, team, position, debut_year, retirement_year,
                         plate_apps, avg, obp, slg)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        values,
                    )
                else:
                    cur.execute(
                        """
                        INSERT OR REPLACE INTO players
                        (id, name, team, position, debut_year, retirement_year,
                         plate_apps, avg, obp, slg)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (player_id, *values),
                    )

        conn.commit()

    conn.close()


def select_new_player():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    player = cursor.execute(
        """
        SELECT id, name, avg, obp, slg
        FROM players
        ORDER BY RANDOM()
        LIMIT 1
        """
    ).fetchone()

    conn.close()

    with open(PLAYER_FILE, "w", encoding="utf-8") as file:
        if player:
            values = [
                f"'{value}'"
                if NAME_DETECTOR.match(str(value))
                else str(value)
                for value in player
            ]
            file.write(", ".join(values))


def load_current_player():
    global chosen, statline

    if not os.path.exists(PLAYER_FILE) or os.path.getsize(PLAYER_FILE) == 0:
        select_new_player()

    if not os.path.exists(PLAYER_FILE):
        return

    with open(PLAYER_FILE, "r", encoding="utf-8") as file:
        target = file.read()

    parts = target.split(", ")
    if len(parts) >= 5:
        chosen = parts[1].strip("'")
        statline = "/".join(parts[2:]).strip("'")


@app.get("/start")
async def starting_info():
    return {"hint": statline}


@app.post("/guess-player")
async def guess_player(request: Request):
    try:
        data = await request.json()
    except (json.JSONDecodeError, ValueError):
        return PlainTextResponse("Invalid JSON", status_code=400)

    unique_id = data.get("id")
    guess_name = data.get("name")

    if unique_id is None and not guess_name:
        return PlainTextResponse("Missing necessary fields", status_code=400)

    if guess_name and guess_name == chosen:
        return {"success": True, "msg": "You did it!"}

    if unique_id is not None:
        conn = sqlite3.connect(DB_PATH)
        player = conn.execute(
            "SELECT name FROM players WHERE id = ?",
            (unique_id,),
        ).fetchone()
        conn.close()

        success = bool(player and player[0] == chosen)
        return {
            "success": success,
            "msg": "You did it!" if success else "Try again",
        }

    return {"success": False, "msg": "Try again"}


@app.post("/get-players")
async def search_string(request: Request):
    body = await request.body()
    content_type = request.headers.get("content-type", "")

    value = None

    if "application/json" in content_type:
        try:
            value = json.loads(body.decode("utf-8")).get("value")
        except (json.JSONDecodeError, ValueError):
            return PlainTextResponse("Invalid JSON", status_code=400)
    else:
        values = parse_qs(body.decode("utf-8"))
        value = values.get("value", [None])[0]

    if value is None:
        return PlainTextResponse(
            "Missing 'value' query parameter",
            status_code=400,
        )

    return {"received_string": value}


init_db()
load_current_player()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
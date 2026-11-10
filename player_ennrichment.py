import csv
import json
import logging
import pandas as pd
import random
import re
import requests as req
from bs4 import BeautifulSoup, element
from concurrent.futures import ThreadPoolExecutor

bad_team = re.compile("(,)?(\\dTM)")

def position_filter(s: str):
    pos = s.lower()
    if pos.startswith("first basem"):
        return "1B"
    elif pos.startswith("second basem"):
        return "2B"
    elif pos.startswith("third basem"):
        return "3B"
    elif pos.startswith("catcher"):
        return "C"
    elif pos.startswith("designated hit"):
        return "DH"
    elif pos.startswith("shortstop"):
        return "SS"
    elif pos.startswith("left field") or pos.startswith("leftfielder"):
        return "LF"
    elif pos.startswith("center field") or pos.startswith("centerfielder"):
        return "CF"
    elif pos.startswith("right field") or pos.startswith("rightfielder"):
        return "RF"
    elif pos.startswith("outfielder"):
        return "OF"
    elif pos.startswith("pitcher"):
        return "P"
    else:
        return ""


def main():
    new_rows = []
    with open("./players.csv", newline='', encoding="latin-1") as f:
        reader = csv.DictReader(f)
        dataset = list(reader)
        cols = reader.fieldnames
    # dataset = pd.read_csv("./players.csv")
    # names = list(dataset['Player Name'])
    # print(names)
    for row in dataset[:20]:
        print(row['Player Name'])
        # Fix teams
        print(row['Team(s)'])
        new_teams = ",".join([team for team in row['Team(s)'].split(',') if not bad_team.match(team)])
        print(new_teams)
        row['Team(s)'] = new_teams
        # Reformat Positions
        print(row['Position(s)'])
        new_pos = ",".join([position_filter(pos) for pos in re.split(r"\s+and\s+|,\s*", row['Position(s)']) if bool(position_filter(pos))])
        print(new_pos)
        row['Position(s)'] = new_pos
        # Rescrape
        # attempt = 1
        # fname, lname = row['Player Name'].lower().split(" ")
        # slug = f"players/{lname[0]}/{lname[:5]}{fname[:2]}{attempt:0>2}.shtml"
        # url = f"https://www.baseball-reference.com/{slug}"
        # try:
        #     resp = req.get(url)
        #     resp.raise_for_status()
        # except req.RequestException as e:
        #     return
        # else:
        #     print(resp)
            # soup = BeautifulSoup(resp.content, 'lxml', from_encoding="latin-1")

            # Step 1: Confirm that this is the one we are looking for

            # Step 2: Fetch what we are looking for

            #   a. Last team played for

            #   b. Jersey Number

            #   c.

            
            

    return



# Rescrape Negro Leagues
def build_teams_negro_leagues():
    """
    Build dictionary of teams from list.
    """
    def _sufficient_games(franchise: element.Tag):
        return franchise.name == 'tr' and int(franchise('td')[2].get_text()) >= 50

    URL = "https://www.seamheads.com/NegroLgs/history.php?tab=tm_at&first=1886&last=1948&lgID=All&lgType=N"
    abbrs = []
    names = []

    try:
        resp = req.get(URL)
    except req.RequestException as e:
        raise e
    else:
        soup = BeautifulSoup(resp.text, 'lxml')
        team_table = soup.find('table', class_="main_table").find('tbody')
        if team_table:
            rows = team_table(_sufficient_games)
            print(len(rows))
            for row in rows:
                cells = row('td')
                team_full_name = cells[1].get_text(strip=True)
                team_abbrviate = cells[1].div.a['href'].split('=')[-1]
                names.append(team_full_name)
                abbrs.append(team_abbrviate)

    print(abbrs)
    check = pd.Series(abbrs)
    print(check)
    if not check.duplicated().any():
        final = {a: b for a, b in zip(abbrs, names)}
        print(final)
        with open("negro_pro_teams.json", 'w') as file:
            json.dump(final, file)
    return



if __name__ == "__main__":
    main()
    # COMPLETE
    #build_teams_negro_leagues()
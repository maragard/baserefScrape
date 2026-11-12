import csv
import json
import logging
import pandas as pd
import random
import re
import requests as req
from bs4 import BeautifulSoup, element
from concurrent.futures import ThreadPoolExecutor
from statistics import mode
from time import sleep

bad_team = re.compile("\\dTM")
bad_league = re.compile("\\dLG")

def position_filter(s: str) -> str:
    if s in {"1B", "2B", "3B", "C", "DH", "SS", "LF", "CF", "RF", "OF", "P"}:
        return s

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
    elif pos.startswith(("leftfielder", "left field")):
        return "LF"
    elif pos.startswith(("centerfielder", "center field")):
        return "CF"
    elif pos.startswith(("rightfielder", "right field")):
        return "RF"
    elif pos.startswith("outfielder"):
        return "OF"
    elif pos.startswith("pitcher"):
        return "P"
    else:
        return ""


def main():
    new_rows = []
    with open("./players.csv", newline='') as f:
        reader = csv.DictReader(f)
        dataset = list(reader)
        # cols = reader.fieldnames
    for row in dataset[67::420]:
        print(row['Player Name'])
        # Fix statistics
        avg = float(row['AVG'])
        row['AVG'] = f"{avg:.3f}"[1:]
        obp = float(row['OBP'])
        row['OBP'] = f"{obp:.3f}"[1:]
        slg = float(row['SLG'])
        row['SLG'] = f"{slg:.3f}"[1:]
        # # Fix teams
        # print(row['Team(s)'])
        # new_teams = ",".join(
        #                     [
        #                         team
        #                         for team
        #                         in row['Team(s)'].split(',')
        #                         if not bad_team.match(team)
        #                     ]
        #                 )
        # print(new_teams)
        # row['Team(s)'] = new_teams
        # Reformat Positions
        print(row['Position(s)'])
        new_pos = ",".join(
                            [
                                position_filter(pos)
                                for pos
                                in re.split(r"\s+and\s+|,\s*", row['Position(s)'])
                                if bool(position_filter(pos))
                            ]
                        )
        print(new_pos)
        row['Position(s)'] = new_pos
        # Rescrape
        print("beginning rescrape")
        url = f"https://www.baseball-reference.com/search/search.fcgi?hint=&search={row['Player Name']}&pid=&idx="
        try:
            resp = req.get(url)
            resp.raise_for_status()
        except req.RequestException as e:
            raise e
        else: 
            # else block MUST end in a state that scraping can continue under "finally" or fail out
            if '/players/' in resp.url:
                # Branch 1: We get redirected to player page
                print("redirected to player")
                row['URL'] = resp.url
                soup = BeautifulSoup(resp.content, 'lxml')
            elif 'search' in resp.url:
                # Branch 2: We remain on search page
                print("searching for player")
                search_soup = BeautifulSoup(resp.content, 'lxml')
                for search_result in search_soup('div', class_='search-item'):
                    career_start, career_final = re.findall(r'\d{4}', search_result.a.text)
                    if row['Debut Year'] == career_start and (row['Retirement Year'] == career_final or row['Retirement Year'] == 'Not Found'):
                        print('found player')
                        row['URL'] = "https://www.baseball-reference.com" + search_result.a.get("href")
                        sleep(random.randint(10, 15))
                        try:
                            player_resp = req.get(row['URL'])
                            player_resp.raise_for_status()
                        except req.RequestException as e:
                            raise e
                        else:
                            soup = BeautifulSoup(player_resp.content, 'lxml')
                            break
                    sleep(random.randint(5, 15))
        finally:
            def _rows_no_spacers(tag: element.Tag) -> bool:
                return tag.name == 'tr' and (not tag.get('class') or 'spacer' not in tag.get('class'))

            sleep(random.randint(10, 25))
            data_table = soup.find('table', attrs={'id':'players_standard_batting'}).find('tbody')
            # Step 2: Fetch what we are looking for
            row['Born'] = soup.find('span', id='necro-birth').get('data-birth')
            row['Died'] = soup.find('span', id='necro-death').get('data-death') if soup.find('span', id='necro-death') else 'Alive'
            if row['Retirement Year'] == 'Not Found':
                if row['Died'] != 'Alive':
                    last_year_row = data_table('tr')[-1]
                    row['Retirement Year'] = last_year_row.th.text
                else:
                    row['Retirement Year'] = "Active"
            #   a. Last team played for
            row['Final Team'] = data_table(_rows_no_spacers)[-1].find('td', attrs={'data-stat': 'team_name_abbr'}).text
            all_teams = [
                tag.find('td', attrs={'data-stat': 'team_name_abbr'}).text 
                for tag 
                in data_table(_rows_no_spacers)
                if not bad_team.match(tag.find('td', attrs={'data-stat': 'team_name_abbr'}).text)
                and len(tag.find('td', attrs={'data-stat': 'team_name_abbr'}).text) <= 3
            ]
            row['Team(s)'] = ','.join(set(all_teams))
            row['Longest Team'] = mode(all_teams)
            #   b. Jersey Number(s)
            # for number_medal in soup.find('div', class_='uni_holder br')('a'):
            #     num = number_medal.get_text(strip=True)
            #     # Year and franchise info would need to be extrated from this string
            #     num_info = number_medal.get('data-tip')
            #   c. Leagues
            row['Leagues'] = ','.join(
                                    set(
                                        [
                                            league.find('td', attrs={'data-stat': 'comp_name_abbr'}).get_text(strip=True)
                                            for league
                                            in data_table(_rows_no_spacers)
                                            if league.find('td', attrs={'data-stat': 'comp_name_abbr'}) and not bad_league.match(league.find('td', attrs={'data-stat': 'comp_name_abbr'}).get_text(strip=True))
                                        ]
                                    )
                                )
            print(row)
            new_rows.append(row)
                     
    print(new_rows)
    # with open('players_enhanced.csv', 'w', newline='') as newfile:
    #     writer = csv.DictWriter(newfile, fieldnames=cols)
    #     writer.writeheader()
    #     writer.writerows(new_rows)
    return



# Rescrape Negro Leagues
def build_teams_negro_leagues():
    """
    Build dictionary of teams from list.
    """
    def _sufficient_games(franchise: element.Tag):
        return franchise.name == 'tr' and int(franchise('td')[2].get_text()) >= 1

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

def scrape_negro_leagues_seamhead():
    URL = "https://www.seamheads.com/NegroLgs/history.php?tab=bat_basic_at&first=1886&last=1948&lgID=All&lgType=N&HOF=All&pos=All&bats=All&minPA=500&results=500&sort=PA_a"
    return


if __name__ == "__main__":
    main()
    # COMPLETE
    # build_teams_negro_leagues()
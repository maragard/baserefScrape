import argparse
import csv
import logging
import pandas as pd
import random
import re
import requests
import string
import time
from bs4 import BeautifulSoup
from bs4.element import Tag
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
file_format = logging.Formatter('%(asctime)s %(threadName)s %(levelname)s %(message)s')
logfile = logging.FileHandler('base_scrape.log', mode='w')
logfile.setLevel(logging.DEBUG)
logfile.setFormatter(file_format)
stream_format = logging.Formatter('%(threadName)s %(levelname)s %(message)s')
logstream = logging.StreamHandler()
logstream.setLevel(logging.INFO)
logstream.setFormatter(stream_format)
logger.addHandler(logstream)
logger.addHandler(logfile)

# Add: debut year, retirement year(if eligible), team(s) played for

DATA_COLS = ["b_pa", "b_batting_avg", "b_onbase_perc", "b_slugging_perc"]
SORTED_COLUMNS = ["Player Name", "Position(s)", "Team(s)", "Debut Year", "Retirement Year", "PA", "AVG", "OBP", "SLG"]

#Filter func for use with BeautifulSoup's find_all() to find parts of rows we need
def _column_we_care_about(tag: Tag) -> bool:
    return tag.name in ['th', 'td'] and'data-stat' in tag.attrs.keys() and tag.get('data-stat') in DATA_COLS

#Filter func for use with BeautifulSoup's find_all() to find parts of the 'info' div that we need
def _has_data(tag: Tag) -> bool:
    return tag.name == 'p' and len(tag.contents) > 1

year = re.compile(r"\d{4}")

def sort_player_names(names: pd.Series) -> pd.Series:
    """Create last-name, then first-name sort keys for DataFrame.sort_values()."""
    def sort_key(name: str) -> tuple[str, str]:
        first, _, last = name.strip().rpartition(" ")
        return last.casefold(), first.casefold()

    return names.map(sort_key)

def timing(f):
    @wraps(f)
    def wrap(*args, **kw):
        start_time = time.time()
        result = f(*args, **kw)
        end_time = time.time()
        logger.debug(f'func:{f.__name__} args:[{args}, {kw}] took: {(end_time-start_time):2.4f} sec')
        return result
    return wrap

class ScrapeFromSeasonBatting:
    
    def __init__(self):
        return 

    url = "https://www.baseball-reference.com/leagues/majors/2025-standard-batting.shtml"
    table_id = "players_standard_batting"

    def parse_table(self, table):
        headers = [th.get_text(strip=True) for th in table.find("thead").find_all("th")]
        rows = []

        for row in table.find("tbody").find_all("tr"):
            if row.get("class") and "thead" in row.get("class"):
                continue
            cells = [cell.get_text(strip=True) for cell in row("td")]
            if not cells:
                continue
            row_data = dict(zip(headers, cells))
            rows.append(row_data)

        return rows

    def get_batting_stats(self):
        try:
            response = requests.get(self.url)
            response.raise_for_status()
        except requests.RequestException as e:
            return None
        else:
            html = response.text
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", id=self.table_id)
        if table is None:  
            return None
        return self.parse_table(table)
    
class ScrapeFromPlayerGlossary:

    url = "https://www.baseball-reference.com/"
    table_id = "players_standard_batting"

    def __init__(self):
        self.data = []
        return

    # def parse_table(self, table):
    #     headers = [th.get_text(strip=True) for th in table.find("thead").find_all("th") if _column_we_care_about(th.get('data-stat'))]
    #     rows = []

    #     for row in table("tr", id=f"{self.table_id}.Yrs"):
    #         print(row)
    #         cells = [cell.get_text(strip=True) for cell in row("td") if _column_we_care_about(cell.get('data-stat'))]
    #         if not cells:
    #             continue
    #         row_data = dict(zip(headers, cells))
    #         rows.append(row_data)

    #     return rows

    def serialize_data(self, filename: str, **kwarg) -> None:
        if not bool(self.data):
            logger.debug("No data")
            return
        df = pd.DataFrame(self.data)
        logger.debug(f"Data: {len(df)} rows\n")
        df.rename(columns={"BA": "AVG"}, inplace=True)
        df = df.loc[:, SORTED_COLUMNS]
        if kwarg.get('method') == 'append':
            df_old = pd.read_csv(f"./{filename}.csv")
            new_df = pd.concat([df_old, df], ignore_index=True)
            logger.debug(len(new_df))
            new_df.to_csv(f"./{filename}.csv", index=False)
            return
        # df.sort_values("Player Name", key=sort_player_names, inplace=True)
        df.to_csv(f"./{filename}.csv", index=False)
        return

    @timing
    def scrape_by_letter(self, letter: str) -> list[str]:
        scrape_url = f"{self.url}players/{letter}/"
        try:
            resp = requests.get(scrape_url)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Encountered {e}")
            return None
        else:
            soup = BeautifulSoup(resp.content, "lxml")
            players = soup.find('div', class_="section_content")('p')
            players = [tag.find('a').get('href') for tag in players]
  
        return players

    @timing
    def build_player_list(self, limit: int | str = None) -> list[str]:
        full_player_list = []
        allchars = list(string.ascii_lowercase)
        #Limit on how much we scrape
        if (isinstance(limit, int) and limit < len(allchars)) or limit is None:
            for char in allchars[:limit]:
                full_player_list += self.scrape_by_letter(char)
                time.sleep(random.randint(10, 30))
        elif isinstance(limit, str) and limit in allchars:
            for char in allchars:
                if char is not limit:
                    full_player_list += self.scrape_by_letter(char)
                    time.sleep(random.randint(10, 30))
                else:
                    break
        else:
            logger.critical(f"Incorrect input provided for 'limit': {limit}")
        return full_player_list
    
    def scrape_player(self, player_slug: str) -> None:
        time.sleep(random.randint(10, 45))
        scrape_url = f"{self.url}{player_slug}"
        try:
            resp = requests.get(scrape_url)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Encountered {e}")
            self.data.append(None)
            return
        else:
            soup = BeautifulSoup(resp.content, 'lxml', from_encoding="latin-1")

        name = soup.find('div', id='info')('h1')[0].get_text(strip=True)
        logger.info(name)
        table = soup.find("table", id=self.table_id)
        if table is None:
            logger.warning(f"{name} -- Not Eligible: No batting data")
            self.data.append(None)
            time.sleep(60)
            return
        
        lifetime_batting_data = table.find('tr', id=f"{self.table_id}.Yrs")
        if lifetime_batting_data:
            headers = [th.get_text(strip=True) for th in table.find("thead").find_all(_column_we_care_about)]
            # print(headers)
            row_data = [td.get_text(strip=True) for td in lifetime_batting_data(_column_we_care_about)]
            logger.debug(row_data)
            datum = dict(zip(headers, row_data))

            # Players must have at least 900 plate apperances
            if int(datum['PA']) < 900:
                logger.warning(f"{name} -- Not Eligible: Insufficient batting data") 
                self.data.append(None)
                time.sleep(60)
                return
            else:
                # Teams must be harvested from the tbody
                teams = set([
                    row.find('td', attrs={'data-stat': 'team_name_abbr'}).get_text(strip=True)
                    for row 
                    in table.find('tbody').find_all('tr')
                ])
                #All data about player is in the div w/ id 'info'.
                #If player is active or retires, or depending on records quality,
                # the list of p tags varies. Reconfigure _has_data() to adjust how we find 
                # tags with data.
                general_info = [tag.get_text(strip=True) for tag in soup.find('div', id='info')(_has_data)]
                logger.debug(general_info)
                #TODO: write func to parse down positions (e.g. "First Baseman and Left Field" ==> "1B/LF")
                position_maybe = [tag for tag in general_info if 'Position' in tag]
                debut_maybe = [tag for tag in general_info if 'Debut' in tag]
                retire_maybe = [tag for tag in general_info if 'Last Game' in tag]
                logger.debug(position_maybe)
                
                try:
                    datum["Position(s)"] = position_maybe[0].split(":")[1]
                except IndexError:
                    datum['Position(s)'] = "Not Found"
                
                # TODO: Compute 'era' of player based on debut & retirement year
                try:
                    datum["Retirement Year"] = year.search(retire_maybe[0]).group(0)
                except IndexError:
                    datum["Retirement Year"] = "Not Found"
                datum['Debut Year'] = year.search(debut_maybe[0]).group(0)
                datum["Player Name"] = name
                datum['Team(s)'] = ','.join([team for team in teams if len(team) == 3])

                # print(datum)
                logger.info(f"{name} -- Successfully scraped")
                self.data.append(datum)
                time.sleep(30)
                return

    @timing
    def scrape_from_point(self) -> None:
        """
        Being scraping from the last player serialized.
        """
        players = self.build_player_list(limit='j')
        logger.debug(players[::420])
        logger.info(f"{len(players)} to process")
        # Seek from EOF to read only the final CSV record, rather than loading
        # the entire file. The first field is the player name.
        with open("players.csv", "rb") as file:
            file.seek(0, 2)
            pos = file.tell() - 1
            if pos < 0:
                return
            file.seek(pos)
            if file.read(1) == b"\n":
                pos -= 1
            while pos >= 0:
                file.seek(pos)
                if file.read(1) == b"\n":
                    pos += 1
                    break
                pos -= 1
            # Locate the beginning of the record immediately before the last one.
            fallback_pos = pos - 2
            while fallback_pos >= 0:
                file.seek(fallback_pos)
                if file.read(1) == b"\n":
                    fallback_pos += 1
                    break
                fallback_pos -= 1
            file.seek(max(fallback_pos, 0))
            fall_back = file.readline().decode("utf-8-sig").rstrip("\r\n")
            file.seek(max(pos, 0))
            last_line = file.readline().decode("utf-8-sig").rstrip("\r\n")

        latest_player = next(csv.reader([last_line]))[0]
        backup_player = next(csv.reader([fall_back]))[0]
        logger.debug(f"Last player in players.csv: {latest_player}\n\t\t\t\t\t\tBackup player: {backup_player}")
        try:
            fname, lname = latest_player.lower().split(" ")
            lp_slug = f"/players/{lname[0]}/{lname[:5]}{fname[:2]}01.shtml"
            logger.info(lp_slug)
            separator = players.index(lp_slug)
        except ValueError:
            logger.critical(f"Starting point {latest_player} not found in data from site")
            return
        else:
            remaining = players[separator+1:]
            logger.info(f"{len(remaining)} players")
            with ThreadPoolExecutor(max_workers=8) as exec:
                exec.map(self.scrape_player, remaining)
            self.data = [i for i in self.data if i is not None]
            return

    @timing
    def scrape_all_fresh(self) -> None:
        players = self.build_player_list(limit='c')
        logger.debug(players[::420])
        logger.info(f"{len(players)} to process")
        with ThreadPoolExecutor(max_workers=8) as exec:
            exec.map(self.scrape_player, players)
        self.data = [i for i in self.data if i is not None]
        return

# def main():
#     # stats = ScrapeFromSeasonBatting().get_batting_stats()
#     # print(len(stats))
#     # for index, row in enumerate(stats[:20], start=1):
#     #     print(index, row)
#     scraper = ScrapeFromPlayerGlossary()
#     start_time = time.time()

#     #Logic below can be condensed
#     players = scraper.build_player_list(limit='c')
#     list_acq_time = time.time()
#     logger.info(f"Compiled list of {len(players)} players in {list_acq_time - start_time} seconds")
#     print(players[::420])
#     print(len(players))
#     with ThreadPoolExecutor(max_workers=8) as exec:
#         exec.map(scraper.scrape_player, players)
#     # for player in players[:]:
#     #     time.sleep(30)
#     #     data = scraper.scrape_player(player)
#     #     if data is not None:
#     #         player_data.append(data)
#         # print(scraper.scrape_player(player))
#     scraper.data = [i for i in scraper.data if i is not None]
#     scrape_complete = time.time()
#     logger.info(f"Acquired {len(scraper.data)} in {scrape_complete - start_time} seconds")
#     # print(len(scraper.data)) 
#     # print(scraper.data[-5:])
#     scraper.serialize_data(filename="players")
#     end_time = time.time()
#     logger.info(f"Total runtime: {end_time - start_time} seconds")



if __name__ == "__main__":
    scraper = ScrapeFromPlayerGlossary()
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=['fresh', 'restart'])
    # parser.add_argument("--stopping-point", "-sp", action='store', type=str)
    args = parser.parse_args()

    if args.mode == 'fresh':
        scraper.scrape_all_fresh()
        scraper.serialize_data(filename="players")
    elif args.mode == 'restart':
        scraper.scrape_from_point()
        scraper.serialize_data(filename="players", method='append')
    else:
        logger.error(f"Invalid mode: {args.mode}")

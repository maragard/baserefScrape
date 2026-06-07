import time
import requests
import string
import pandas as pd
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)
logfile = logging.FileHandler('base_scrape.log')
logfile.setLevel(logging.DEBUG)
logstream = logging.StreamHandler()
logstream.setLevel(logging.INFO)
logger.addHandler(logfile)
logger.addHandler(logstream)

DATA_COLS = ["b_pa", "b_batting_avg", "b_onbase_perc", "b_slugging_perc"]
SORTED_COLUMNS = ["Name", "Position(s)", "PA", "AVG", "OBP", "SLG"]

def _column_we_care_about(column_data_stat_val):
    return column_data_stat_val in DATA_COLS

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

    def scrape_by_letter(self, letter):
        scrape_url = f"{self.url}players/{letter}/"
        try:
            resp = requests.get(scrape_url)
            resp.raise_for_status()
        except requests.RequestException as e:
            return None
        else:
            soup = BeautifulSoup(resp.text, "lxml")
            players = soup.find('div', class_="section_content")('p')
            players = [tag.find('a').get('href') for tag in players]
  
        return players

    def build_player_list(self):
        full_player_list = []
        allchars = list(string.ascii_lowercase)
        #Limit on how much we scrape
        for char in allchars[:1]:
            full_player_list += self.scrape_by_letter(char)
            time.sleep(30)
        return full_player_list
    
    def scrape_player(self, player_slug):
        scrape_url = f"{self.url}{player_slug}"
        try:
            resp = requests.get(scrape_url)
            resp.raise_for_status()
        except requests.RequestException as e:
            return None
        else:
            soup = BeautifulSoup(resp.text, 'lxml')

        name = soup.find('div', id='info')('h1')[0].get_text(strip=True)
        logger.info(name)
        table = soup.find("table", id=self.table_id)
        if table is None:
            logger.warning("Not Eligible: No batting data")
            return None
        
        lifetime_batting_data = table.find('tr', id=f"{self.table_id}.Yrs")
        if lifetime_batting_data:
            headers = [th.get_text(strip=True) for th in table.find("thead").find_all("th") if _column_we_care_about(th.get('data-stat'))]
            # print(headers)
            row_data = [td.get_text(strip=True) for td in lifetime_batting_data('td') if _column_we_care_about(td.get('data-stat'))]
            logger.debug(row_data)
            datum = dict(zip(headers, row_data))
            
            datum["Player Name"] = name

            #Position is in the very first paragraph in div, MOST TIMES
            logger.debug(soup.find('div', id='info')('p'))
            position_maybe = [
                tag.get_text(strip=True)
                for tag
                in soup.find('div', id='info')('p')[:]
                if 'Position' in tag.get_text(strip=True)]
            logger.info(position_maybe)
            datum["Position(s)"] = position_maybe[0].split(":")[1]

            # print(datum)
            # Players must have at least 900 plate apperances
            if int(datum['PA']) < 900:
                logger.warning("Not Eligible: Insufficient batting data") 
                return None
            else:
                return datum

def main():
    # stats = ScrapeFromSeasonBatting().get_batting_stats()
    # print(len(stats))
    # for index, row in enumerate(stats[:20], start=1):
    #     print(index, row)
    scraper = ScrapeFromPlayerGlossary()

    #Logic below can be condensed
    players = scraper.build_player_list()
    print(players[::420])
    print(len(players))
    player_data = []
    for player in players[:]:
        time.sleep(30)
        data = scraper.scrape_player(player)
        if data is not None:
            player_data.append(data)
        # print(scraper.scrape_player(player))
    print(len(player_data)) 
    print(player_data[-5:])



if __name__ == "__main__":
    main()

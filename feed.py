import argparse
import json
import math
import os
import random
import queue
import re
import requests
import time
import nodriver as uc

from bs4 import BeautifulSoup as BS
from shared import *
from datetime import datetime, timedelta

def commitChanges():
	repo = git.Repo(".")
	repo.git.add(A=True)
	repo.index.commit("test")

	origin = repo.remote(name="origin")
	origin.push()

async def writeFeed(date, loop):
	if not date:
		date = str(datetime.now())[:10]
	url = f"https://baseballsavant.mlb.com/gamefeed?date={date}&hf=exitVelocity"
	browser = await uc.start(no_sandbox=True)
	page = await browser.get(url)
	await page.wait_for(selector=".container-open")
	time.sleep(5)

	#b = await page.query_selector("#btnHide")
	#await b.click()

	# click exit velo table
	if False:
		o = await page.query_selector(".container-open")
		id = o.get("id").split("-")[-1]
		#print(id)
		await o.click()
		btn = await page.query_selector(f"#button_exitVelocity_{id}")
		await btn.click()

	with open("feed_times.json") as fh:
		times = json.load(fh)

	schedule_url = "https://raw.githubusercontent.com/zhecht/playerprops/main/static/mlb/schedule.json"
	response = requests.get(schedule_url)
	schedule = response.json()

	i = 0
	while True:
		html = await page.get_content()
		with open(f"feed.html", "w") as fh:
			fh.write(html)

		games = []
		for gameData in schedule[date]:
			if gameData["start"] and gameData["start"] != "LIVE":
				dt = datetime.strptime(gameData["start"], "%I:%M %p")
				dt = int(dt.strftime("%H%M"))
				#print(dt, int(datetime.now().strftime("%H%M")))
				if dt <= int(datetime.now().strftime("%H%M")):
					games.append(gameData)
		data = {}
		parseFeed(data, times, len(games), len(schedule[date]), loop)
		i += 1

		if not loop:
			break
		
		time.sleep(1)
		if i >= 5:
			commitChanges()
			i = 0

	browser.stop()

def parseFeed(data, times, liveGames, totGames, loop):
	soup = BS(open("feed.html", 'rb').read(), "lxml")
	allTable = soup.find("div", id="allMetrics")
	hdrs = [th.text.lower() for th in allTable.find_all("th")]
	data["all"] = {k: v.text.strip() for k,v in zip(hdrs,allTable.find_all("td")) if k}
	data["all"]["liveGames"] = liveGames
	data["all"]["totGames"] = totGames
	data["all"]["updated"] = str(datetime.now())
	for div in soup.find_all("div", class_="game-container"):
		away = div.find("div", class_="team-left")
		home = div.find("div", class_="team-right")
		away = convertMLBTeam(away.text.strip())
		home = convertMLBTeam(home.text.strip())
		game = f"{away} @ {home}"
		if game in data:
			game += "-gm2"
		data[game] = []
		if game not in times:
			times[game] = {}
		table = div.find("div", class_="exit-velocity-table")
		if not table:
			continue
		for tr in table.find("tbody").find_all("tr"):
			tds = tr.find_all("td")
			player = parsePlayer(tds[2].text.strip())
			pitcher = parsePlayer(tds[4].text.strip())
			img = tr.find("img").get("src")
			team = convertSavantLogoId(img.split("/")[-1].replace(".svg", ""))
			hrPark = tds[-1].text.strip()

			pa = tds[5].text.strip()
			seen = pa in times[game]
			dt = times[game].get(pa, str(datetime.now()).split(".")[0])
			times[game][pa] = dt
			j = {
				"player": player,
				"pitcher": pitcher,
				"game": game,
				"hr/park": hrPark,
				"pa": pa,
				"dt": dt,
				"img": img,
				"team": team
			}
			i = 6
			for hdr in ["in", "result", "evo", "la", "dist", "speed", "mph", "xba"]:
				j[hdr] = tds[i].text.strip()
				i += 1

			data[game].append(j)

	with open("feed.json", "w") as fh:
		json.dump(data, fh, indent=4)
	with open("feed_times.json", "w") as fh:
		json.dump(times, fh, indent=4)

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument("--sport")
	parser.add_argument("--date", "-d")
	parser.add_argument("--loop", action="store_true")
	parser.add_argument("--clear", action="store_true")
	parser.add_argument("--history", action="store_true")

	args = parser.parse_args()

	date = args.date
	if not date:
		date = str(datetime.now())[:10]

	if args.history:
		with open("feed_times.json") as fh:
			times = json.load(fh)
		with open("feed_times_historical.json") as fh:
			hist = json.load(fh)
		hist[str(datetime.now())[:10]] = times
		with open("feed_times_historical.json", "w") as fh:
			json.dump(hist, fh)
		exit()

	if args.clear:
		with open("feed_times.json", "w") as fh:
			json.dump({}, fh)
		exit()

	uc.loop().run_until_complete(writeFeed(date, args.loop))
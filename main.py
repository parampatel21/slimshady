import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import sqlite3
import spotipy
import spotipy.oauth2 as oauth2
from datetime import datetime, date, timedelta
from enchant.checker import SpellChecker
import lyricsgenius
from langdetect import detect_langs
import smtplib
import mimetypes
from email.mime.multipart import MIMEMultipart
from email import encoders
from email.message import Message
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from openpyxl.workbook import Workbook
import os

print('start time - ' + str(datetime.now()))
# start time

conn = sqlite3.connect('slimshady.db')
c = conn.cursor()
# connect to database

genius = lyricsgenius.Genius("enter-here")
genius.verbose = False
genius.remove_section_headers = True
genius.excluded_terms = ["(Remix)", "(Live)"]
# genius api and language client setup

countries = ["ar", "us", "at", "au", "be", "bg", "bo", "id",
             "br", "cl", "ch", "co", "cr", "cz", "de", "dk",
             "do", "ec", "ee", "es", "fi", "fr", "gb",
             "gr", "gt", "hk", "hn", "hu", "ie", "is",
             "it", "lt", "lu", "lv", "mx", "my", "ni",
             "nl", "no", "nz", "pa", "pe", "ph", "pl",
             "pt", "py", "se", "sg", "sk", "sv", "tr",
             "tw", "uy"]

bad_genres = ['turkish trap pop', 'norwegian pop', 'czech pop', 'czsk hip hop', 'dominican pop',
              'trap colombiano', 'french pop', 'trap latino', 'jump up', 'eurovision', 'trap venezolano',
              'spanish pop', 'danish hip hop', 'french hip hop', 'german hip hop', 'dutch rap pop',
              'dutch pop', 'panamanian pop', 'trap italiana', 'italian hip hop', 'danish pop', 'greek pop',
              'hungarian pop', 'greek trap', 'cantopop', 'pinoy hip hop', 'hip hop tuga', 'cumbia', 'europop',
              'eurodance', 'meme rap', 'mando', 'tagalog rap', 'bulgarian pop', 'german pop', 'estonian pop',
              'finnish dance pop', 'icelandic', 'dutch hip hop', 'korean pop', 'k-pop', 'french', 'perreo', 'latin',
              'malaysian pop']


def list_to_string(s):
    str1 = ""
    for ele in s:
        str1 += ele
    return str1
    # list to string converter


def is_in_english(songis):
    d = SpellChecker("en_US")
    d.set_text(songis)
    songis = re.sub(' +', ' ', songis.replace("-", "")).split(" ")
    if 'remix' in songis:
        songis.remove("Remix")
    if 'live' in songis:
        songis.remove('live')
    for i in songis:
        if len(i) <= 3:
            songis.remove(i)
    errors = [err.word for err in d]
    return False if len(errors) / len(songis) > 0.33 else True


def check_special(string):
    return False if re.findall(r'[\u4e00-\u9fff]+', string) else True
    # check special characters


def get_data(chart_type, country):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0",
               "Accept-Encoding": "gzip, deflate",
               "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "DNT": "1",
               "Connection": "close", "Upgrade-Insecure-Requests": "1"}
    r = requests.get('https://spotifycharts.com/' + chart_type + '/' + country + '/daily/latest', headers=headers)
    content = r.content
    soup = BeautifulSoup(content, "html.parser")
    song_data = soup.findAll("strong")  # find song data
    artist_data = soup.findAll("span", text=re.compile("by "))  # find artist data
    ranking_data = soup.findAll("td", {"class": "chart-table-position"})  # find ranking data
    stream_data = soup.findAll("td", {"class": "chart-table-streams"})  # find stream data
    df = pd.DataFrame(
        columns=['Country', 'Date', 'Ranking', 'Song', 'Artist', 'Features', 'Streams', 'Followers', 'Popularity',
                 'Artist Page',
                 'Genre'])  # create df
    print("\n" + country + " - " + chart_type)
    for x in range(0, len(song_data)):
        ranking = ranking_data[x].text
        # format ranking

        artist = artist_data[x].text.replace("by ", "", 1).split(",", maxsplit=1)
        features = list_to_string(artist[1:])[1:]
        artist = artist[0]
        # format artists

        try:
            res = spotify.search(artist, type="artist", limit=1)
            followers = int(res['artists']['items'][0]['followers']["total"])
            if followers > 100000:
                continue
            popularity = int(res['artists']['items'][0]['popularity'])
            artistlink = str(res['artists']['items'][0]['external_urls']["spotify"])
            genre = str(res['artists']['items'][0]['genres'])

        except:
            print("retrieval failure for rank " + ranking)
            continue
        # spotify api data

        if any(x in genre for x in bad_genres):
            continue
        # list with genres we no likey

        song = song_data[x].text.split(" (", maxsplit=1)
        morefeatures = ""
        if len(song) > 1:
            if "feat." in song[1]:
                morefeatures = song[1].split(")", maxsplit=1)[0].replace("feat. ", "")
            if "with" in song[1]:
                morefeatures = song[1].split(")", maxsplit=1)[0].replace("with ", "")
        song = song[0]
        # format songs

        try:
            songl = genius.search_song(song, artist)
            if 'en' in str(detect_langs(songl.lyrics)[0]):
                pass
            else:
                continue
        except:
            if is_in_english(song + " " + artist):
                pass
            else:
                continue

        if not check_special(song):
            continue
        # check if english more parameters

        if len(morefeatures) > 2 and len(features) > 2:
            features = morefeatures + ", " + features
        else:
            features = morefeatures
        # format artists pt. 2

        if chart_type == "regional":
            streams = int(stream_data[x].text.replace(",", ""))
            df = df.append(
                {'Country': country, 'Date': date.today() - timedelta(days=1), 'Ranking': ranking, 'Song': song,
                 'Artist': artist,
                 'Features': features, 'Streams': streams, 'Followers': followers, 'Popularity': popularity,
                 'Artist Page': artistlink, 'Genre': genre},
                ignore_index=True)
        else:
            df = df.append(
                {'Country': country, 'Date': date.today() - timedelta(days=1), 'Ranking': ranking, 'Song': song,
                 'Artist': artist,
                 'Features': features, 'Followers': followers, 'Popularity': popularity, 'Artist Page': artistlink,
                 'Genre': genre},
                ignore_index=True)
        # insert to df

    df.to_sql(chart_type, conn, if_exists='append',
              index=False)  # df insert to sqlite db
    print("db successful")  # to print dataframe, use df.to_string() for full dataframe


# EXECUTION
for i in range(0, len(countries)):
    if i == 0 or i == 5 or i == 10 or i == 15 or i == 20 or i == 25 or i == 30 or i == 35 or i == 40 or i == 45:
        credentials = oauth2.SpotifyClientCredentials(
            client_id="686c49202b6e4d8b8a159b5927f63f8a",
            client_secret="enter-here")
        token = credentials.get_access_token(as_dict=False)
        spotify = spotipy.Spotify(auth=token)
        # spotify api setup
    get_data("regional", countries[i])
    get_data("viral", countries[i])
    # viral ("viral") or top 200 ("regional")

# EMAIL SENDING BELOW:

dat = sqlite3.connect('slimshady.db')
regionaldf = pd.read_sql_query("SELECT * FROM regional", dat)
regionaldf.to_excel("top 200 - " + str(date.today() - timedelta(days=1)) + ".xlsx", encoding='utf-8', index=False)
dat2 = sqlite3.connect('slimshady.db')
viraldf = pd.read_sql_query("SELECT * FROM viral", dat2)
viraldf.to_excel("viral - " + str(date.today() - timedelta(days=1)) + ".xlsx", encoding='utf-8', index=False)
# DB TO CSV


def attachment_iterator(fileToSend):
    ctype, encoding = mimetypes.guess_type(fileToSend)
    if ctype is None or encoding is not None:
        ctype = "application/octet-stream"

    maintype, subtype = ctype.split("/", 1)

    if maintype == "text":
        fp = open(fileToSend)
        # Note: we should handle calculating the charset
        attachment = MIMEText(fp.read(), _subtype=subtype)
        fp.close()
    elif maintype == "image":
        fp = open(fileToSend, "rb")
        attachment = MIMEImage(fp.read(), _subtype=subtype)
        fp.close()
    elif maintype == "audio":
        fp = open(fileToSend, "rb")
        attachment = MIMEAudio(fp.read(), _subtype=subtype)
        fp.close()
    else:
        fp = open(fileToSend, "rb")
        attachment = MIMEBase(maintype, subtype)
        attachment.set_payload(fp.read())
        fp.close()
        encoders.encode_base64(attachment)
    attachment.add_header("Content-Disposition", "attachment", filename=fileToSend)
    msg.attach(attachment)


emailfrom = "slimshadydatabase@gmail.com"
emailto = 'parampatel21@mittymonarch.com'
username = "slimshadydatabase"
# <editor-fold desc="Password">
password = 'enter-here'
# </editor-fold>

msg = MIMEMultipart()
msg["From"] = emailfrom
msg["To"] = emailto
msg["Subject"] = "Spotify Charts Email - " + str(date.today() - timedelta(days=1))
msg.preamble = "XLSX File"

attachment_iterator("top 200 - " + str(date.today() - timedelta(days=1)) + ".xlsx")
attachment_iterator("viral - " + str(date.today() - timedelta(days=1)) + ".xlsx")

server = smtplib.SMTP("smtp.gmail.com:587")
server.starttls()
server.login(username, password)
server.sendmail(emailfrom, emailto, msg.as_string())
server.quit()

try:
    os.remove("top 200 - " + str(date.today() - timedelta(days=3)) + ".xlsx")
    os.remove("viral - " + str(date.today() - timedelta(days=3)) + ".xlsx")
except:
    print("nothing deleted")

print('end time - ' + str(datetime.now()))

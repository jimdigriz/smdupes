from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
import requests
import sys
import sqlite3
import webbrowser

from authlib.integrations.requests_client import OAuth1Session, OAuth1Auth
from configparser import ConfigParser

CONF = 'conf.ini'
DB = 'db.sqlite3'

# https://api.smugmug.com/api/v2/doc/tutorial/authorization.html
ORIGIN = 'https://api.smugmug.com'
AUTH_BASE = f'{ORIGIN}/services/oauth/1.0a'
REQUEST_TOKEN_URL = f'{AUTH_BASE}/getRequestToken'
USER_AUTHORIZATION_URL = f'{AUTH_BASE}/authorize'
ACCESS_TOKEN_URL = f'{AUTH_BASE}/getAccessToken'

config = ConfigParser()

try:
    config.read(CONF)
except FileNotFoundError:
    print(f"'{CONF}' not found", file=sys.stderr)
    sys.exit(1)

kwargs = {
    'client_id': config['client']['client_id'],
    'client_secret': config['client']['client_secret'],
    'redirect_uri': 'oob'
}

if 'token' not in config:
    client = OAuth1Session(**kwargs)

    request_token = client.fetch_request_token(REQUEST_TOKEN_URL)
    
    authorization_url = client.create_authorization_url(USER_AUTHORIZATION_URL)
    
    webbrowser.open(authorization_url)

    code = input('Enter in code: ')
    
    token = client.fetch_access_token(ACCESS_TOKEN_URL, code)

    config['token'] = {
        'token': token['oauth_token'],
        'token_secret': token['oauth_token_secret']
    }
    with os.open(CONF, os.O_WRONLY, 0o600) as configfile:
        config.write(configfile)

kwargs['token'] = config['token']['token']
kwargs['token_secret'] = config['token']['token_secret']

session = requests.Session()
session.keep_alive = 5

auth = OAuth1Auth(**kwargs)

def fetch(uri, *args, headers=None, **kwargs):
    headers = headers or {}
    headers['accept'] = 'application/json'
    headers['accept-encoding'] = 'gzip'
    headers['user-agent'] = 'smdupes (https://github.com/jimdigriz/smdupes)'
    return session.get(ORIGIN + uri, *args, auth=auth, headers=headers, **kwargs)

res = fetch('/api/v2!authuser')

try:
    os.unlink(DB)
except FileNotFoundError:
    pass

with sqlite3.connect(DB) as con:
     con.execute('CREATE TABLE album(uri PRIMARY KEY, json, weburi UNIQUE, name)')
     con.execute('CREATE TABLE image(uri PRIMARY KEY, album REFERENCES album(uri), json, filename, created DATETIME, md5)')
     con.execute('CREATE INDEX image_created ON image(created)')
     con.execute('CREATE INDEX image_md5 ON image(md5)')

def process_album(album):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute('INSERT INTO album VALUES (?, ?, ?, ?)', (
        album['Uri'],
        json.dumps(album),
        album['WebUri'],
        album['Name']
    ))
    con.commit()

    next_page = album['Uris']['AlbumImages']['Uri']
    while next_page:
        print(f'processing album images {next_page}')
        res = fetch(next_page)
        resJ = res.json()
        cur.executemany('INSERT INTO image VALUES (?, ?, ?, ?, ?, ?)', (
            (
                image['Uri'],
                album['Uri'],
                json.dumps(image),
                image['FileName'],
                datetime.fromisoformat(min(image.get('DateTimeOriginal', datetime.max.isoformat()), image['DateTimeUploaded'])),
                image['ArchivedMD5']
            ) for image in resJ['Response']['AlbumImage'] ))
        con.commit()
        next_page = resJ['Response']['Pages'].get('NextPage')

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = []
    next_page = res.json()['Response']['User']['Uris']['UserAlbums']['Uri']
    while next_page:
        print(f'processing albums {next_page}')
        res = fetch(next_page)
        resJ = res.json()
        futures.extend(executor.map(process_album, resJ['Response']['Album']))
        next_page = resJ['Response']['Pages'].get('NextPage')
    for future in futures:
        if future:
            future.result()

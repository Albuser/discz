import settings as S
import sql_db as DB
import base64 as b64
import requests
from functools import lru_cache

class RateLimitError(Exception):
    def __init__(self, retry_after, message):
        self.retry_after = retry_after
        self.message = message
        super().__init__(message)

def get_authorization_header():
    encodedClient = str(b64.b64encode(bytes(f"{S.CLIENT_ID}:{S.CLIENT_SECRET}", "ISO-8859-1")).decode("ascii"))
    headers = {
        'Authorization': 'Basic '+encodedClient,
    }

    payload = {
        'grant_type': 'client_credentials'
    }

    try:
        r = requests.post('https://accounts.spotify.com/api/token', headers=headers, data=payload)
        token = r.json()['access_token']
        token_header = {
            'Authorization': 'Bearer '+token,
        }
        return token_header
    except Exception as e:
        log_error('Could not get access token. Please check your credentials.', e)
    return


def get_artist(artist_id, sp_header):
    try:
        r = make_get_request(f'https://api.spotify.com/v1/artists/{artist_id}', sp_header)
        return r.json()
    except RateLimitError as e:
        raise e
    except Exception as e:
        log_error('Could not get related artists.', e)


def get_related_artists(artist_id, sp_header):
    try:
        r = make_get_request(f'https://api.spotify.com/v1/artists/{artist_id}/related-artists', sp_header)
        return r.json()['artists']
    except RateLimitError as e:
        raise e
    except Exception as e:
        log_error('Could not get related artists.', e)


def make_get_request(url, header):
    r = requests.get(url, headers=header)
    if r.status_code == 200:
        return r
    elif r.status_code == 429:
        # If we got cut off by rate-limiting, sleep however long they tell us to then try again
        duration = r.headers['retry-after']
        raise RateLimitError(duration, f"Request failed with status {r.status_code}")
    else:
        raise Exception(f"Request failed with status {r.status_code}")


def log_error(msg, e=None):
    with open('err_log.txt', 'a') as f:
        f.write(msg+'\n')
        if e != None:
            f.write("Exception {0} occurred. Arguments:\n{1!r}\n".format(type(e).__name__, e.args))


def seed_mq(artist_id, sp_header):
    response = get_artist(artist_id, sp_header)
    if response != None:
        if not DB.is_in_db(artist_id):
            DB.write_artist((response['id'], response['name'], str(response['genres']), response['popularity']))
        return get_related_artists(artist_id, sp_header)


@lru_cache(maxsize = 2000)
def is_in_db(artist_id):
    return DB.is_in_db(artist_id)


def write_artist(artist):
    DB.write_artist((artist['id'], artist['name'], str(artist['genres']), artist['popularity']))
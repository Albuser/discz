import sqlite3 as sl
import time
import settings as S

def start_db():
    try:
        db_con = sl.connect('artists.db')
    except Exception as e:
        log_error('Failed to connect to sqlite db.', e)
    create_artist_table(db_con)

def create_artist_table(db_con):
    query = """ CREATE TABLE IF NOT EXISTS artists (
                    id text PRIMARY KEY,
                    name text,
                    genres text,
                    popularity integer
                ); """
    try:
        cur = db_con.cursor()
        cur.execute(query)
        db_con.commit()
    except Exception as e:
        log_error('Failed to create artist table.', e)

def write_artist(artist):
    # We shouldn't insert the same artist twice, but if we do we should
    # fail quietly, hence the IGNORE
    query = f""" INSERT or IGNORE INTO artists
                            VALUES(?,?,?,?);"""
    tries = 0
    while tries < S.MAX_DB_RETRIES:
        try:
            db_con = sl.connect('artists.db')
            cur = db_con.cursor()
            cur.execute(query, artist)
            db_con.commit()
            break
        except sl.OperationalError as e:
            # Because we have parallel tasks accessing the same db, the db
            # may be locked, raising an OperationalError. We wait 1s and try again.
            # If it fails 5 times in a row, skip it.
            time.sleep(1)
            tries += 1
            if (tries == S.MAX_DB_RETRIES):
                log_error('Max DB write retries exceeded. Skipping artist.', e)
            continue

def log_error(msg, e=None):
    with open('err_log.txt', 'a') as f:
        f.write(msg+'\n')
        f.write("Exception {0} occurred. Arguments:\n{1!r}\n".format(type(e).__name__, e.args))

def is_in_db(id):
    query = f""" SELECT id FROM artists
                    WHERE id == "{id}" """
    db_con = sl.connect('artists.db')
    db_con.row_factory = sl.Row
    res = db_con.execute(query)
    row = res.fetchone()
    if row == None:
        return False
    if len(row) > 0:
        return True
    return False
import multiprocessing
import pickle
import uuid
import time
import redis

import settings as S
from utils import (get_related_artists, get_authorization_header, is_in_db, seed_mq,
                   write_artist, RateLimitError, log_error)

# Much of this code is borrowed from https://testdriven.io/blog/developing-an-asynchronous-task-queue-in-python/

sp_header = get_authorization_header()

class SimpleQueue(object):
    def __init__(self, conn, name):
        self.conn = conn
        self.name = name

    def enqueue(self, func, *args):
        task = SimpleTask(func, *args)
        serialized_task = pickle.dumps(task, protocol=pickle.HIGHEST_PROTOCOL)
        self.conn.lpush(self.name, serialized_task)
        return task.id

    def dequeue(self):
        _, serialized_task = self.conn.brpop(self.name)
        task = pickle.loads(serialized_task)
        related_artists = task.process_task()
        if related_artists != None:
            for artist in related_artists:
                if not is_in_db(artist['id']):
                    write_artist(artist)
                    self.enqueue(get_related_artists, artist['id'], sp_header)
                
        return task

    def get_length(self):
        return self.conn.llen(self.name)

class SimpleTask(object):
    def __init__(self, func, *args):
        self.id = str(uuid.uuid4())
        self.func = func
        self.args = args

    def process_task(self):
        try:
            return self.func(*self.args)
        except RateLimitError as e:
            log_error(f'{self.id}: Rate limit exceeded. Sleeping task for {e.retry_after} seconds.')
            time.sleep(int(e.retry_after))
            self.process_task()

def worker():
    mq_con = redis.Redis()
    queue = SimpleQueue(mq_con, "seeding_mq")
    while True:
        if queue.get_length() > 0:
            queue.dequeue()
        else:
            with open('err_log.txt', 'a') as f:
                f.write('No tasks in queue :(\n')

def start_redis():
    mq_con = redis.Redis()
    queue = SimpleQueue(mq_con, "seeding_mq")
    for artist in S.SEED_ARTISTS:
        queue.enqueue(seed_mq, artist, sp_header)
    processes = []
    print(f'Running with {S.PROCESSES} processes.')
    for i in range(S.PROCESSES):
        p = multiprocessing.Process(target=worker)
        processes.append(p)
        p.start()
    for i in range(len(processes)):
        p = processes[i]
        p.join()

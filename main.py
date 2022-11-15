import sql_db as DB
import redis_mq as MQ

if __name__ == '__main__':
    DB.start_db()
    MQ.start_redis()

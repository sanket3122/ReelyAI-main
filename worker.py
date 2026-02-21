from queue_config import q

if __name__ == "__main__":
    q.connection.ping()
    from rq import Worker
    worker = Worker([q], connection=q.connection)
    worker.work()

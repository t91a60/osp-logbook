workers = 2
worker_class = "sync"
timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
preload_app = True
accesslog = "-"
errorlog = "-"
loglevel = "info"


def post_fork(server, worker):
    """Reset the DB connection pool after Gunicorn forks a worker.

    With preload_app=True the pool is created before forking.
    Both workers would share the same TCP sockets to PostgreSQL,
    causing random SSL errors under load. Resetting forces each
    worker to create its own fresh connections.
    """
    from backend.db import reset_pool
    reset_pool()

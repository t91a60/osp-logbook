import os


workers = int(os.environ.get("GUNICORN_WORKERS", 2))
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gthread")
threads = max(1, int(os.environ.get("GUNICORN_THREADS", 2))) if worker_class == "gthread" else 1
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 30))
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

from __future__ import annotations
import threading
import logging
from pymongo import MongoClient
from pymongo.database import Database
import config

_lock = threading.Lock()
_client: MongoClient | None = None
_db: Database | None = None

log = logging.getLogger(__name__)


def get_db() -> Database:
    """Return the singleton MongoDB database, creating the client lazily on first call.

    Creation is deferred post-fork (never at module load) so gunicorn workers each
    get their own independent connection pool.  Pool params per D-003.
    """
    global _client, _db
    if _db is not None:
        return _db
    with _lock:
        if _db is not None:
            return _db
        if not config.UNIFIELD_MONGO_URI:
            raise RuntimeError("UNIFIELD_MONGO_URI is not set")
        _client = MongoClient(
            config.UNIFIELD_MONGO_URI,
            maxPoolSize=20,
            minPoolSize=3,
            connectTimeoutMS=10_000,
            socketTimeoutMS=15_000,
            maxIdleTimeMS=60_000,
        )
        _db = _client[config.UNIFIELD_MONGO_DB]
        log.info('{"event": "mongo_client_init", "db": "%s"}', config.UNIFIELD_MONGO_DB)
    return _db

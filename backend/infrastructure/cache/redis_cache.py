import datetime
import json
import logging
import os
import time
from collections import OrderedDict
from decimal import Decimal
from typing import Any, Optional

import redis

logger = logging.getLogger(__name__)


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class RedisCache:
    """Warstwa buforowania używająca Redis z fallbackiem na in-memory.
    
    Zapewnia tag-based invalidation i bezpieczną serializację typów bazodanowych.
    """

    def __init__(self, url: Optional[str] = None):
        self.url = url or os.environ.get('REDIS_URL')
        self.redis: Optional[redis.Redis] = None
        self._in_memory: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._MAX_SIZE = 1024

        if self.url:
            try:
                self.redis = redis.from_url(self.url, decode_responses=True)
                self.redis.ping()
                logger.info("Połączono z cache Redis.")
            except redis.ConnectionError:
                logger.warning("Brak połączenia z Redis, używam in-memory cache.")
                self.redis = None

    def get(self, key: str) -> Optional[Any]:
        if self.redis:
            try:
                val = self.redis.get(key)
                return json.loads(val) if val else None
            except redis.ConnectionError:
                pass

        # In-memory fallback
        now = time.monotonic()
        entry = self._in_memory.get(key)
        if entry and entry['expires_at'] > now:
            self._in_memory.move_to_end(key)
            return entry['value']
        
        # Cleanup expired
        if entry:
            self._in_memory.pop(key, None)
        return None

    def set(self, key: str, value: Any, ttl_seconds: int, tags: Optional[list[str]] = None) -> None:
        tags = tags or []
        if self.redis:
            try:
                serialized = json.dumps(value, cls=CustomJSONEncoder)
                pipe = self.redis.pipeline()
                pipe.setex(key, ttl_seconds, serialized)
                for tag in tags:
                    tag_key = f"tag:{tag}"
                    pipe.sadd(tag_key, key)
                    pipe.expire(tag_key, ttl_seconds)
                pipe.execute()
                return
            except redis.ConnectionError:
                pass

        # In-memory fallback
        # Wymuszamy serializację/deserializację, żeby unikać problemów ze zmianami obiektów mutowalnych
        # i naśladować zachowanie Redis (gdzie daty stają się stringami).
        try:
            val_to_store = json.loads(json.dumps(value, cls=CustomJSONEncoder))
        except TypeError:
            val_to_store = value

        self._in_memory[key] = {
            'value': val_to_store,
            'expires_at': time.monotonic() + max(1, ttl_seconds),
            'tags': tags,
        }
        self._in_memory.move_to_end(key)
        while len(self._in_memory) > self._MAX_SIZE:
            self._in_memory.popitem(last=False)

    def invalidate_tags(self, tags: list[str]) -> None:
        """Inwaliduje wszystkie klucze powiązane z podanymi tagami."""
        if not tags:
            return

        if self.redis:
            try:
                pipe = self.redis.pipeline()
                keys_to_delete = set()
                
                for tag in tags:
                    tag_key = f"tag:{tag}"
                    keys = self.redis.smembers(tag_key)
                    if keys:
                        keys_to_delete.update(keys)
                    pipe.delete(tag_key)
                
                if keys_to_delete:
                    pipe.delete(*keys_to_delete)
                pipe.execute()
                return
            except redis.ConnectionError:
                pass

        # In-memory fallback
        keys_to_delete = []
        for key, entry in self._in_memory.items():
            entry_tags = entry.get('tags', [])
            if any(t in entry_tags for t in tags):
                keys_to_delete.append(key)
                
        for k in keys_to_delete:
            self._in_memory.pop(k, None)

    def invalidate_prefix(self, prefix: str) -> None:
        """Inwaliduje klucze po prefiksie (legacy)."""
        if self.redis:
            try:
                cursor = '0'
                while cursor != 0:
                    cursor, keys = self.redis.scan(cursor=cursor, match=f"{prefix}*", count=100)
                    if keys:
                        self.redis.delete(*keys)
                return
            except redis.ConnectionError:
                pass

        # In-memory fallback
        keys_to_delete = [k for k in self._in_memory.keys() if k.startswith(prefix)]
        for k in keys_to_delete:
            self._in_memory.pop(k, None)

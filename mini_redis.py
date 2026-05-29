"""Mini Redis engine using hand-built hash map, linked list, and heap."""

import shlex
import time

from hash_map import HashMap
from linked_list import DoublyLinkedList
from min_heap import ExpireRecord, MinHeap
from pubsub import PubSub


class RedisValue:
    """Stored string value plus its LRU list node."""

    def __init__(self, value, lru_node):
        self.value = value
        self.lru_node = lru_node


class Expiration:
    """Current TTL metadata for a key."""

    def __init__(self, expire_at, version):
        self.expire_at = expire_at
        self.version = version


class MiniRedis:
    """Command executor for the CLI Mini Redis."""

    def __init__(self, clock=None):
        self._store = HashMap()
        self._expirations = HashMap()
        self._ttl_heap = MinHeap()
        self._lru = DoublyLinkedList()
        self._used_memory = 0
        self._maxmemory = 0
        self._evicted_keys = 0
        self._ttl_version = 0
        self._pubsub = PubSub()
        self._clock = clock if clock is not None else time.time

    def execute_line(self, line):
        try:
            parts = shlex.split(line)
        except ValueError as error:
            return "(error) ERR " + str(error)
        if len(parts) == 0:
            return ""
        return self.execute(parts)

    def execute(self, parts):
        command = parts[0].upper()
        self._purge_expired()
        if command == "SET":
            return self._cmd_set(parts)
        if command == "GET":
            return self._cmd_get(parts)
        if command == "DEL":
            return self._cmd_del(parts)
        if command == "EXISTS":
            return self._cmd_exists(parts)
        if command == "DBSIZE":
            return self._cmd_dbsize(parts)
        if command == "KEYS":
            return self._cmd_keys(parts)
        if command == "CONFIG":
            return self._cmd_config(parts)
        if command == "INFO":
            return self._cmd_info(parts)
        if command == "EXPIRE":
            return self._cmd_expire(parts)
        if command == "TTL":
            return self._cmd_ttl(parts)
        if command == "PUBLISH":
            return self._cmd_publish(parts)
        if command == "SUBSCRIBE":
            return self._cmd_subscribe(parts)
        if command == "MESSAGES":
            return self._cmd_messages(parts)
        if command == "CLEARMSG":
            return self._cmd_clear_messages(parts)
        return "(error) ERR unknown command '" + command + "'"

    def _cmd_set(self, parts):
        if len(parts) != 3:
            return self._wrong_args("SET")
        key = parts[1]
        value = parts[2]
        new_size = self._entry_size(key, value)
        if self._maxmemory > 0 and new_size > self._maxmemory:
            return "(error) OOM command not allowed when used_memory > 'maxmemory'"
        existing = self._store.get(key)
        if existing is None:
            node = self._lru.insert_front(key)
            self._store.put(key, RedisValue(value, node))
            self._used_memory += new_size
        else:
            self._used_memory -= self._entry_size(key, existing.value)
            existing.value = value
            existing.lru_node = self._lru.move_to_front(existing.lru_node)
            self._used_memory += new_size
        self._expirations.remove(key)
        self._evict_if_needed()
        if self._store.get(key) is None:
            return "(error) OOM command not allowed when used_memory > 'maxmemory'"
        return "OK"

    def _cmd_get(self, parts):
        if len(parts) != 2:
            return self._wrong_args("GET")
        key = parts[1]
        if self._delete_if_expired(key):
            return "(nil)"
        entry = self._store.get(key)
        if entry is None:
            return "(nil)"
        entry.lru_node = self._lru.move_to_front(entry.lru_node)
        return '"' + entry.value + '"'

    def _cmd_del(self, parts):
        if len(parts) != 2:
            return self._wrong_args("DEL")
        deleted = self._delete_key(parts[1], count_eviction=False)
        if deleted:
            return "(integer) 1"
        return "(integer) 0"

    def _cmd_exists(self, parts):
        if len(parts) != 2:
            return self._wrong_args("EXISTS")
        if self._delete_if_expired(parts[1]):
            return "(integer) 0"
        if self._store.contains(parts[1]):
            return "(integer) 1"
        return "(integer) 0"

    def _cmd_dbsize(self, parts):
        if len(parts) != 1:
            return self._wrong_args("DBSIZE")
        return "(integer) " + str(self._store.size())

    def _cmd_keys(self, parts):
        if len(parts) != 1:
            return self._wrong_args("KEYS")
        keys = self._store.keys()
        if len(keys) == 0:
            return "(empty array)"
        lines = []
        index = 0
        while index < len(keys):
            lines.append(str(index + 1) + '. "' + str(keys.get(index)) + '"')
            index += 1
        return "\n".join(lines)

    def _cmd_config(self, parts):
        if len(parts) != 4 or parts[1].upper() != "SET" or parts[2].lower() != "maxmemory":
            return self._wrong_args("CONFIG")
        value = self._parse_non_negative_int(parts[3])
        if value is None:
            return "(error) ERR value is not an integer or out of range"
        self._maxmemory = value
        self._evict_if_needed()
        return "OK"

    def _cmd_info(self, parts):
        if len(parts) != 2 or parts[1].lower() != "memory":
            return self._wrong_args("INFO")
        return (
            "used_memory:" + str(self._used_memory) + "\n"
            "maxmemory:" + str(self._maxmemory) + "\n"
            "evicted_keys:" + str(self._evicted_keys)
        )

    def _cmd_expire(self, parts):
        if len(parts) != 3:
            return self._wrong_args("EXPIRE")
        key = parts[1]
        seconds = self._parse_int(parts[2])
        if seconds is None:
            return "(error) ERR value is not an integer or out of range"
        if self._delete_if_expired(key):
            return "(integer) 0"
        if not self._store.contains(key):
            return "(integer) 0"
        if seconds <= 0:
            self._delete_key(key, count_eviction=False)
            return "(integer) 1"
        self._ttl_version += 1
        expire_at = self._clock() + seconds
        self._expirations.put(key, Expiration(expire_at, self._ttl_version))
        self._ttl_heap.push(ExpireRecord(expire_at, key, self._ttl_version))
        return "(integer) 1"

    def _cmd_ttl(self, parts):
        if len(parts) != 2:
            return self._wrong_args("TTL")
        key = parts[1]
        if self._delete_if_expired(key):
            return "(integer) -2"
        if not self._store.contains(key):
            return "(integer) -2"
        expiration = self._expirations.get(key)
        if expiration is None:
            return "(integer) -1"
        remaining = int(expiration.expire_at - self._clock())
        if remaining < 0:
            self._delete_key(key, count_eviction=False)
            return "(integer) -2"
        return "(integer) " + str(remaining)

    def _cmd_publish(self, parts):
        if len(parts) != 3:
            return self._wrong_args("PUBLISH")
        count = self._pubsub.publish(parts[1], parts[2])
        return "(integer) " + str(count)

    def _cmd_subscribe(self, parts):
        if len(parts) != 3:
            return self._wrong_args("SUBSCRIBE")
        added = self._pubsub.subscribe(parts[1], parts[2])
        if added:
            return "(integer) 1"
        return "(integer) 0"

    def _cmd_messages(self, parts):
        if len(parts) != 2:
            return self._wrong_args("MESSAGES")
        messages = self._pubsub.messages(parts[1])
        if messages is None:
            return "(empty array)"
        lines = []
        index = 1
        node = messages.head
        while node is not None:
            lines.append(str(index) + '. "' + node.data.channel + ': ' + node.data.text + '"')
            index += 1
            node = node.next
        return "\n".join(lines)

    def _cmd_clear_messages(self, parts):
        if len(parts) != 2:
            return self._wrong_args("CLEARMSG")
        return "(integer) " + str(self._pubsub.clear_messages(parts[1]))

    def _purge_expired(self):
        now = self._clock()
        while self._ttl_heap.size() > 0:
            record = self._ttl_heap.peek()
            if record.expire_at > now:
                break
            self._ttl_heap.pop()
            expiration = self._expirations.get(record.key)
            if expiration is None:
                continue
            if expiration.version == record.version and expiration.expire_at <= now:
                self._delete_key(record.key, count_eviction=False)

    def _delete_if_expired(self, key):
        expiration = self._expirations.get(key)
        if expiration is None:
            return False
        if expiration.expire_at <= self._clock():
            return self._delete_key(key, count_eviction=False)
        return False

    def _delete_key(self, key, count_eviction):
        entry = self._store.remove(key)
        if entry is None:
            self._expirations.remove(key)
            return False
        self._used_memory -= self._entry_size(key, entry.value)
        self._lru.remove_node(entry.lru_node)
        self._expirations.remove(key)
        if count_eviction:
            self._evicted_keys += 1
        return True

    def _evict_if_needed(self):
        if self._maxmemory <= 0:
            return
        while self._used_memory > self._maxmemory and self._lru.tail is not None:
            key = self._lru.tail.data
            self._delete_key(key, count_eviction=True)

    def _entry_size(self, key, value):
        return len(str(key).encode("utf-8")) + len(str(value).encode("utf-8"))

    def _parse_int(self, text):
        try:
            return int(text)
        except ValueError:
            return None

    def _parse_non_negative_int(self, text):
        value = self._parse_int(text)
        if value is None or value < 0:
            return None
        return value

    def _wrong_args(self, command):
        return "(error) ERR wrong number of arguments for '" + command + "' command"

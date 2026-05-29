"""Separate-chaining hash map implemented without dict/set/collections."""

from dynamic_array import DynamicArray
from linked_list import DoublyLinkedList


class HashEntry:
    """A key-value pair stored in a hash bucket."""

    def __init__(self, key, value):
        self.key = key
        self.value = value


class HashMap:
    """Hash map with separate chaining and capacity doubling at 0.75 load."""

    def __init__(self, initial_capacity=8):
        self._capacity = max(2, initial_capacity)
        self._buckets = DynamicArray(self._capacity)
        index = 0
        while index < self._capacity:
            self._buckets.raw_set(index, None)
            index += 1
        self._size = 0

    def size(self):
        return self._size

    def put(self, key, value):
        bucket_index = self._index_for(key)
        bucket = self._bucket_at(bucket_index)
        node = bucket.head
        while node is not None:
            if node.data.key == key:
                node.data.value = value
                return False
            node = node.next
        bucket.insert_back(HashEntry(key, value))
        self._size += 1
        if self._size / self._capacity > 0.75:
            self._resize(self._capacity * 2)
        return True

    def get(self, key):
        node = self._find_node(key)
        if node is None:
            return None
        return node.data.value

    def remove(self, key):
        bucket_index = self._index_for(key)
        bucket = self._buckets.raw_get(bucket_index)
        if bucket is None:
            return None
        node = bucket.head
        while node is not None:
            if node.data.key == key:
                value = node.data.value
                bucket.remove_node(node)
                self._size -= 1
                return value
            node = node.next
        return None

    def contains(self, key):
        return self._find_node(key) is not None

    def keys(self):
        result = DynamicArray()
        self.each(lambda key, value: result.append(key))
        return result

    def each(self, visit):
        index = 0
        while index < self._capacity:
            bucket = self._buckets.raw_get(index)
            node = None if bucket is None else bucket.head
            while node is not None:
                visit(node.data.key, node.data.value)
                node = node.next
            index += 1

    def _find_node(self, key):
        bucket_index = self._index_for(key)
        bucket = self._buckets.raw_get(bucket_index)
        if bucket is None:
            return None
        node = bucket.head
        while node is not None:
            if node.data.key == key:
                return node
            node = node.next
        return None

    def _bucket_at(self, index):
        bucket = self._buckets.raw_get(index)
        if bucket is None:
            bucket = DoublyLinkedList()
            self._buckets.raw_set(index, bucket)
        return bucket

    def _index_for(self, key):
        return self._hash(key) % self._capacity

    def _hash(self, key):
        """Polynomial rolling hash over UTF-8 bytes."""
        text = str(key)
        result = 0
        multiplier = 31
        data = text.encode("utf-8")
        index = 0
        while index < len(data):
            result = (result * multiplier + data[index]) & 0x7FFFFFFF
            index += 1
        return result

    def _resize(self, new_capacity):
        old_buckets = self._buckets
        old_capacity = self._capacity
        self._capacity = new_capacity
        self._buckets = DynamicArray(new_capacity)
        index = 0
        while index < new_capacity:
            self._buckets.raw_set(index, None)
            index += 1
        old_size = self._size
        self._size = 0
        index = 0
        while index < old_capacity:
            bucket = old_buckets.raw_get(index)
            node = None if bucket is None else bucket.head
            while node is not None:
                self.put(node.data.key, node.data.value)
                node = node.next
            index += 1
        self._size = old_size

"""A tiny dynamic array used by the custom data structures.

Python lists are used only as the fixed-size backing store. Capacity growth,
index access, append, set, and remove are implemented here for learning
purposes instead of relying on list-as-container behavior throughout the app.
"""


class DynamicArray:
    """Resizable array with doubling capacity."""

    def __init__(self, initial_capacity=4):
        if initial_capacity < 1:
            initial_capacity = 1
        self._capacity = initial_capacity
        self._size = 0
        self._items = [None] * self._capacity

    def __len__(self):
        return self._size

    @property
    def capacity(self):
        return self._capacity

    def append(self, value):
        if self._size >= self._capacity:
            self._resize(self._capacity * 2)
        self._items[self._size] = value
        self._size += 1

    def get(self, index):
        self._check_index(index)
        return self._items[index]

    def set(self, index, value):
        self._check_index(index)
        self._items[index] = value

    def remove(self, index):
        self._check_index(index)
        value = self._items[index]
        current = index
        while current < self._size - 1:
            self._items[current] = self._items[current + 1]
            current += 1
        self._size -= 1
        self._items[self._size] = None
        return value

    def raw_get(self, index):
        """Return by capacity index. Used for bucket tables."""
        if index < 0 or index >= self._capacity:
            raise IndexError("index out of capacity range")
        return self._items[index]

    def raw_set(self, index, value):
        """Set by capacity index. Used for bucket tables."""
        if index < 0 or index >= self._capacity:
            raise IndexError("index out of capacity range")
        self._items[index] = value
        if index >= self._size:
            self._size = index + 1

    def _resize(self, new_capacity):
        new_items = [None] * new_capacity
        index = 0
        while index < self._size:
            new_items[index] = self._items[index]
            index += 1
        self._items = new_items
        self._capacity = new_capacity

    def _check_index(self, index):
        if index < 0 or index >= self._size:
            raise IndexError("index out of range")

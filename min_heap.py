"""Min heap for TTL expiration records."""

from dynamic_array import DynamicArray


class ExpireRecord:
    """Heap element ordered by expire_at and carrying lazy-deletion version."""

    def __init__(self, expire_at, key, version):
        self.expire_at = expire_at
        self.key = key
        self.version = version

    def __lt__(self, other):
        if self.expire_at == other.expire_at:
            return self.key < other.key
        return self.expire_at < other.expire_at


class MinHeap:
    """Array-backed minimum heap."""

    def __init__(self):
        self._items = DynamicArray()

    def size(self):
        return len(self._items)

    def peek(self):
        if self.size() == 0:
            return None
        return self._items.get(0)

    def push(self, value):
        self._items.append(value)
        self._heapify_up(self.size() - 1)

    def pop(self):
        if self.size() == 0:
            return None
        root = self._items.get(0)
        last = self._items.remove(self.size() - 1)
        if self.size() > 0:
            self._items.set(0, last)
            self._heapify_down(0)
        return root

    def _heapify_up(self, index):
        while index > 0:
            parent = (index - 1) // 2
            if not self._items.get(index) < self._items.get(parent):
                break
            self._swap(index, parent)
            index = parent

    def _heapify_down(self, index):
        size = self.size()
        while True:
            left = index * 2 + 1
            right = index * 2 + 2
            smallest = index
            if left < size and self._items.get(left) < self._items.get(smallest):
                smallest = left
            if right < size and self._items.get(right) < self._items.get(smallest):
                smallest = right
            if smallest == index:
                break
            self._swap(index, smallest)
            index = smallest

    def _swap(self, left, right):
        left_value = self._items.get(left)
        self._items.set(left, self._items.get(right))
        self._items.set(right, left_value)

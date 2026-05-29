"""Doubly linked list with O(1) insert, delete, and move operations."""


class Node:
    """A node containing prev, next, and data fields."""

    def __init__(self, data):
        self.prev = None
        self.next = None
        self.data = data


class DoublyLinkedList:
    """Doubly linked list used by buckets, LRU tracking, and queues."""

    def __init__(self):
        self.head = None
        self.tail = None
        self._size = 0

    def size(self):
        return self._size

    def insert_front(self, data):
        node = Node(data)
        node.next = self.head
        if self.head is not None:
            self.head.prev = node
        self.head = node
        if self.tail is None:
            self.tail = node
        self._size += 1
        return node

    def insert_back(self, data):
        node = Node(data)
        node.prev = self.tail
        if self.tail is not None:
            self.tail.next = node
        self.tail = node
        if self.head is None:
            self.head = node
        self._size += 1
        return node

    def remove_front(self):
        if self.head is None:
            return None
        return self.remove_node(self.head)

    def remove_back(self):
        if self.tail is None:
            return None
        return self.remove_node(self.tail)

    def remove_node(self, node):
        if node is None:
            return None
        if node.prev is not None:
            node.prev.next = node.next
        else:
            self.head = node.next
        if node.next is not None:
            node.next.prev = node.prev
        else:
            self.tail = node.prev
        node.prev = None
        node.next = None
        self._size -= 1
        return node.data

    def move_to_front(self, node):
        if node is None or node is self.head:
            return node
        data = self.remove_node(node)
        return self.insert_front(data)

"""CLI-friendly Pub/Sub built on the custom hash map and linked list."""

from hash_map import HashMap
from linked_list import DoublyLinkedList


class Message:
    def __init__(self, channel, text):
        self.channel = channel
        self.text = text


class PubSub:
    """Channel subscription registry and per-subscriber message queues."""

    def __init__(self):
        self._channels = HashMap()
        self._queues = HashMap()

    def subscribe(self, subscriber, channel):
        subscribers = self._channels.get(channel)
        if subscribers is None:
            subscribers = DoublyLinkedList()
            self._channels.put(channel, subscribers)
        if self._contains(subscribers, subscriber):
            return False
        subscribers.insert_back(subscriber)
        if self._queues.get(subscriber) is None:
            self._queues.put(subscriber, DoublyLinkedList())
        return True

    def publish(self, channel, message):
        subscribers = self._channels.get(channel)
        if subscribers is None:
            return 0
        count = 0
        node = subscribers.head
        while node is not None:
            queue = self._queues.get(node.data)
            if queue is None:
                queue = DoublyLinkedList()
                self._queues.put(node.data, queue)
            queue.insert_back(Message(channel, message))
            count += 1
            node = node.next
        return count

    def messages(self, subscriber):
        queue = self._queues.get(subscriber)
        if queue is None or queue.size() == 0:
            return None
        return queue

    def clear_messages(self, subscriber):
        queue = self._queues.get(subscriber)
        if queue is None:
            return 0
        count = queue.size()
        self._queues.put(subscriber, DoublyLinkedList())
        return count

    def _contains(self, linked_list, value):
        node = linked_list.head
        while node is not None:
            if node.data == value:
                return True
            node = node.next
        return False

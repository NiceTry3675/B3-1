import unittest

from bst import BinarySearchTree
from mini_redis import MiniRedis


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class MiniRedisTest(unittest.TestCase):
    def test_string_lru_and_memory(self):
        redis = MiniRedis()
        self.assertEqual(redis.execute_line("CONFIG SET maxmemory 30"), "OK")
        self.assertEqual(redis.execute_line('SET user:1 "Alice"'), "OK")
        self.assertEqual(redis.execute_line('SET user:2 "Bob"'), "OK")
        self.assertEqual(redis.execute_line('SET user:3 "Charlie"'), "OK")
        self.assertEqual(redis.execute_line("GET user:1"), "(nil)")
        info = redis.execute_line("INFO memory")
        self.assertIn("used_memory:22", info)
        self.assertIn("maxmemory:30", info)
        self.assertIn("evicted_keys:1", info)

    def test_ttl_and_set_clears_ttl(self):
        clock = FakeClock()
        redis = MiniRedis(clock=clock)
        self.assertEqual(redis.execute_line("SET a one"), "OK")
        self.assertEqual(redis.execute_line("EXPIRE a 3"), "(integer) 1")
        self.assertEqual(redis.execute_line("TTL a"), "(integer) 3")
        self.assertEqual(redis.execute_line("SET a two"), "OK")
        self.assertEqual(redis.execute_line("TTL a"), "(integer) -1")
        clock.advance(4)
        self.assertEqual(redis.execute_line("GET a"), '"two"')

    def test_expired_key_is_deleted(self):
        clock = FakeClock()
        redis = MiniRedis(clock=clock)
        redis.execute_line("SET a one")
        redis.execute_line("EXPIRE a 1")
        clock.advance(2)
        self.assertEqual(redis.execute_line("GET a"), "(nil)")
        self.assertEqual(redis.execute_line("TTL a"), "(integer) -2")

    def test_errors_and_pubsub(self):
        redis = MiniRedis()
        self.assertEqual(redis.execute_line("HELLO"), "(error) ERR unknown command 'HELLO'")
        self.assertEqual(redis.execute_line("GET"), "(error) ERR wrong number of arguments for 'GET' command")
        self.assertEqual(redis.execute_line("CONFIG SET maxmemory abc"), "(error) ERR value is not an integer or out of range")
        self.assertEqual(redis.execute_line("SUBSCRIBE alice news"), "(integer) 1")
        self.assertEqual(redis.execute_line('PUBLISH news "hi"'), "(integer) 1")
        self.assertEqual(redis.execute_line("MESSAGES alice"), '1. "news: hi"')


class BonusStructureTest(unittest.TestCase):
    def test_bst_inorder_and_delete(self):
        tree = BinarySearchTree()
        for key in (4, 2, 6, 1, 3, 5, 7):
            tree.insert(key, str(key))
        self.assertEqual(tree.search(5), "5")
        self.assertTrue(tree.delete(4))
        keys = tree.inorder_keys()
        actual = []
        index = 0
        while index < len(keys):
            actual.append(keys.get(index))
            index += 1
        self.assertEqual(actual, [1, 2, 3, 5, 6, 7])
        self.assertEqual(tree.size(), 6)


if __name__ == "__main__":
    unittest.main()

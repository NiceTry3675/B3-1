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
    def run_command(self, redis, command):
        output = redis.execute_line(command)
        print("mini-redis> " + command, flush=True)
        if output != "":
            print(output, flush=True)
        return output

    def test_string_lru_and_memory(self):
        redis = MiniRedis()
        self.assertEqual(self.run_command(redis, "CONFIG SET maxmemory 30"), "OK")
        self.assertEqual(self.run_command(redis, 'SET user:1 "Alice"'), "OK")
        self.assertEqual(self.run_command(redis, 'SET user:2 "Bob"'), "OK")
        self.assertEqual(self.run_command(redis, 'SET user:3 "Charlie"'), "OK")
        self.assertEqual(self.run_command(redis, "GET user:1"), "(nil)")
        info = self.run_command(redis, "INFO memory")
        self.assertIn("used_memory:22", info)
        self.assertIn("maxmemory:30", info)
        self.assertIn("evicted_keys:1", info)

    def test_ttl_and_set_clears_ttl(self):
        clock = FakeClock()
        redis = MiniRedis(clock=clock)
        self.assertEqual(self.run_command(redis, "SET a one"), "OK")
        self.assertEqual(self.run_command(redis, "EXPIRE a 3"), "(integer) 1")
        self.assertEqual(self.run_command(redis, "TTL a"), "(integer) 3")
        self.assertEqual(self.run_command(redis, "SET a two"), "OK")
        self.assertEqual(self.run_command(redis, "TTL a"), "(integer) -1")
        clock.advance(4)
        print("[clock] advance 4 seconds", flush=True)
        self.assertEqual(self.run_command(redis, "GET a"), '"two"')

    def test_expired_key_is_deleted(self):
        clock = FakeClock()
        redis = MiniRedis(clock=clock)
        self.run_command(redis, "SET a one")
        self.run_command(redis, "EXPIRE a 1")
        clock.advance(2)
        print("[clock] advance 2 seconds", flush=True)
        self.assertEqual(self.run_command(redis, "GET a"), "(nil)")
        self.assertEqual(self.run_command(redis, "TTL a"), "(integer) -2")

    def test_errors_and_pubsub(self):
        redis = MiniRedis()
        self.assertEqual(self.run_command(redis, "HELLO"), "(error) ERR unknown command 'HELLO'")
        self.assertEqual(self.run_command(redis, "GET"), "(error) ERR wrong number of arguments for 'GET' command")
        self.assertEqual(self.run_command(redis, "CONFIG SET maxmemory abc"), "(error) ERR value is not an integer or out of range")
        self.assertEqual(self.run_command(redis, "SUBSCRIBE alice news"), "(integer) 1")
        self.assertEqual(self.run_command(redis, 'PUBLISH news "hi"'), "(integer) 1")
        self.assertEqual(self.run_command(redis, "MESSAGES alice"), '1. "news: hi"')


class BonusStructureTest(unittest.TestCase):
    def test_bst_inorder_and_delete(self):
        tree = BinarySearchTree()
        for key in (4, 2, 6, 1, 3, 5, 7):
            print("[bst] insert " + str(key), flush=True)
            tree.insert(key, str(key))
        print("[bst] search 5", flush=True)
        self.assertEqual(tree.search(5), "5")
        print("[bst] delete 4", flush=True)
        self.assertTrue(tree.delete(4))
        keys = tree.inorder_keys()
        actual = []
        index = 0
        while index < len(keys):
            actual.append(keys.get(index))
            index += 1
        print("[bst] inorder keys after delete: " + str(actual), flush=True)
        self.assertEqual(actual, [1, 2, 3, 5, 6, 7])
        self.assertEqual(tree.size(), 6)


if __name__ == "__main__":
    unittest.main()

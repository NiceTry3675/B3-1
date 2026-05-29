"""REPL entry point for Mini Redis."""

from mini_redis import MiniRedis


def main():
    redis = MiniRedis()
    while True:
        try:
            line = input("mini-redis> ")
        except EOFError:
            print()
            break
        if line.strip().lower() in ("exit", "quit"):
            break
        output = redis.execute_line(line)
        if output != "":
            print(output)


if __name__ == "__main__":
    main()

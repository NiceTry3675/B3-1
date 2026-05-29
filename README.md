# Mini Redis

Python 3.8 이상에서 실행되는 CLI 기반 Mini Redis입니다. `dict`, `set`, `collections`로 핵심 저장소를 대체하지 않고, 직접 구현한 해시맵, 이중 연결 리스트, 최소 힙, 동적 배열을 조합해 String 명령어, LRU eviction, TTL, Pub/Sub 보너스 기능을 제공합니다.

## 실행

```bash
python3 cli.py
```

종료는 `exit` 또는 `quit`을 입력합니다.

## 주요 명령어

```text
SET key value
GET key
DEL key
EXISTS key
DBSIZE
KEYS
CONFIG SET maxmemory bytes
INFO memory
EXPIRE key seconds
TTL key
```

값은 공백 없는 문자열 또는 큰따옴표 문자열을 사용할 수 있습니다.

```text
SET user:1 "Alice"
GET user:1
```

## 보너스 명령어: Pub/Sub

단일 CLI 환경에서 확인하기 쉽도록 구독자 이름을 직접 받습니다.

```text
SUBSCRIBE learner news
PUBLISH news "hello"
MESSAGES learner
CLEARMSG learner
```

## 파일 구성

- `dynamic_array.py`: capacity 2배 확장을 포함한 동적 배열
- `linked_list.py`: 이중 연결 리스트
- `hash_map.py`: 체이닝 방식 해시맵
- `min_heap.py`: TTL 관리용 최소 힙
- `mini_redis.py`: 명령 실행, LRU, TTL, 메모리 관리
- `pubsub.py`: 채널 기반 메시징
- `binary_tree.py`: 이진 트리와 순회
- `bst.py`: 이진 탐색 트리
- `cli.py`: REPL 진입점
- `STACK_QUEUE_DEQUE.md`: 스택/큐/덱 학습 문서
- `INTERVIEW_PREP.md`: 인터뷰 대비 학습 문서

## 테스트

```bash
python3 -m unittest -v
```

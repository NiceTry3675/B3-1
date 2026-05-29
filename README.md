# Mini Redis

Python 3.8 이상에서 실행되는 CLI 기반 Mini Redis입니다. Redis의 네트워크 서버나 영속성까지 구현하는 프로젝트가 아니라, Redis가 빠르게 동작하는 핵심 이유인 자료구조 조합을 직접 구현해 보는 학습용 프로젝트입니다.

핵심 저장소를 `dict`, `set`, `collections`로 대체하지 않고, 직접 만든 해시맵, 이중 연결 리스트, 최소 힙, 동적 배열을 조합해 String 명령어, LRU eviction, TTL, Pub/Sub 보너스 기능을 제공합니다.

## 빠른 시작

```bash
python3 cli.py
```

실행하면 아래처럼 `mini-redis>` 프롬프트가 표시됩니다.

```text
mini-redis> SET user:1 "Alice"
OK
mini-redis> GET user:1
"Alice"
mini-redis> DBSIZE
(integer) 1
```

종료하려면 `exit` 또는 `quit`을 입력합니다.

```text
mini-redis> exit
```

## 테스트

```bash
python3 -m unittest -v
```

테스트는 String 명령어, LRU eviction, TTL 만료, 에러 출력, Pub/Sub, BST 보너스 구현을 확인합니다.

## 지원 명령어

### String

| 명령어 | 설명 | 예시 출력 |
| --- | --- | --- |
| `SET key value` | key에 문자열 value를 저장합니다. 성공 시 LRU 최신 위치로 이동합니다. | `OK` |
| `GET key` | key의 value를 조회합니다. 성공 시 LRU 최신 위치로 이동합니다. | `"Alice"` 또는 `(nil)` |
| `DEL key` | key를 삭제합니다. LRU와 TTL 메타데이터도 함께 정리합니다. | `(integer) 1` |
| `EXISTS key` | key 존재 여부를 확인합니다. | `(integer) 1` |
| `DBSIZE` | 현재 저장된 key 개수를 반환합니다. | `(integer) 3` |
| `KEYS` | 전체 key 목록을 출력합니다. 순서는 보장하지 않습니다. | `1. "user:1"` |

값은 공백 없는 문자열 또는 큰따옴표로 감싼 문자열을 사용할 수 있습니다. 입력 파싱은 Python `shlex.split`을 사용하므로 `"Alice Kim"`처럼 공백이 있는 값도 하나의 인자로 처리됩니다.

```text
mini-redis> SET user:1 "Alice Kim"
OK
mini-redis> GET user:1
"Alice Kim"
```

### Memory와 LRU

| 명령어 | 설명 |
| --- | --- |
| `CONFIG SET maxmemory bytes` | 최대 메모리 제한을 바이트 단위로 설정합니다. `0`은 무제한입니다. |
| `INFO memory` | `used_memory`, `maxmemory`, `evicted_keys`를 출력합니다. |

`used_memory`는 아래 공식으로 계산합니다.

```text
used_memory = sum(len(utf8(key)) + len(utf8(value)))
```

자료구조의 노드, 포인터, 버킷 배열 같은 오버헤드는 계산하지 않습니다.

```text
mini-redis> CONFIG SET maxmemory 30
OK
mini-redis> SET user:1 "Alice"
OK
mini-redis> SET user:2 "Bob"
OK
mini-redis> SET user:3 "Charlie"
OK
mini-redis> GET user:1
(nil)
mini-redis> INFO memory
used_memory:22
maxmemory:30
evicted_keys:1
```

메모리 제한을 넘으면 가장 오래 사용되지 않은 key부터 삭제합니다. 이 프로젝트에서는 LRU 리스트의 `head`가 가장 최근 사용된 key, `tail`이 가장 오래 사용되지 않은 key입니다.

### TTL

| 명령어 | 설명 | 예시 출력 |
| --- | --- | --- |
| `EXPIRE key seconds` | key에 만료 시간을 설정합니다. | `(integer) 1` |
| `TTL key` | key의 남은 만료 시간을 초 단위로 조회합니다. | `(integer) 10` |

TTL 출력 규칙은 Redis 스타일을 따릅니다.

- key가 없으면 `(integer) -2`
- key는 있지만 TTL이 없으면 `(integer) -1`
- TTL이 있으면 남은 초를 `(integer) N`으로 출력

```text
mini-redis> SET token abc
OK
mini-redis> EXPIRE token 3
(integer) 1
mini-redis> TTL token
(integer) 2
mini-redis> GET token
(nil)
```

만료된 key는 명령 실행 전에 먼저 정리되어 없는 key처럼 처리됩니다. 기존 key를 `SET`으로 덮어쓰면 기존 TTL은 삭제됩니다.

### Pub/Sub 보너스

단일 CLI 환경에서 확인하기 쉽도록 구독자 이름을 직접 받습니다.

| 명령어 | 설명 |
| --- | --- |
| `SUBSCRIBE subscriber channel` | subscriber를 channel에 구독시킵니다. |
| `PUBLISH channel message` | channel 구독자들의 메시지 큐에 message를 넣습니다. |
| `MESSAGES subscriber` | subscriber가 받은 메시지 목록을 출력합니다. |
| `CLEARMSG subscriber` | subscriber의 메시지 큐를 비웁니다. |

```text
mini-redis> SUBSCRIBE learner news
(integer) 1
mini-redis> PUBLISH news "hello"
(integer) 1
mini-redis> MESSAGES learner
1. "news: hello"
mini-redis> CLEARMSG learner
(integer) 1
```

## 핵심 동작 요약

- 모든 명령은 실행 전에 만료된 TTL key를 먼저 정리합니다.
- `GET` 성공과 `SET` 성공은 해당 key를 LRU 최신 위치로 이동합니다.
- `GET` 대상 key가 만료되어 삭제된 경우에는 LRU를 갱신하지 않습니다.
- `DEL`은 저장소, LRU 리스트, TTL 메타데이터를 함께 정리합니다.
- `SET`이 기존 key를 덮어쓰면 기존 TTL을 삭제합니다.
- 단일 엔트리의 `len(key) + len(value)`가 `maxmemory`보다 크면 저장하지 않고 OOM 에러를 반환합니다.

## 파일 구성

- `cli.py`: `mini-redis>` REPL 진입점입니다. 사용자 입력을 받아 `MiniRedis.execute_line`으로 전달합니다.
- `mini_redis.py`: 명령 실행 엔진입니다. String 명령어, LRU, TTL, 메모리 제한, Pub/Sub 명령을 연결합니다.
- `hash_map.py`: 체이닝 방식 해시맵입니다. 버킷 충돌은 이중 연결 리스트로 관리하고, 로드 팩터가 0.75를 넘으면 capacity를 2배로 늘립니다.
- `linked_list.py`: 이중 연결 리스트입니다. 해시맵 버킷, LRU 리스트, Pub/Sub 메시지 큐에 재사용됩니다.
- `min_heap.py`: TTL 만료 관리를 위한 최소 힙입니다. 가장 빨리 만료될 key를 빠르게 찾습니다.
- `dynamic_array.py`: capacity 2배 확장을 포함한 동적 배열입니다. 해시맵 버킷과 힙의 내부 저장소로 사용됩니다.
- `pubsub.py`: 채널별 구독자 목록과 구독자별 메시지 큐를 관리합니다.
- `binary_tree.py`: 보너스 학습용 이진 트리와 전위, 중위, 후위, 레벨 순회 구현입니다.
- `bst.py`: 보너스 학습용 이진 탐색 트리입니다. 삽입, 탐색, 삭제, 중위 순회를 제공합니다.
- `test_mini_redis.py`: 주요 기능과 보너스 구조 일부를 검증하는 unittest 파일입니다.
- `INTERVIEW_PREP.md`: 구현 설명과 면접 답변 포인트를 정리한 문서입니다.
- `STACK_QUEUE_DEQUE.md`: 스택, 큐, 덱 개념과 이 프로젝트에서의 연결점을 정리한 문서입니다.
- `IMPLEMENTATION.md`: 기능들이 코드상에서 어떤 방식으로 구현되어 있는지 따라 읽는 문서입니다.
- `DATA_STRUCTURES.md`: 과제에서 사용된 자료구조를 시각화해 설명하는 문서입니다.

## 에러 출력 예시

```text
mini-redis> HELLO
(error) ERR unknown command 'HELLO'
mini-redis> GET
(error) ERR wrong number of arguments for 'GET' command
mini-redis> CONFIG SET maxmemory abc
(error) ERR value is not an integer or out of range
```

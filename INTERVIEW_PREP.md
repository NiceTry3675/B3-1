# Mini Redis 인터뷰 대비 학습 문서

## 1. 한 문장 설명

이 프로젝트는 직접 구현한 해시맵, 이중 연결 리스트, 최소 힙, 동적 배열을 조합해 Redis의 String 저장, LRU 메모리 제거, TTL 만료 처리를 CLI로 재현한 Mini Redis입니다.

> Redis가 빠른 이유를 자료구조 관점에서 이해하기 위해, key 조회는 해시맵으로, 사용 순서 관리는 이중 연결 리스트로, 만료 시간 관리는 최소 힙으로 직접 구현한 프로젝트입니다.

## 2. 전체 실행 흐름

사용자가 `cli.py`의 REPL에 명령어를 입력하면 `MiniRedis.execute_line`이 문자열을 파싱하고, `MiniRedis.execute`가 명령어별 메서드로 분기합니다.

전체 흐름은 다음과 같습니다.

1. `shlex.split`으로 입력을 토큰화합니다.
2. 명령 실행 전 `_purge_expired`로 이미 만료된 key를 정리합니다.
3. `SET`, `GET`, `DEL`, `EXPIRE` 같은 명령어별 로직을 실행합니다.
4. 저장소, LRU 리스트, TTL 메타데이터, 메모리 사용량을 함께 갱신합니다.
5. Redis 스타일 문자열 출력으로 결과를 반환합니다.

이 구조의 핵심은 데이터가 한 곳에만 저장되지 않는다는 점입니다. 실제 value는 해시맵에 있고, 사용 순서는 LRU 리스트에 있고, 만료 후보는 TTL 힙에 있습니다. 그래서 삭제나 갱신 시 세 구조를 일관되게 정리하는 것이 중요합니다.

## 3. 자료구조별 역할

| 자료구조 | 파일 | 주요 메서드 | 시간복잡도 | Mini Redis에서의 역할 |
| --- | --- | --- | --- | --- |
| 동적 배열 | `dynamic_array.py` | `append`, `get`, `set`, `remove`, `raw_get`, `raw_set` | 인덱스 접근 O(1), append 평균 O(1), remove O(N) | 해시맵 버킷 배열과 힙 내부 저장소 |
| 이중 연결 리스트 | `linked_list.py` | `insert_front`, `insert_back`, `remove_node`, `move_to_front` | 노드를 알고 있으면 삽입/삭제/이동 O(1) | LRU 순서 관리, 해시맵 버킷, Pub/Sub 큐 |
| 해시맵 | `hash_map.py` | `put`, `get`, `remove`, `contains`, `keys` | 평균 O(1), 최악 O(N) | key로 value와 메타데이터를 빠르게 조회 |
| 최소 힙 | `min_heap.py` | `push`, `pop`, `peek` | push/pop O(log N), peek O(1) | 가장 빨리 만료될 TTL key 추적 |

## 4. 해시맵

`hash_map.py`의 `HashMap`은 separate chaining 방식입니다. 버킷 배열의 각 칸에는 필요할 때 이중 연결 리스트가 만들어지고, 같은 버킷으로 충돌한 key-value 쌍은 리스트에 연결됩니다.

해시 함수는 key를 문자열로 바꾼 뒤 UTF-8 바이트를 순회하면서 아래 형태로 누적합니다.

```text
result = result * 31 + byte
index = result % capacity
```

로드 팩터가 `0.75`를 초과하면 버킷 배열을 2배로 늘리고 모든 엔트리를 새 capacity 기준으로 다시 배치합니다. capacity가 바뀌면 `hash % capacity` 결과도 바뀌기 때문에 rehash가 필요합니다.

답변 포인트:

- 평균적으로 `put`, `get`, `remove`는 O(1)입니다.
- 최악의 경우 모든 key가 한 버킷에 몰리면 O(N)입니다.
- 충돌 자체는 문제가 아니고, 충돌을 어떻게 관리하느냐가 중요합니다.
- 이 구현은 Python `dict`를 쓰지 않고 직접 만든 버킷 배열과 연결 리스트로 key-value 저장소를 구성합니다.

## 5. 이중 연결 리스트와 LRU

`linked_list.py`의 노드는 `prev`, `next`, `data`를 가집니다. Mini Redis는 LRU 리스트의 `head`를 가장 최근 사용한 key, `tail`을 가장 오래 사용하지 않은 key로 둡니다.

LRU 갱신 규칙은 다음과 같습니다.

- `SET`으로 key가 새로 저장되면 LRU head에 삽입합니다.
- `SET`으로 기존 key를 덮어쓰면 해당 key의 LRU 노드를 head로 이동합니다.
- `GET`이 성공하면 해당 key의 LRU 노드를 head로 이동합니다.
- `GET` 대상이 없거나 만료되어 삭제된 경우에는 LRU를 갱신하지 않습니다.
- 메모리 제한을 초과하면 tail부터 삭제합니다.

Redis 엔트리인 `RedisValue`가 자기 LRU 노드 포인터를 들고 있으므로, key를 찾은 뒤 리스트 전체를 다시 검색하지 않아도 됩니다.

답변 포인트:

- 해시맵만 있으면 key 조회는 빠르지만 사용 순서를 알 수 없습니다.
- 리스트만 있으면 순서는 알 수 있지만 key 조회가 느립니다.
- 해시맵과 이중 연결 리스트를 함께 쓰면 조회, 이동, 삭제를 평균 O(1)에 처리할 수 있습니다.
- 단일 연결 리스트는 임의 노드 삭제 시 이전 노드를 찾기 위해 탐색이 필요하므로 LRU에는 이중 연결 리스트가 더 적합합니다.

## 6. 메모리 제한과 eviction 흐름

`used_memory`는 요구사항 공식대로 `len(utf8(key)) + len(utf8(value))`의 합입니다. 노드, 포인터, 버킷 오버헤드는 계산하지 않습니다.

`CONFIG SET maxmemory 0`은 무제한을 뜻합니다. `maxmemory`가 0보다 클 때만 eviction이 동작합니다.

`SET` 흐름은 다음과 같습니다.

1. 새 엔트리 하나의 크기를 계산합니다.
2. 단일 엔트리가 `maxmemory`보다 크면 저장하지 않고 OOM 에러를 반환합니다.
3. 새 key면 해시맵에 저장하고 LRU head에 추가합니다.
4. 기존 key면 이전 value 크기를 빼고 새 value 크기를 더한 뒤 LRU head로 이동합니다.
5. 기존 key를 덮어쓴 경우 TTL 메타데이터를 삭제합니다.
6. `used_memory > maxmemory`이면 LRU tail부터 삭제합니다.
7. eviction으로 삭제된 key 수는 `evicted_keys`에 누적됩니다.

단일 엔트리를 먼저 거절하는 이유는 다른 key를 모두 삭제해도 그 엔트리 하나만으로 제한을 초과하기 때문입니다.

## 7. TTL과 최소 힙

TTL은 `(expire_at, key, version)` 형태의 `ExpireRecord`를 `min_heap.py`의 최소 힙에 넣습니다. 가장 빨리 만료될 항목이 heap root에 있으므로 다음 만료 후보를 빠르게 확인할 수 있습니다.

만료 처리는 두 방식이 함께 쓰입니다.

- 명령 실행 전 `_purge_expired`가 힙의 root를 보면서 이미 만료된 key들을 정리합니다.
- 특정 key를 조회하는 명령은 `_delete_if_expired`로 해당 key가 만료되었는지 한 번 더 확인합니다.

같은 key에 `EXPIRE`가 여러 번 호출될 수 있으므로 lazy deletion 전략을 사용합니다. 새 TTL을 설정할 때 version을 증가시키고, 힙에서 꺼낸 레코드의 version이 현재 expiration map의 version과 다르면 오래된 레코드로 보고 무시합니다.

답변 포인트:

- 힙의 `push`와 `pop`은 O(log N), `peek`은 O(1)입니다.
- 모든 key를 매번 순회하며 만료 여부를 찾으면 O(N)입니다.
- 힙은 가장 이른 만료 시간을 계속 추적하는 데 적합합니다.
- lazy deletion은 힙 중간에 있는 오래된 TTL 레코드를 즉시 제거하지 않고, 나중에 root로 올라왔을 때 유효성 검사를 통해 무시하는 방식입니다.

## 8. 명령어 엣지 케이스

- 만료된 key는 명령 실행 전에 삭제되어 없는 key처럼 처리됩니다.
- 만료된 key에 `GET`을 하면 `(nil)`이고 LRU 갱신은 하지 않습니다.
- `TTL`은 key가 없으면 `(integer) -2`, TTL이 없으면 `(integer) -1`입니다.
- `EXPIRE key 0` 또는 음수는 즉시 삭제로 처리합니다.
- `DEL`은 store, TTL metadata, LRU 리스트를 함께 정리합니다.
- `SET`이 기존 key를 덮어쓰면 기존 TTL을 삭제합니다.
- 잘못된 명령은 `(error) ERR unknown command '<CMD>'` 형식으로 반환합니다.
- 인자 개수가 틀리면 `(error) ERR wrong number of arguments for '<CMD>' command` 형식으로 반환합니다.

## 9. 보너스 구현 설명

- `dynamic_array.py`: capacity 2배 확장, `append/get/set/remove` 구현. 힙과 해시맵 버킷 배열의 기반입니다.
- `binary_tree.py`: 전위, 중위, 후위, 레벨 순회 구현. 레벨 순회에는 이중 연결 리스트를 큐처럼 사용합니다.
- `bst.py`: 삽입, 탐색, 삭제, 중위 순회 정렬 결과 구현. 삭제 시 오른쪽 서브트리의 successor를 사용합니다.
- `pubsub.py`: 채널별 구독자 리스트와 구독자별 메시지 큐 구현. 메시지 큐는 이중 연결 리스트로 관리합니다.
- `STACK_QUEUE_DEQUE.md`: 스택, 큐, 덱 개념과 Redis 확장 연결 설명입니다.

## 10. 자주 나올 수 있는 질문

Q. 왜 해시맵과 이중 연결 리스트를 같이 쓰나요?

A. 해시맵은 key 조회를 빠르게 하지만 사용 순서를 모릅니다. 이중 연결 리스트는 사용 순서를 유지하지만 key 조회가 느립니다. 두 구조를 함께 쓰면 key 조회는 해시맵으로 평균 O(1), 사용 순서 이동과 삭제는 리스트 노드 포인터로 O(1)에 처리할 수 있습니다.

Q. 왜 LRU에 단일 연결 리스트가 아니라 이중 연결 리스트를 쓰나요?

A. 임의 노드를 삭제하거나 앞으로 이동할 때 이전 노드를 알아야 합니다. 단일 연결 리스트는 이전 노드를 찾기 위해 탐색이 필요하지만, 이중 연결 리스트는 `prev` 포인터가 있어 O(1)에 연결을 바꿀 수 있습니다.

Q. TTL 관리에 왜 힙을 쓰나요?

A. TTL에서 중요한 질문은 “가장 빨리 만료될 key가 무엇인가?”입니다. 최소 힙은 가장 작은 `expire_at`을 root에 두므로 다음 만료 후보를 O(1)에 확인하고, 삽입과 삭제를 O(log N)에 처리할 수 있습니다.

Q. TTL 힙에서 기존 TTL을 직접 삭제하지 않는 이유는 무엇인가요?

A. 일반 힙에서 중간 원소를 key로 찾아 삭제하려면 별도 인덱스 맵이 필요합니다. 이 구현은 version을 둔 lazy deletion으로 오래된 TTL 레코드를 꺼낼 때 무시합니다. 구현이 단순하고 `EXPIRE` 갱신이 빠릅니다.

Q. `SET`이 기존 key를 덮어쓰면 TTL을 왜 삭제하나요?

A. 요구사항에서 기존 TTL을 초기화하도록 정했기 때문입니다. Redis의 기본 `SET`도 별도 옵션이 없으면 기존 TTL을 제거하는 동작과 유사합니다.

Q. `maxmemory=0`은 어떤 의미인가요?

A. 메모리 제한이 없다는 뜻입니다. 이 경우 `used_memory`는 계속 계산하지만, LRU eviction은 실행하지 않습니다.

Q. OOM 처리에서 단일 엔트리가 `maxmemory`보다 크면 왜 바로 거절하나요?

A. 다른 key를 모두 제거해도 그 엔트리 하나만으로 제한을 초과하기 때문입니다. 저장 후 eviction을 해도 조건을 만족할 수 없어 저장하지 않는 것이 맞습니다.

Q. 만료된 key가 있으면 바로 사라지나요?

A. 백그라운드 스레드가 없기 때문에 시간만 지난다고 자동으로 출력이 바뀌는 것은 아닙니다. 대신 다음 명령이 실행될 때 `_purge_expired`가 힙을 확인해 만료된 key를 정리합니다. 특정 key를 조회할 때도 `_delete_if_expired`로 한 번 더 확인합니다.

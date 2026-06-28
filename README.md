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

## 자료구조와 심화 개념 설명

이 프로젝트의 핵심은 Redis 명령어를 흉내 내는 것보다, 빠른 조회와 제거를 위해 여러 자료구조를 함께 쓰는 이유를 설명할 수 있게 만드는 것입니다.

### 이중 연결 리스트

`linked_list.py`의 `Node`는 `prev`, `next`, `data` 세 필드를 가집니다.

```text
prev <- [ data ] -> next
```

`DoublyLinkedList`는 `head`, `tail`, `_size`를 들고 있어서 앞과 뒤를 바로 알 수 있습니다.

주요 메서드의 동작은 다음과 같습니다.

| 메서드 | 동작 | 시간복잡도 |
| --- | --- | --- |
| `insert_front` | 새 노드를 `head` 앞에 연결 | O(1) |
| `insert_back` | 새 노드를 `tail` 뒤에 연결 | O(1) |
| `remove_front` | `head` 노드를 제거 | O(1) |
| `remove_back` | `tail` 노드를 제거 | O(1) |
| `remove_node` | 전달받은 노드의 앞뒤 노드를 서로 연결하고 제거 | O(1) |
| `move_to_front` | 전달받은 노드를 제거한 뒤 `head`에 다시 삽입 | O(1) |

`remove_node`가 O(1)인 이유는 삭제할 노드가 자기 앞 노드(`prev`)와 뒤 노드(`next`)를 이미 알고 있기 때문입니다. 단일 연결 리스트라면 이전 노드를 찾기 위해 처음부터 순회해야 할 수 있지만, 이중 연결 리스트는 포인터 몇 개만 바꾸면 됩니다.

### 해시맵의 해시 함수와 인덱스 계산

`hash_map.py`의 `HashMap`은 Python `dict` 대신 직접 구현한 체이닝 해시맵입니다. key를 저장할 위치는 다음 흐름으로 정합니다.

```text
key
-> str(key)
-> UTF-8 bytes
-> result = result * 31 + byte
-> index = result % capacity
```

실제 해시 함수는 문자열의 UTF-8 바이트를 왼쪽부터 읽으며 `31`을 곱해 누적합니다. 마지막에는 `capacity`로 나눈 나머지를 버킷 인덱스로 사용합니다.

```text
_hash("user:1") % 8 = bucket index
```

해시 함수는 key를 넓은 숫자 공간에 퍼뜨리고, `% capacity`는 그 숫자를 현재 버킷 배열 범위 안의 인덱스로 바꿉니다.

### 충돌 해결과 체이닝

서로 다른 key라도 같은 버킷 인덱스가 나올 수 있습니다. 이것을 해시 충돌이라고 합니다.

```text
bucket[3] -> ("user:1", "Alice") <-> ("cart:7", "Book")
```

이 프로젝트는 충돌을 체이닝 방식으로 해결합니다. 버킷 하나가 비어 있으면 새 `DoublyLinkedList`를 만들고, 같은 버킷으로 들어온 `HashEntry(key, value)`들을 그 리스트에 이어 붙입니다.

조회할 때는 먼저 해시로 버킷을 찾고, 그 버킷 리스트 안에서 같은 key를 찾습니다. 평균적으로 버킷에 들어 있는 원소 수가 짧게 유지되면 `put`, `get`, `remove`는 O(1)에 가깝습니다. 최악의 경우 모든 key가 한 버킷에 몰리면 O(N)이 될 수 있습니다.

### 로드 팩터와 리사이즈

로드 팩터는 해시맵이 얼마나 차 있는지 나타내는 값입니다.

```text
load factor = size / capacity
```

`HashMap.put`은 새 key를 추가한 뒤 로드 팩터가 `0.75`를 넘으면 버킷 배열의 capacity를 2배로 늘립니다.

```text
capacity 8, size 7 -> load factor 0.875
resize to capacity 16
```

capacity가 바뀌면 `hash % capacity` 결과도 바뀌므로 기존 엔트리를 새 버킷 배열에 다시 배치해야 합니다. 이 과정을 rehash라고 합니다. 리사이즈 한 번은 O(N)이지만, 자주 발생하지 않도록 capacity를 2배씩 키우기 때문에 일반적인 삽입은 평균 O(1)로 볼 수 있습니다.

### LRU에서 해시맵과 이중 연결 리스트를 함께 쓰는 이유

LRU는 Least Recently Used의 약자로, 가장 오래 사용하지 않은 key를 먼저 제거하는 정책입니다.

Mini Redis의 LRU 리스트는 다음 규칙을 따릅니다.

```text
head                                      tail
가장 최근 사용                          가장 오래 사용하지 않음
[user:3] <-> [user:2] <-> [user:1]
```

해시맵과 리스트의 역할은 다릅니다.

| 자료구조 | 역할 |
| --- | --- |
| 해시맵 `_store` | key로 `RedisValue`를 평균 O(1)에 찾음 |
| 이중 연결 리스트 `_lru` | 최근 사용 순서를 보관하고 tail에서 오래된 key를 찾음 |
| `RedisValue.lru_node` | 해당 key가 LRU 리스트의 어느 노드인지 바로 가리킴 |

해시맵만 있으면 key 조회는 빠르지만 사용 순서를 알 수 없습니다. 리스트만 있으면 사용 순서는 알 수 있지만 특정 key를 찾으려면 순회해야 합니다. 둘을 함께 쓰면 `GET key`로 엔트리를 평균 O(1)에 찾고, 그 엔트리가 들고 있는 `lru_node`를 O(1)에 `head`로 옮길 수 있습니다.

### O(1) LRU 달성 원리

`GET user:1`이 성공했을 때의 흐름은 다음과 같습니다.

1. `_store.get("user:1")`로 `RedisValue`를 찾습니다. 평균 O(1)입니다.
2. `RedisValue.lru_node`로 LRU 리스트의 노드를 바로 얻습니다.
3. `_lru.move_to_front(node)`로 해당 노드를 최신 위치로 옮깁니다. O(1)입니다.

`SET`으로 기존 key를 갱신할 때도 같은 방식으로 LRU 노드를 `head`로 옮깁니다. 메모리가 초과되면 `_lru.tail.data`가 가장 오래 사용하지 않은 key이므로 tail부터 삭제합니다. 이 과정도 tail 포인터를 바로 사용하므로 오래된 key를 찾기 위해 전체 리스트를 순회하지 않습니다.

### TTL 관리에 최소 힙을 쓰는 이유

TTL에서 자주 필요한 질문은 “가장 먼저 만료될 key가 무엇인가?”입니다. 모든 key를 매 명령마다 순회하면 O(N)이 걸립니다. 최소 힙은 가장 작은 `expire_at`을 root에 두므로 가장 빨리 만료될 후보를 O(1)에 확인할 수 있습니다.

TTL 레코드는 다음 형태로 힙에 들어갑니다.

```text
ExpireRecord(expire_at, key, version)
```

`MinHeap.push`는 새 레코드를 배열 끝에 넣고 `_heapify_up`으로 부모와 비교하며 올립니다. `pop`은 root를 꺼낸 뒤 마지막 값을 root로 옮기고 `_heapify_down`으로 자식과 비교하며 내립니다.

```text
push: O(log N)
pop:  O(log N)
peek: O(1)
```

같은 key에 `EXPIRE`가 여러 번 호출되면 힙 안에 예전 만료 레코드가 남을 수 있습니다. 이 구현은 `version`을 사용한 lazy deletion으로 해결합니다. 힙에서 꺼낸 레코드의 version이 `_expirations`에 저장된 현재 version과 다르면 오래된 레코드로 보고 무시합니다.

### 메모리 초과 시 eviction 흐름

`SET key value`가 실행되면 메모리 제한은 다음 순서로 처리됩니다.

1. 새 엔트리 크기를 `len(utf8(key)) + len(utf8(value))`로 계산합니다.
2. `maxmemory > 0`이고 단일 엔트리 크기가 `maxmemory`보다 크면 저장하지 않고 OOM 에러를 반환합니다.
3. 새 key면 LRU `head`에 key 노드를 만들고 `_store`에 `RedisValue(value, lru_node)`를 저장합니다.
4. 기존 key면 이전 value 크기를 `used_memory`에서 빼고 새 value 크기를 더한 뒤 LRU 노드를 `head`로 옮깁니다.
5. 기존 key를 `SET`으로 덮어쓴 경우 TTL 메타데이터를 삭제합니다.
6. `used_memory > maxmemory`인 동안 `_lru.tail.data`를 읽어 가장 오래 사용하지 않은 key부터 삭제합니다.
7. eviction으로 삭제된 key마다 `evicted_keys`를 1 증가시킵니다.

삭제는 `_delete_key`로 모아서 처리합니다. 이 메서드는 `_store`, `_expirations`, `_lru`, `_used_memory`를 함께 갱신하므로 한 구조에만 찌꺼기 데이터가 남지 않게 합니다.

### GET 명령어 전체 실행 흐름

`GET key`는 단순 조회가 아니라 TTL과 LRU를 함께 고려합니다.

1. `execute` 진입 시 `_purge_expired()`가 먼저 실행되어 이미 만료된 key들을 정리합니다.
2. `_cmd_get`에서 인자 개수가 맞는지 확인합니다.
3. `_delete_if_expired(key)`로 조회 대상 key가 만료되었는지 다시 확인합니다.
4. 만료되었거나 `_store`에 없으면 `(nil)`을 반환합니다.
5. 존재하면 value를 `"value"` 형태로 반환합니다.
6. 조회 성공한 key는 방금 사용한 key이므로 `entry.lru_node = _lru.move_to_front(entry.lru_node)`로 최신 위치로 이동합니다.

중요한 점은 만료되어 삭제된 key는 LRU를 갱신하지 않는다는 것입니다. 없는 key를 최근 사용한 key처럼 취급하면 LRU 순서가 잘못됩니다.

### LFU 정책으로 바꾼다면

현재 구현은 LRU이므로 “마지막으로 언제 사용했는가”를 기준으로 삭제합니다. LFU는 Least Frequently Used의 약자로 “사용 횟수가 가장 적은 key”를 먼저 삭제합니다.

LFU로 바꾸려면 `RedisValue`에 사용 횟수와 위치 정보를 추가해야 합니다.

```text
RedisValue(value, lru_node, frequency)
```

대표적인 O(1) LFU 구조는 다음 조합을 사용합니다.

| 구조 | 역할 |
| --- | --- |
| key 해시맵 | key -> value, frequency, frequency 리스트 노드 |
| frequency 해시맵 | frequency -> 같은 빈도의 key들을 담은 이중 연결 리스트 |
| `min_frequency` | 현재 가장 낮은 사용 빈도 |

`GET`이나 기존 key `SET`이 성공하면 해당 key의 frequency를 1 올리고, 기존 frequency 리스트에서 다음 frequency 리스트로 노드를 이동합니다. 메모리가 초과되면 `min_frequency` 리스트의 tail에서 가장 오래된 key를 제거하면 됩니다. 이렇게 하면 “사용 횟수는 적고, 같은 횟수 안에서는 오래된 key”를 제거하는 정책을 만들 수 있습니다.

단순히 key마다 count만 저장하면 삭제할 최저 빈도 key를 찾기 위해 전체 key를 순회해야 하므로 O(N)이 됩니다. LFU에서도 O(1)에 가깝게 동작하려면 frequency별 리스트와 `min_frequency`가 필요합니다.

### 데이터가 10만 건으로 늘어났을 때 병목과 개선

10만 건 수준으로 커지면 기능은 그대로여도 다음 지점이 병목이 될 수 있습니다.

| 병목 가능 지점 | 이유 | 개선 방향 |
| --- | --- | --- |
| 해시 충돌 증가 | 버킷이 부족하거나 해시 분포가 나쁘면 한 버킷 리스트가 길어짐 | capacity 확장 정책 유지, 해시 함수 개선, 충돌 통계 관찰 |
| `KEYS` 명령 | 전체 key를 모두 순회하므로 O(N) | 운영용이라면 cursor 기반 `SCAN` 방식으로 분할 조회 |
| TTL lazy deletion | `EXPIRE` 갱신이 많으면 오래된 힙 레코드가 쌓임 | heap record 수를 관찰하고, 필요하면 key -> heap index 맵을 추가해 직접 갱신 |
| 리사이즈 순간 비용 | capacity 2배 확장 시 전체 rehash가 발생 | 점진적 rehash나 초기 capacity 설정 옵션 도입 |
| Python 객체 오버헤드 | 노드, 엔트리, 레코드 객체가 많아질수록 실제 메모리 사용 증가 | 객체 수 줄이기, 슬롯 구조 사용, 더 정확한 메모리 모델 도입 |

현재 과제 범위에서는 평균 O(1) 조회와 O(log N) TTL 처리가 핵심입니다. 실서비스 수준으로 확장한다면 `KEYS` 같은 전체 순회 명령을 조심하고, TTL 힙의 오래된 레코드가 과도하게 쌓이는지 확인하는 것이 중요합니다.

### used_memory에 자료구조 오버헤드를 포함한다면

현재 `used_memory`는 요구사항에 맞춰 아래 값만 계산합니다.

```text
used_memory = sum(len(utf8(key)) + len(utf8(value)))
```

그래서 해시맵 버킷 배열, `HashEntry`, 연결 리스트 `Node`, `RedisValue`, TTL 레코드 같은 오버헤드는 제외됩니다. 만약 더 현실적인 메모리 모델로 바꾼다면 다음 항목을 함께 더해야 합니다.

```text
entry_memory =
  key bytes
  + value bytes
  + RedisValue object overhead
  + HashEntry overhead
  + LRU Node overhead
  + bucket chain Node overhead
  + optional Expiration overhead
  + optional heap ExpireRecord overhead
  + share of bucket array slots
```

구현 방식은 두 가지가 있습니다.

1. 고정 상수 모델: 노드, 엔트리, 포인터, 힙 슬롯의 비용을 상수로 정하고 저장/삭제 시 함께 더하고 뺍니다.
2. 보정 모델: 실제 Python 객체 크기와 테스트 데이터를 기준으로 평균 오버헤드 상수를 정하고 `INFO memory`가 그 값을 반영하게 합니다.

이 과제에서는 요구사항의 공식이 명확하므로 key/value byte만 계산했습니다. 하지만 실제 Redis처럼 운영 메모리에 가깝게 보려면 데이터 자체보다 자료구조를 유지하는 비용도 포함해야 합니다.

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

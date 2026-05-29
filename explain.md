# Mini Redis 과제 강의: “작은 Redis를 직접 만들면서 자료구조 배우기”

이 저장소의 과제는 **Mini Redis**입니다. 진짜 Redis처럼 네트워크 서버나 파일 저장까지 구현하는 과제는 아니고, CLI에서 명령어를 입력하면 key-value 데이터를 저장·조회·삭제하는 작은 Redis를 만드는 학습용 프로젝트입니다. 핵심 조건은 Python의 `dict`, `set`, `collections`로 핵심 저장소를 대체하지 않고, 직접 만든 **해시맵, 이중 연결 리스트, 최소 힙, 동적 배열**을 조합하는 것입니다. 

---

## 1. 이 과제는 한 문장으로 뭐냐?

이름표(key)로 값(value)을 저장하고, 빨리 찾고, 오래 안 쓴 데이터는 지우고, 시간이 지나면 자동 만료시키는 작은 저장소를 직접 구현하는 과제입니다.

예를 들어 사용자는 이렇게 입력합니다.

```text
mini-redis> SET user:1 "Alice"
OK

mini-redis> GET user:1
"Alice"

mini-redis> DBSIZE
(integer) 1
```

저장소 실행은 `python3 cli.py`로 시작하고, `mini-redis>` 프롬프트에서 명령어를 입력하는 구조입니다. 

---

## 2. Redis를 모른다고 생각하고 비유해 보자

이 프로그램을 **사물함 관리 시스템**이라고 생각하면 쉽습니다.

`SET user:1 Alice`는 “`user:1`이라는 이름표가 붙은 사물함에 `Alice`를 넣어라”입니다.

`GET user:1`은 “`user:1` 사물함 안에 뭐가 있니?”입니다.

`DEL user:1`은 “그 사물함을 비워라”입니다.

`EXPIRE user:1 10`은 “이 사물함은 10초 뒤 자동으로 비워라”입니다.

`CONFIG SET maxmemory 30`은 “전체 사물함에 넣을 수 있는 글자 수를 30바이트로 제한해라”입니다.

그런데 공간이 부족해지면 누구 것을 버릴까요? 이 과제에서는 **LRU**, 즉 “가장 오래 안 쓴 것부터 버리자”라는 규칙을 씁니다. README에도 메모리 제한을 넘으면 가장 오래 사용되지 않은 key부터 삭제하며, LRU 리스트의 `head`가 가장 최근 사용된 key이고 `tail`이 가장 오래 사용되지 않은 key라고 설명되어 있습니다. 

---

## 3. 전체 구조: 사용자가 입력한 한 줄은 어디로 가나?

프로그램 흐름은 이렇게 보면 됩니다.

```text
사용자 입력
  ↓
cli.py
  ↓
MiniRedis.execute_line(line)
  ↓
MiniRedis.execute(parts)
  ↓
_cmd_set / _cmd_get / _cmd_expire / ...
  ↓
문자열 결과 출력
```

구현 문서에도 실행 진입점은 `cli.py`이고, 사용자의 한 줄 입력이 `MiniRedis.execute_line(line)`으로 전달된 뒤 명령별 메서드로 나뉜다고 되어 있습니다. 

`MiniRedis` 객체 안에는 여러 자료구조가 들어 있습니다.

```python
self._store = HashMap()
self._expirations = HashMap()
self._ttl_heap = MinHeap()
self._lru = DoublyLinkedList()
self._pubsub = PubSub()
```

각각의 역할은 다음과 같습니다.

| 필드             | 쉬운 의미           | 역할             |
| -------------- | --------------- | -------------- |
| `_store`       | 실제 사물함          | key-value 저장   |
| `_expirations` | 만료 시간 표         | key별 TTL 정보 저장 |
| `_ttl_heap`    | 가장 빨리 만료될 것 정렬기 | 다음에 만료될 key 찾기 |
| `_lru`         | 최근 사용 순서 줄      | 오래 안 쓴 key 찾기  |
| `_pubsub`      | 방송/구독 관리소       | Pub/Sub 메시지 처리 |

구현 문서에서도 `_store`, `_expirations`, `_ttl_heap`, `_lru`, `_pubsub`가 각각 실제 저장소, TTL 메타데이터, TTL 후보 관리, 최근 사용 순서, Pub/Sub 관리를 맡는다고 정리되어 있습니다. 

---

## 4. 이 과제에서 지원하는 명령어

### 4.1 기본 저장소 명령어

| 명령어             | 뜻             |
| --------------- | ------------- |
| `SET key value` | key에 value 저장 |
| `GET key`       | key의 value 조회 |
| `DEL key`       | key 삭제        |
| `EXISTS key`    | key가 있는지 확인   |
| `DBSIZE`        | key 개수 확인     |
| `KEYS`          | 전체 key 목록 출력  |

README에는 이 String 명령어들이 표로 정리되어 있고, `GET`과 `SET` 성공 시 LRU 최신 위치로 이동한다고 설명되어 있습니다. 

### 4.2 메모리와 LRU 명령어

| 명령어                          | 뜻                             |
| ---------------------------- | ----------------------------- |
| `CONFIG SET maxmemory bytes` | 저장소 최대 메모리 설정                 |
| `INFO memory`                | 현재 메모리 사용량, 제한값, 삭제된 key 수 확인 |

메모리 사용량은 단순히 `len(key의 UTF-8 바이트) + len(value의 UTF-8 바이트)` 합으로 계산하고, 노드나 포인터 같은 자료구조 오버헤드는 계산하지 않습니다. 

### 4.3 TTL 명령어

| 명령어                  | 뜻                       |
| -------------------- | ----------------------- |
| `EXPIRE key seconds` | key를 seconds초 뒤 만료되게 설정 |
| `TTL key`            | key가 몇 초 뒤 만료되는지 확인     |

TTL 결과는 Redis 스타일입니다.

```text
key가 없으면        (integer) -2
key는 있지만 TTL 없음 (integer) -1
TTL 있음            (integer) N
```

README에도 이 출력 규칙과, 만료된 key는 명령 실행 전에 먼저 정리된다고 설명되어 있습니다. 

### 4.4 Pub/Sub 보너스 명령어

| 명령어                            | 뜻                |
| ------------------------------ | ---------------- |
| `SUBSCRIBE subscriber channel` | 사용자를 채널에 구독시킴    |
| `PUBLISH channel message`      | 채널 구독자들에게 메시지 전송 |
| `MESSAGES subscriber`          | 구독자가 받은 메시지 확인   |
| `CLEARMSG subscriber`          | 구독자의 메시지 큐 비우기   |

README에는 단일 CLI 환경에서 확인하기 쉽도록 구독자 이름을 직접 받는 방식이라고 되어 있습니다. 

---

# 5. 이제 자료구조를 하나씩 이해해 보자

이 과제의 핵심은 “명령어 구현”보다 **왜 이 자료구조가 필요한가**입니다.

---

## 5.1 동적 배열: “필요하면 커지는 칸 목록”

일반 배열은 칸 수가 정해져 있습니다.

```text
[ A ][ B ][ C ][ D ]
```

공간이 부족해지면 더 큰 배열을 만들고 기존 값을 옮깁니다.

```text
기존 배열:
[ A ][ B ][ C ][ D ]

더 큰 배열:
[ A ][ B ][ C ][ D ][   ][   ][   ][   ]
```

이 과제의 `DynamicArray`는 내부에 고정 길이 Python list를 두고, `append`, `resize`, `get`, `set`, `remove`를 직접 구현합니다. 코드에서도 용량이 부족하면 `_resize(self._capacity * 2)`로 공간을 두 배 늘립니다.  

동적 배열은 혼자 주인공이라기보다, 다른 자료구조의 **바닥 재료**입니다. 해시맵의 버킷 배열과 힙의 내부 저장소로 쓰입니다. 

---

## 5.2 해시맵: “key로 value를 빨리 찾는 사전”

해시맵은 이 과제에서 가장 중요한 자료구조입니다.

```text
user:1  -> Alice
user:2  -> Bob
token   -> abc123
```

`GET user:1`을 했을 때 모든 key를 처음부터 끝까지 뒤지면 느립니다. 해시맵은 key를 숫자로 바꾼 뒤 저장 위치를 계산합니다.

```text
"user:1"
   ↓
해시 함수
   ↓
버킷 번호
```

이 저장소의 `HashMap`은 `DynamicArray`를 버킷 배열로 쓰고, 충돌이 생기면 같은 버킷 안에 `DoublyLinkedList`로 여러 `HashEntry`를 이어 붙입니다. 코드에서도 `HashMap`은 별도 체이닝 방식이고, 로드 팩터가 0.75를 넘으면 capacity를 두 배로 늘린다고 되어 있습니다. 

실제 `put`은 대략 이렇게 동작합니다.

1. key를 해시해서 버킷 위치를 찾는다.
2. 그 버킷 안에 같은 key가 있는지 확인한다.
3. 있으면 value만 바꾼다.
4. 없으면 새 `HashEntry`를 리스트 뒤에 붙인다.
5. 너무 꽉 차면 배열 크기를 두 배로 늘린다.

코드에서도 같은 key를 찾으면 value를 갱신하고, 없으면 `bucket.insert_back(HashEntry(key, value))`로 추가한 뒤, `self._size / self._capacity > 0.75`이면 `_resize`를 호출합니다. 

초심자식으로 말하면 해시맵은 **“이름표를 보고 바로 사물함 번호를 계산하는 표”**입니다.

---

## 5.3 이중 연결 리스트: “앞뒤로 연결된 줄”

연결 리스트는 이런 모양입니다.

```text
A -> B -> C
```

이중 연결 리스트는 앞뒤를 모두 압니다.

```text
A <-> B <-> C
```

각 노드는 `prev`, `next`, `data`를 가집니다. 코드에서도 `Node`가 `prev`, `next`, `data` 필드를 갖고, `DoublyLinkedList`가 `head`, `tail`, `_size`를 가집니다. 

이 구조가 중요한 이유는 **중간 노드를 빠르게 빼거나 앞으로 옮길 수 있기 때문**입니다.

LRU에서 이중 연결 리스트는 이렇게 씁니다.

```text
head                                      tail
가장 최근 사용                          가장 오래 사용하지 않음

[user:3] <-> [user:2] <-> [user:1]
```

`GET user:1`을 하면 `user:1`은 방금 사용된 것이므로 맨 앞으로 갑니다.

```text
조회 전:
[user:3] <-> [user:2] <-> [user:1]

GET user:1

조회 후:
[user:1] <-> [user:3] <-> [user:2]
```

구현 문서도 LRU에서 `head`는 가장 최근 사용, `tail`은 가장 오래 사용하지 않은 key라고 설명하고, 메모리 초과 시 `_lru.tail.data`를 읽어 삭제한다고 되어 있습니다. 

---

## 5.4 LRU: “오래 안 쓴 것부터 버리는 규칙”

LRU는 자료구조라기보다 **삭제 정책**입니다.

공간이 꽉 찼을 때 아무거나 지우면 안 됩니다. 보통 최근에 쓴 데이터는 또 쓸 가능성이 높고, 오래 안 쓴 데이터는 다시 안 쓸 가능성이 높다고 가정합니다.

그래서 LRU는 이렇게 말합니다.

```text
메모리가 부족하면 가장 오래 안 쓴 key부터 지우자.
```

이 과제에서는 `SET`이나 성공한 `GET`이 일어나면 해당 key를 LRU 리스트의 앞쪽으로 보냅니다. 실제 `GET` 코드도 key가 존재하면 `entry.lru_node = self._lru.move_to_front(entry.lru_node)`를 실행한 뒤 값을 반환합니다. 

메모리 초과 삭제는 `_evict_if_needed()`가 담당합니다.

```python
while self._used_memory > self._maxmemory and self._lru.tail is not None:
    key = self._lru.tail.data
    self._delete_key(key, count_eviction=True)
```

즉, 제한을 넘으면 계속 `tail`, 곧 가장 오래 안 쓴 key를 삭제합니다. 

---

## 5.5 최소 힙: “가장 빨리 만료될 key를 맨 위에 두는 구조”

TTL을 생각해 봅시다.

```text
user:1 -> 10초 뒤 만료
user:2 -> 3초 뒤 만료
user:3 -> 7초 뒤 만료
```

가장 먼저 확인해야 할 것은 `user:2`입니다.

이때 모든 key를 매번 다 뒤져서 “누가 제일 빨리 만료되지?”를 찾으면 비효율적입니다. 그래서 **최소 힙**을 씁니다.

최소 힙은 가장 작은 값이 항상 맨 위에 있습니다. 이 과제에서는 그 “작은 값”이 만료 시각 `expire_at`입니다. 자료구조 문서에서도 Mini Redis에서 최소 힙은 “가장 빨리 만료될 데이터”를 찾는 데 잘 맞는다고 설명합니다. 

코드에서 `ExpireRecord`는 `expire_at`, `key`, `version`을 가지고, `__lt__`에서 `expire_at` 기준으로 비교합니다. 

---

# 6. SET 명령어는 실제로 어떤 일을 할까?

초심자는 `SET`을 “그냥 저장”이라고 생각하기 쉽지만, 이 과제에서 `SET`은 꽤 많은 일을 합니다.

```text
SET user:1 Alice
```

이 한 줄이 들어오면 내부에서는 대략 이렇게 처리합니다.

1. 인자가 `SET key value` 형태인지 확인한다.
2. key와 value의 바이트 크기를 계산한다.
3. 한 항목이 maxmemory보다 크면 저장하지 않는다.
4. 새 key면 LRU 리스트 앞에 key를 넣는다.
5. `_store` 해시맵에 key-value를 저장한다.
6. 기존 key면 value를 바꾸고 LRU 위치를 앞으로 옮긴다.
7. 기존 TTL은 삭제한다.
8. 메모리가 초과되면 LRU 기준으로 오래 안 쓴 key를 삭제한다.

구현 문서도 `SET`이 value, LRU 순서, TTL 정보, 메모리 사용량을 함께 갱신한다고 설명합니다. 

실제 코드에서도 새 key면 `_lru.insert_front(key)`로 LRU 앞에 넣고, `_store.put(key, RedisValue(value, node))`로 저장합니다. 기존 key면 값을 바꾸고 `move_to_front`로 최근 사용 위치로 옮깁니다. 그리고 마지막에 `_expirations.remove(key)`로 기존 TTL을 지웁니다. 

여기서 중요한 설계가 하나 있습니다. `_store`에는 그냥 문자열 value만 저장하지 않고 `RedisValue(value, lru_node)`를 저장합니다. 즉, value와 함께 “LRU 리스트에서 이 key가 있는 노드”도 들고 있습니다. 그래야 `GET`이나 `SET` 때 리스트에서 해당 노드를 빠르게 앞으로 옮길 수 있습니다. 

---

# 7. GET 명령어는 왜 LRU를 바꿀까?

```text
GET user:1
```

`GET`은 값을 읽는 명령어입니다. 그런데 이 과제에서는 조회도 “사용”으로 봅니다.

그래서 `GET user:1`에 성공하면 `user:1`은 방금 사용된 key가 됩니다. 즉 LRU 리스트 맨 앞으로 가야 합니다.

실제 흐름은 다음과 같습니다.

1. 인자가 `GET key`인지 확인한다.
2. 해당 key가 만료됐는지 확인한다.
3. 없거나 만료됐으면 `(nil)`을 반환한다.
4. 있으면 LRU 노드를 앞으로 옮긴다.
5. value를 `"value"` 형태로 반환한다.

구현 문서도 `GET` 성공 시 해당 LRU 노드를 `move_to_front`로 이동한다고 설명합니다. 

---

# 8. TTL은 왜 해시맵과 힙을 둘 다 쓸까?

TTL은 “몇 초 뒤 자동 삭제” 기능입니다.

```text
SET token abc
EXPIRE token 3
```

그러면 `token`은 3초 뒤 만료되어야 합니다.

여기서 두 가지 질문이 생깁니다.

첫째, `TTL token`을 입력했을 때 token의 만료 시간을 바로 알고 싶습니다.
이건 `_expirations` 해시맵이 담당합니다.

```text
token -> Expiration(expire_at, version)
```

둘째, 시간이 지났을 때 “가장 빨리 만료될 key가 뭐지?”를 알고 싶습니다.
이건 `_ttl_heap` 최소 힙이 담당합니다.

구현 문서도 TTL 정보가 `_expirations`와 `_ttl_heap` 두 군데에 저장된다고 설명합니다. `_expirations`는 특정 key의 현재 TTL 확인용이고, `_ttl_heap`은 가장 빨리 만료될 key 찾기용입니다. 

---

## 8.1 만료 정리는 언제 일어날까?

이 프로그램은 백그라운드 스레드가 계속 돌면서 삭제하는 구조가 아닙니다. 대신 명령어가 들어올 때마다 먼저 `_purge_expired()`를 호출합니다.

실제 `execute` 메서드는 명령어를 확인한 뒤 바로 `self._purge_expired()`를 호출합니다. 

`_purge_expired()`는 힙의 맨 위를 봅니다.

```text
힙의 root = 가장 빨리 만료될 후보
```

그 후보가 아직 만료되지 않았다면 멈춥니다. 왜냐하면 최소 힙에서 맨 위가 아직 만료 전이면, 그 아래 것들은 더 늦게 만료되기 때문입니다.

후보가 만료됐다면 힙에서 꺼내고, 현재 TTL 정보와 버전이 맞는지 확인한 뒤 삭제합니다. 실제 코드도 `record = self._ttl_heap.peek()`로 맨 위를 확인하고, `record.expire_at > now`이면 멈추며, 만료된 레코드는 pop한 뒤 version을 확인해 `_delete_key`를 호출합니다. 

---

## 8.2 lazy deletion은 뭘까?

같은 key에 `EXPIRE`를 여러 번 걸 수 있습니다.

```text
EXPIRE token 10
EXPIRE token 30
```

그러면 힙 안에는 예전 기록과 새 기록이 같이 남을 수 있습니다.

```text
token, 10초 뒤 만료, version 1
token, 30초 뒤 만료, version 2
```

힙 중간에서 예전 기록을 찾아 삭제하는 건 번거롭습니다. 그래서 이 과제는 **lazy deletion**, 즉 “나중에 꺼낼 때 오래된 기록이면 무시하자” 방식을 씁니다.

구현 문서에서도 예전 TTL 레코드를 힙 중간에서 직접 찾아 삭제하지 않고, version을 사용해서 `_purge_expired`가 힙에서 레코드를 꺼냈을 때 현재 version과 다르면 오래된 레코드로 보고 무시한다고 설명합니다. 

초심자식으로 말하면 이렇습니다.

```text
책상 위에 옛날 알람 쪽지가 남아 있어도,
알람 시간이 됐을 때 확인해서
"아, 이건 옛날 쪽지네" 하고 버리는 방식
```

---

# 9. Pub/Sub은 어떻게 이해하면 될까?

Pub/Sub은 “방송 채널”이라고 생각하면 쉽습니다.

```text
SUBSCRIBE alice news
```

alice가 news 채널을 구독합니다.

```text
PUBLISH news "hi"
```

news 채널을 구독한 사람들의 메시지 큐에 `"news: hi"`가 들어갑니다.

```text
MESSAGES alice
```

alice가 받은 메시지 목록을 봅니다.

코드에서 `PubSub`은 `_channels`와 `_queues`라는 두 해시맵을 사용합니다. `_channels`는 channel에서 subscriber 리스트를 찾는 용도이고, `_queues`는 subscriber별 메시지 큐를 찾는 용도입니다. 

`publish`는 해당 channel의 subscriber 리스트를 순회하면서 각 subscriber의 큐 뒤에 메시지를 붙입니다. 코드에서도 `queue.insert_back(Message(channel, message))`로 메시지를 뒤에 추가합니다. 

여기서 메시지 큐는 “먼저 들어온 메시지를 먼저 보여주는 줄”로 이해하면 됩니다.

---

# 10. BST 보너스는 왜 있나?

이 과제에는 Mini Redis 핵심 기능 외에 보너스 학습용으로 이진 트리와 BST가 있습니다.

BST, 즉 이진 탐색 트리는 이런 규칙을 갖습니다.

```text
왼쪽에는 더 작은 key
오른쪽에는 더 큰 key
```

예를 들어 4를 기준으로 2는 왼쪽, 6은 오른쪽에 둡니다.

```text
        4
      /   \
     2     6
    / \   / \
   1   3 5   7
```

BST의 좋은 점은 찾을 때 매번 왼쪽 또는 오른쪽 중 한쪽만 고르면 된다는 것입니다. `5`를 찾는다면 `4보다 크니까 오른쪽`, `6보다 작으니까 왼쪽`, 이렇게 이동합니다. 자료구조 문서도 BST는 왼쪽에 작은 값, 오른쪽에 큰 값을 두며, 중위 순회를 하면 정렬된 순서로 값을 볼 수 있다고 설명합니다. 

코드의 `BinarySearchTree`는 삽입, 탐색, 삭제, 중위 순회를 제공합니다. 

---

# 11. 테스트는 무엇을 확인하나?

테스트는 이 과제에서 “반드시 제대로 돼야 하는 기능”을 보여주는 좋은 안내서입니다.

테스트 파일은 다음을 확인합니다.

* `SET`, `GET`, `CONFIG SET maxmemory`, `INFO memory`가 함께 동작하는지
* 메모리 초과 시 LRU key가 삭제되는지
* `EXPIRE`, `TTL`, 만료 삭제가 동작하는지
* `SET`이 기존 TTL을 삭제하는지
* 잘못된 명령어와 인자 오류가 Redis 스타일로 출력되는지
* Pub/Sub 메시지가 구독자 큐에 쌓이는지
* BST 삽입, 탐색, 삭제, 중위 순회가 동작하는지

실제 테스트에서도 maxmemory를 30으로 설정한 뒤 세 key를 넣고, 오래된 key가 삭제되어 `GET user:1`이 `(nil)`이 되는지 확인합니다. 

TTL 테스트에서는 `FakeClock`으로 시간을 직접 움직여 실제로 기다리지 않고 만료를 검증합니다. 예를 들어 `EXPIRE a 1` 뒤에 시간을 2초 전진시키고 `GET a`가 `(nil)`인지 확인합니다. 

또 `SET a two`를 하면 기존 TTL이 지워져 `TTL a`가 `(integer) -1`이 되는지도 확인합니다. 

---

# 12. 파일별로 무엇을 보면 되나?

이 저장소는 파일 역할이 비교적 명확합니다.

| 파일                   | 역할           |
| -------------------- | ------------ |
| `cli.py`             | CLI 진입점      |
| `mini_redis.py`      | 명령 실행 엔진     |
| `hash_map.py`        | 직접 구현한 해시맵   |
| `linked_list.py`     | 이중 연결 리스트    |
| `min_heap.py`        | TTL용 최소 힙    |
| `dynamic_array.py`   | 동적 배열        |
| `pubsub.py`          | Pub/Sub 관리   |
| `binary_tree.py`     | 보너스 이진 트리    |
| `bst.py`             | 보너스 이진 탐색 트리 |
| `test_mini_redis.py` | 기능 테스트       |
| `DATA_STRUCTURES.md` | 자료구조 설명      |
| `IMPLEMENTATION.md`  | 구현 설명        |

README에도 같은 파일 구성이 정리되어 있습니다. 

초심자에게 추천하는 읽는 순서는 이렇습니다.

```text
1. README.md
2. DATA_STRUCTURES.md
3. mini_redis.py
4. linked_list.py
5. hash_map.py
6. min_heap.py
7. pubsub.py
8. test_mini_redis.py
9. bst.py
```

처음부터 `hash_map.py`를 보면 어렵습니다. 먼저 “무슨 프로그램인지”를 보고, 그다음 “왜 이 자료구조가 필요한지”를 본 뒤, 마지막에 코드를 보는 게 좋습니다.

---

# 13. 핵심을 그림 하나로 정리하면

```text
사용자 명령어
  |
  v
MiniRedis
  |
  +-- _store: HashMap
  |      key -> RedisValue(value, lru_node)
  |
  +-- _lru: DoublyLinkedList
  |      head = 최근 사용
  |      tail = 오래 안 씀
  |
  +-- _expirations: HashMap
  |      key -> Expiration(expire_at, version)
  |
  +-- _ttl_heap: MinHeap
  |      가장 빨리 만료될 ExpireRecord가 root
  |
  +-- _pubsub: PubSub
         channel -> subscribers
         subscriber -> message queue
```

즉 이 과제는 단순히 “SET/GET 만들기”가 아닙니다.

**해시맵으로 빨리 찾고, 연결 리스트로 사용 순서를 관리하고, 힙으로 만료 시간을 관리하고, 동적 배열로 내부 저장 공간을 만들고, 큐 개념으로 메시지를 쌓는 과제**입니다.

자료구조 문서도 이 과제의 가장 중요한 연결을 세 가지로 정리합니다.

```text
빠르게 찾기             -> 해시맵
오래 안 쓴 데이터 찾기  -> 이중 연결 리스트와 LRU
가장 빨리 만료될 데이터 찾기 -> 최소 힙
```



---

## 마지막으로, 이 과제에서 꼭 가져가야 할 감각

자료구조를 잘 모르는 사람에게 이 과제를 설명한다면 결론은 이겁니다.

**자료구조는 외우는 게 아니라 “문제를 빨리 해결하기 위해 데이터를 놓는 방식”입니다.**

이 과제에는 여러 문제가 있습니다.

```text
key로 값을 빨리 찾고 싶다.
메모리가 부족하면 오래 안 쓴 것을 지우고 싶다.
시간이 지나면 자동 삭제하고 싶다.
메시지를 순서대로 쌓고 싶다.
정렬된 탐색 구조도 연습하고 싶다.
```

각 문제에 맞는 도구가 붙습니다.

```text
key로 빨리 찾기       -> HashMap
오래 안 쓴 것 찾기    -> DoublyLinkedList + LRU
빨리 만료될 것 찾기   -> MinHeap
필요하면 커지는 저장소 -> DynamicArray
메시지 순서 관리      -> Queue 느낌의 LinkedList
정렬된 탐색 연습      -> BST
```
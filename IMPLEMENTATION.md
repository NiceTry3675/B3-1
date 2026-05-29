# Mini Redis 구현 설명

이 문서는 Mini Redis의 기능이 코드상에서 어떤 방식으로 구현되어 있는지 설명합니다. 사용법은 `README.md`, 면접 답변 관점의 요약은 `INTERVIEW_PREP.md`를 함께 보면 좋습니다.

## 1. 전체 구조

실행 진입점은 `cli.py`입니다. `main()`은 `MiniRedis` 객체를 하나 만들고, 사용자가 입력한 한 줄을 `redis.execute_line(line)`에 넘깁니다.

```text
cli.py
사용자 입력
  -> MiniRedis.execute_line
  -> MiniRedis.execute
  -> _cmd_set / _cmd_get / _cmd_expire ...
  -> 문자열 결과 출력
```

`mini_redis.py`의 `MiniRedis`는 여러 자료구조를 멤버 변수로 가지고 있습니다.

실제 초기화 코드는 아래처럼 되어 있습니다.

```python
class MiniRedis:
    """Command executor for the CLI Mini Redis."""

    def __init__(self, clock=None):
        self._store = HashMap()
        self._expirations = HashMap()
        self._ttl_heap = MinHeap()
        self._lru = DoublyLinkedList()
        self._used_memory = 0
        self._maxmemory = 0
        self._evicted_keys = 0
        self._ttl_version = 0
        self._pubsub = PubSub()
        self._clock = clock if clock is not None else time.time
```

| 필드 | 타입 | 역할 |
| --- | --- | --- |
| `_store` | `HashMap` | 실제 key-value 저장소 |
| `_expirations` | `HashMap` | key별 TTL 메타데이터 저장 |
| `_ttl_heap` | `MinHeap` | 가장 빨리 만료될 TTL 후보 관리 |
| `_lru` | `DoublyLinkedList` | 최근 사용 순서 관리 |
| `_pubsub` | `PubSub` | Pub/Sub 구독자와 메시지 관리 |
| `_used_memory` | `int` | 현재 저장된 key/value 크기 합 |
| `_maxmemory` | `int` | 메모리 제한, 0이면 무제한 |
| `_evicted_keys` | `int` | LRU로 제거된 key 개수 |

## 2. 명령어 파싱과 분기

`MiniRedis.execute_line`은 입력 문자열을 `shlex.split`으로 나눕니다. 그래서 아래 두 입력은 value를 하나의 인자로 처리할 수 있습니다.

```python
def execute_line(self, line):
    try:
        parts = shlex.split(line)
    except ValueError as error:
        return "(error) ERR " + str(error)
    if len(parts) == 0:
        return ""
    return self.execute(parts)
```

```text
SET name Alice
SET name "Alice Kim"
```

파싱에 성공하면 `execute(parts)`가 호출됩니다. `execute`는 첫 번째 토큰을 대문자로 바꾼 뒤 명령어별 메서드로 분기합니다.

```text
SET      -> _cmd_set
GET      -> _cmd_get
DEL      -> _cmd_del
CONFIG   -> _cmd_config
EXPIRE   -> _cmd_expire
PUBLISH  -> _cmd_publish
```

모든 명령은 실제 처리 전에 `_purge_expired()`를 먼저 호출합니다. 그래서 만료 시간이 지난 key는 다음 명령이 들어왔을 때 정리됩니다.

```python
def execute(self, parts):
    command = parts[0].upper()
    self._purge_expired()
    if command == "SET":
        return self._cmd_set(parts)
    if command == "GET":
        return self._cmd_get(parts)
    if command == "DEL":
        return self._cmd_del(parts)
    ...
    return "(error) ERR unknown command '" + command + "'"
```

## 3. String 저장과 조회

실제 데이터는 `_store`에 저장됩니다. `_store`는 직접 구현한 `HashMap`이고, value로는 `RedisValue` 객체가 들어갑니다.

```python
class RedisValue:
    """Stored string value plus its LRU list node."""

    def __init__(self, value, lru_node):
        self.value = value
        self.lru_node = lru_node
```

```text
key -> RedisValue(value, lru_node)
```

`RedisValue`가 `lru_node`를 함께 들고 있는 이유는 LRU 리스트에서 해당 key의 노드를 바로 옮기거나 삭제하기 위해서입니다.

### SET

`_cmd_set(parts)`의 흐름은 다음과 같습니다.

1. 인자 개수가 `SET key value` 형태인지 검사합니다.
2. `_entry_size(key, value)`로 key와 value의 UTF-8 byte 길이 합을 계산합니다.
3. 단일 엔트리가 `maxmemory`보다 크면 저장하지 않고 OOM 에러를 반환합니다.
4. 새 key라면 LRU 리스트 앞쪽에 key를 넣고 `_store`에 저장합니다.
5. 기존 key라면 기존 value 크기를 `used_memory`에서 빼고, 새 value 크기를 더합니다.
6. 기존 key의 LRU 노드를 `move_to_front`로 최신 위치로 옮깁니다.
7. 기존 TTL은 `_expirations.remove(key)`로 삭제합니다.
8. `_evict_if_needed()`로 메모리 초과 여부를 확인합니다.

중요한 점은 `SET`이 단순히 `_store`만 바꾸지 않는다는 것입니다. value, LRU 순서, TTL 정보, 메모리 사용량을 함께 갱신합니다.

실제 `_cmd_set`의 핵심 부분입니다.

```python
def _cmd_set(self, parts):
    if len(parts) != 3:
        return self._wrong_args("SET")
    key = parts[1]
    value = parts[2]
    new_size = self._entry_size(key, value)
    if self._maxmemory > 0 and new_size > self._maxmemory:
        return "(error) OOM command not allowed when used_memory > 'maxmemory'"
    existing = self._store.get(key)
    if existing is None:
        node = self._lru.insert_front(key)
        self._store.put(key, RedisValue(value, node))
        self._used_memory += new_size
    else:
        self._used_memory -= self._entry_size(key, existing.value)
        existing.value = value
        existing.lru_node = self._lru.move_to_front(existing.lru_node)
        self._used_memory += new_size
    self._expirations.remove(key)
    self._evict_if_needed()
    if self._store.get(key) is None:
        return "(error) OOM command not allowed when used_memory > 'maxmemory'"
    return "OK"
```

### GET

`_cmd_get(parts)`의 흐름은 다음과 같습니다.

1. 인자 개수가 `GET key` 형태인지 검사합니다.
2. `_delete_if_expired(key)`로 해당 key가 이미 만료됐는지 확인합니다.
3. 만료됐거나 존재하지 않으면 `(nil)`을 반환합니다.
4. 존재하면 value를 반환하고, 해당 LRU 노드를 `move_to_front`로 이동합니다.

즉 조회에 성공한 key는 “최근 사용한 key”가 됩니다.

```python
def _cmd_get(self, parts):
    if len(parts) != 2:
        return self._wrong_args("GET")
    key = parts[1]
    if self._delete_if_expired(key):
        return "(nil)"
    entry = self._store.get(key)
    if entry is None:
        return "(nil)"
    entry.lru_node = self._lru.move_to_front(entry.lru_node)
    return '"' + entry.value + '"'
```

## 4. 해시맵 구현

`hash_map.py`의 `HashMap`은 Python `dict` 대신 직접 만든 해시맵입니다.

구성은 다음과 같습니다.

```text
DynamicArray buckets
bucket[0] -> DoublyLinkedList(HashEntry, HashEntry, ...)
bucket[1] -> None
bucket[2] -> DoublyLinkedList(HashEntry, ...)
```

key를 저장하거나 찾을 때는 `_hash(key) % _capacity`로 버킷 인덱스를 구합니다. `_hash`는 key를 문자열로 바꾼 뒤 UTF-8 byte를 순회하며 다항식 형태로 값을 누적합니다.

충돌이 발생하면 같은 버킷의 `DoublyLinkedList` 안에 여러 `HashEntry`를 저장합니다. 이 방식을 체이닝이라고 합니다.

`put`은 다음 순서로 동작합니다.

1. key의 버킷 인덱스를 구합니다.
2. 버킷 리스트에서 같은 key가 있는지 찾습니다.
3. 있으면 value만 갱신하고 `False`를 반환합니다.
4. 없으면 새 `HashEntry`를 버킷 뒤에 추가하고 size를 늘립니다.
5. 로드 팩터가 0.75를 넘으면 `_resize`로 capacity를 2배로 늘립니다.

`_resize`가 필요한 이유는 capacity가 바뀌면 같은 key라도 `hash % capacity` 결과가 달라질 수 있기 때문입니다. 그래서 기존 엔트리들을 새 버킷 배열에 다시 넣습니다.

실제 `put` 구현은 버킷 리스트를 순회해 기존 key를 찾고, 없으면 뒤에 새 엔트리를 붙입니다.

```python
def put(self, key, value):
    bucket_index = self._index_for(key)
    bucket = self._bucket_at(bucket_index)
    node = bucket.head
    while node is not None:
        if node.data.key == key:
            node.data.value = value
            return False
        node = node.next
    bucket.insert_back(HashEntry(key, value))
    self._size += 1
    if self._size / self._capacity > 0.75:
        self._resize(self._capacity * 2)
    return True
```

해시 함수와 인덱스 계산은 아래 코드가 담당합니다.

```python
def _index_for(self, key):
    return self._hash(key) % self._capacity

def _hash(self, key):
    """Polynomial rolling hash over UTF-8 bytes."""
    text = str(key)
    result = 0
    multiplier = 31
    data = text.encode("utf-8")
    index = 0
    while index < len(data):
        result = (result * multiplier + data[index]) & 0x7FFFFFFF
        index += 1
    return result
```

## 5. 이중 연결 리스트 구현

`linked_list.py`의 `DoublyLinkedList`는 `head`, `tail`, `_size`를 가지고 있습니다. 각 `Node`는 `prev`, `next`, `data`를 가집니다.

```python
class Node:
    """A node containing prev, next, and data fields."""

    def __init__(self, data):
        self.prev = None
        self.next = None
        self.data = data
```

주요 메서드는 다음과 같습니다.

| 메서드 | 동작 |
| --- | --- |
| `insert_front` | 새 노드를 head 앞에 추가 |
| `insert_back` | 새 노드를 tail 뒤에 추가 |
| `remove_front` | head 노드 제거 |
| `remove_back` | tail 노드 제거 |
| `remove_node` | 전달받은 노드를 리스트에서 제거 |
| `move_to_front` | 전달받은 노드를 제거한 뒤 head에 다시 삽입 |

LRU에서는 이 리스트를 아래처럼 사용합니다.

```text
head                                      tail
가장 최근 사용                          가장 오래 사용하지 않음
[user:3] -> [user:2] -> [user:1]
```

메모리 제한을 초과하면 `_evict_if_needed()`가 `_lru.tail.data`를 읽어서 가장 오래 사용하지 않은 key를 찾고, `_delete_key(key, count_eviction=True)`로 삭제합니다.

LRU 이동에서 가장 중요한 메서드는 `move_to_front`입니다.

```python
def move_to_front(self, node):
    if node is None or node is self.head:
        return node
    data = self.remove_node(node)
    return self.insert_front(data)
```

삭제는 전달받은 노드의 앞뒤 포인터를 직접 연결해 O(1)에 처리합니다.

```python
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
```

## 6. 메모리 제한과 LRU eviction

메모리 계산은 `MiniRedis._entry_size`에서 처리합니다.

```python
def _entry_size(self, key, value):
    return len(str(key).encode("utf-8")) + len(str(value).encode("utf-8"))
```

노드, 포인터, 버킷 배열의 크기는 계산하지 않습니다. 요구사항에서 key와 value의 byte 길이만 계산하도록 했기 때문입니다.

`_evict_if_needed()`는 다음 조건에서 동작합니다.

```text
maxmemory > 0
used_memory > maxmemory
```

조건을 만족하면 LRU 리스트의 tail부터 삭제합니다.

```python
def _evict_if_needed(self):
    if self._maxmemory <= 0:
        return
    while self._used_memory > self._maxmemory and self._lru.tail is not None:
        key = self._lru.tail.data
        self._delete_key(key, count_eviction=True)
```

`_delete_key`는 `_store`, `_expirations`, `_lru`, `_used_memory`를 함께 정리합니다. eviction으로 삭제된 경우에는 `_evicted_keys`도 증가합니다.

```python
def _delete_key(self, key, count_eviction):
    entry = self._store.remove(key)
    if entry is None:
        self._expirations.remove(key)
        return False
    self._used_memory -= self._entry_size(key, entry.value)
    self._lru.remove_node(entry.lru_node)
    self._expirations.remove(key)
    if count_eviction:
        self._evicted_keys += 1
    return True
```

## 7. TTL 구현

TTL 정보는 두 군데에 저장됩니다.

| 저장소 | 저장 내용 | 이유 |
| --- | --- | --- |
| `_expirations` | key -> `Expiration(expire_at, version)` | 특정 key의 현재 TTL 확인 |
| `_ttl_heap` | `ExpireRecord(expire_at, key, version)` | 가장 빨리 만료될 key 찾기 |

`EXPIRE key seconds`는 `_cmd_expire`에서 처리합니다.

1. seconds가 정수인지 검사합니다.
2. key가 없으면 `(integer) 0`을 반환합니다.
3. seconds가 0 이하이면 key를 즉시 삭제하고 `(integer) 1`을 반환합니다.
4. `_ttl_version`을 증가시킵니다.
5. 현재 시간 + seconds를 `expire_at`으로 계산합니다.
6. `_expirations`에 현재 TTL 정보를 저장합니다.
7. `_ttl_heap`에 `ExpireRecord`를 push합니다.

`TTL key`는 `_cmd_ttl`에서 처리합니다.

- key가 없으면 `(integer) -2`
- key는 있지만 TTL이 없으면 `(integer) -1`
- TTL이 있으면 남은 초를 `(integer) N`으로 반환

실제 TTL 메타데이터 클래스입니다.

```python
class Expiration:
    """Current TTL metadata for a key."""

    def __init__(self, expire_at, version):
        self.expire_at = expire_at
        self.version = version
```

`EXPIRE`의 핵심 구현은 현재 TTL version을 증가시키고, 해시맵과 힙에 같은 만료 정보를 넣는 것입니다.

```python
def _cmd_expire(self, parts):
    if len(parts) != 3:
        return self._wrong_args("EXPIRE")
    key = parts[1]
    seconds = self._parse_int(parts[2])
    if seconds is None:
        return "(error) ERR value is not an integer or out of range"
    if self._delete_if_expired(key):
        return "(integer) 0"
    if not self._store.contains(key):
        return "(integer) 0"
    if seconds <= 0:
        self._delete_key(key, count_eviction=False)
        return "(integer) 1"
    self._ttl_version += 1
    expire_at = self._clock() + seconds
    self._expirations.put(key, Expiration(expire_at, self._ttl_version))
    self._ttl_heap.push(ExpireRecord(expire_at, key, self._ttl_version))
    return "(integer) 1"
```

`TTL`은 key 존재 여부와 TTL 존재 여부를 나눠서 Redis 스타일 값을 반환합니다.

```python
def _cmd_ttl(self, parts):
    if len(parts) != 2:
        return self._wrong_args("TTL")
    key = parts[1]
    if self._delete_if_expired(key):
        return "(integer) -2"
    if not self._store.contains(key):
        return "(integer) -2"
    expiration = self._expirations.get(key)
    if expiration is None:
        return "(integer) -1"
    remaining = int(expiration.expire_at - self._clock())
    if remaining < 0:
        self._delete_key(key, count_eviction=False)
        return "(integer) -2"
    return "(integer) " + str(remaining)
```

## 8. 최소 힙과 lazy deletion

`min_heap.py`의 `MinHeap`은 `DynamicArray`를 내부 저장소로 사용합니다. 배열 인덱스 관계는 일반적인 이진 힙과 같습니다.

```text
parent = (index - 1) // 2
left   = index * 2 + 1
right  = index * 2 + 2
```

`push`는 새 값을 배열 끝에 넣고 `_heapify_up`으로 부모와 비교하며 올립니다. `pop`은 root를 꺼낸 뒤 마지막 값을 root로 옮기고 `_heapify_down`으로 자식과 비교하며 내립니다.

TTL에서는 같은 key에 `EXPIRE`가 여러 번 호출될 수 있습니다.

```text
EXPIRE token 10
EXPIRE token 30
```

이때 예전 TTL 레코드를 힙 중간에서 직접 찾아 삭제하지 않습니다. 대신 version을 사용합니다.

```text
ExpireRecord(expire_at=1010, key="token", version=1)
ExpireRecord(expire_at=1030, key="token", version=2)
```

나중에 `_purge_expired`가 힙에서 레코드를 꺼냈을 때, `_expirations`에 저장된 현재 version과 다르면 오래된 레코드로 보고 무시합니다. 이것이 lazy deletion입니다.

힙에 들어가는 레코드는 `expire_at` 기준으로 비교됩니다.

```python
class ExpireRecord:
    """Heap element ordered by expire_at and carrying lazy-deletion version."""

    def __init__(self, expire_at, key, version):
        self.expire_at = expire_at
        self.key = key
        self.version = version

    def __lt__(self, other):
        if self.expire_at == other.expire_at:
            return self.key < other.key
        return self.expire_at < other.expire_at
```

`push`와 `pop`은 전형적인 배열 기반 최소 힙 방식입니다.

```python
def push(self, value):
    self._items.append(value)
    self._heapify_up(self.size() - 1)

def pop(self):
    if self.size() == 0:
        return None
    root = self._items.get(0)
    last = self._items.remove(self.size() - 1)
    if self.size() > 0:
        self._items.set(0, last)
        self._heapify_down(0)
    return root
```

만료 정리는 `MiniRedis._purge_expired`에서 힙의 root를 반복 확인하는 방식입니다.

```python
def _purge_expired(self):
    now = self._clock()
    while self._ttl_heap.size() > 0:
        record = self._ttl_heap.peek()
        if record.expire_at > now:
            break
        self._ttl_heap.pop()
        expiration = self._expirations.get(record.key)
        if expiration is None:
            continue
        if expiration.version == record.version and expiration.expire_at <= now:
            self._delete_key(record.key, count_eviction=False)
```

## 9. Pub/Sub 구현

`pubsub.py`의 `PubSub`은 두 개의 해시맵을 사용합니다.

| 필드 | 저장 내용 |
| --- | --- |
| `_channels` | channel -> subscriber 리스트 |
| `_queues` | subscriber -> 메시지 큐 |

`SUBSCRIBE subscriber channel`은 `_channels`에서 channel의 구독자 리스트를 찾고, 없으면 새 `DoublyLinkedList`를 만듭니다. 이미 같은 subscriber가 있으면 중복 추가하지 않고 `(integer) 0`을 반환합니다.

`PUBLISH channel message`는 channel의 구독자 리스트를 순회하면서 각 subscriber의 메시지 큐 뒤에 `Message(channel, text)`를 추가합니다. 반환값은 메시지를 받은 subscriber 수입니다.

`MESSAGES subscriber`는 해당 subscriber의 메시지 큐를 앞에서부터 출력합니다.

`CLEARMSG subscriber`는 기존 큐를 새 빈 `DoublyLinkedList`로 바꾸고, 삭제한 메시지 개수를 반환합니다.

실제 `subscribe`와 `publish` 구현입니다.

```python
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
```

## 10. 보너스 자료구조 구현

`dynamic_array.py`는 고정 길이 Python list를 내부 저장소로 사용하되, append와 resize 동작을 직접 구현합니다. capacity가 부족하면 `_resize(self._capacity * 2)`로 저장 공간을 2배로 늘립니다.

```python
def append(self, value):
    if self._size >= self._capacity:
        self._resize(self._capacity * 2)
    self._items[self._size] = value
    self._size += 1

def _resize(self, new_capacity):
    new_items = [None] * new_capacity
    index = 0
    while index < self._size:
        new_items[index] = self._items[index]
        index += 1
    self._items = new_items
    self._capacity = new_capacity
```

`binary_tree.py`는 일반 이진 트리 순회를 구현합니다.

- `preorder`: 현재 노드, 왼쪽, 오른쪽
- `inorder`: 왼쪽, 현재 노드, 오른쪽
- `postorder`: 왼쪽, 오른쪽, 현재 노드
- `levelorder`: 큐를 사용해 레벨 순서로 방문

`bst.py`는 이진 탐색 트리입니다. 작은 key는 왼쪽, 큰 key는 오른쪽에 저장합니다. 삭제할 노드에 자식이 둘 있으면 오른쪽 서브트리에서 가장 작은 successor를 찾아 현재 노드에 복사한 뒤 successor를 삭제합니다.

BST 삭제에서 자식이 둘인 노드를 처리하는 부분은 아래 코드입니다.

```python
if node.left is None:
    return True, node.right
if node.right is None:
    return True, node.left
successor = self._min_node(node.right)
node.key = successor.key
node.value = successor.value
_, node.right = self._delete(node.right, successor.key)
return True, node
```

## 11. 테스트 구성

`test_mini_redis.py`는 `unittest`로 작성되어 있습니다.

주요 테스트는 다음을 확인합니다.

- `SET`, `GET`, `CONFIG SET maxmemory`, `INFO memory`가 함께 동작하는지
- 메모리 초과 시 LRU key가 삭제되는지
- `EXPIRE`, `TTL`, 만료 삭제가 동작하는지
- `SET`이 기존 key의 TTL을 삭제하는지
- 잘못된 명령, 인자 오류, 정수 파싱 오류가 Redis 스타일로 출력되는지
- Pub/Sub 메시지가 구독자 큐에 쌓이는지
- BST의 삽입, 탐색, 삭제, 중위 순회가 동작하는지

TTL 테스트에서는 `FakeClock`을 사용합니다. 실제 시간을 기다리지 않고 `clock.advance(seconds)`로 시간을 직접 이동시켜 만료 동작을 검증합니다.

```python
class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
```

예를 들어 TTL 초기화 테스트는 `SET`이 기존 key의 TTL을 지우는지 직접 확인합니다.

```python
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
```

# 스택, 큐, 덱 학습 정리

스택, 큐, 덱은 데이터를 넣고 빼는 위치에 규칙이 있는 선형 자료구조입니다. 세 구조 모두 단순해 보이지만, 실행 취소, 탐색, 메시지 처리, 캐시 제거 정책 같은 실제 기능의 기본 부품으로 자주 쓰입니다.

## 한눈에 비교

| 자료구조 | 제거되는 데이터 | 대표 연산 | 일반적인 시간복잡도 |
| --- | --- | --- | --- |
| 스택 | 마지막에 넣은 데이터 | `push`, `pop`, `peek` | O(1) |
| 큐 | 처음에 넣은 데이터 | `enqueue`, `dequeue`, `peek` | O(1) |
| 덱 | 앞 또는 뒤의 데이터 | `push_front`, `push_back`, `pop_front`, `pop_back` | O(1) |

위 시간복잡도는 연결 리스트나 원형 배열처럼 양 끝 접근에 적합한 방식으로 구현했을 때의 기준입니다. 단순 배열의 앞쪽에서 삭제하면 뒤 원소를 당겨야 하므로 O(N)이 될 수 있습니다.

## 스택

스택은 마지막에 넣은 데이터가 먼저 나오는 LIFO 구조입니다. LIFO는 Last In, First Out의 약자입니다.

```text
push A
push B
push C
pop -> C
pop -> B
```

대표 연산:

- `push`: 맨 위에 데이터를 넣습니다.
- `pop`: 맨 위 데이터를 꺼냅니다.
- `peek`: 맨 위 데이터를 제거하지 않고 확인합니다.

활용 예시:

- 함수 호출 스택
- 괄호 짝 검사
- DFS
- 실행 취소 undo
- 웹 브라우저 뒤로 가기 기록

Mini Redis를 확장한다면 최근 명령 히스토리를 스택으로 저장해 `UNDO` 같은 기능을 만들 수 있습니다. 마지막에 실행한 명령부터 되돌려야 하므로 LIFO 규칙이 잘 맞습니다.

## 큐

큐는 먼저 넣은 데이터가 먼저 나오는 FIFO 구조입니다. FIFO는 First In, First Out의 약자입니다.

```text
enqueue A
enqueue B
enqueue C
dequeue -> A
dequeue -> B
```

대표 연산:

- `enqueue`: 뒤쪽에 데이터를 넣습니다.
- `dequeue`: 앞쪽 데이터를 꺼냅니다.
- `peek`: 앞쪽 데이터를 제거하지 않고 확인합니다.

활용 예시:

- 작업 대기열
- BFS
- 프린터 출력 대기열
- 메시지 처리
- 이벤트 루프의 작업 큐

이 프로젝트의 Pub/Sub 보너스에서는 구독자별 메시지 버퍼를 큐처럼 사용할 수 있습니다. `pubsub.py`는 직접 구현한 `DoublyLinkedList`를 메시지 큐로 재활용합니다. `PUBLISH`가 메시지를 뒤에 넣고, 사용자가 `MESSAGES`로 오래된 메시지부터 확인하는 흐름은 큐의 FIFO 사고방식과 잘 맞습니다.

## 덱

덱은 양쪽 끝에서 삽입과 삭제가 모두 가능한 구조입니다. deque는 double-ended queue의 줄임말입니다.

```text
push_front A
push_back B
push_front C
pop_back -> B
pop_front -> C
```

대표 연산:

- `push_front`: 앞쪽에 데이터를 넣습니다.
- `push_back`: 뒤쪽에 데이터를 넣습니다.
- `pop_front`: 앞쪽 데이터를 꺼냅니다.
- `pop_back`: 뒤쪽 데이터를 꺼냅니다.
- `peek_front`, `peek_back`: 양 끝 데이터를 확인합니다.

활용 예시:

- LRU 캐시
- 양방향 작업 처리
- 슬라이딩 윈도우
- 앞뒤 양쪽에서 작업이 들어오는 대기열

이 프로젝트의 `DoublyLinkedList`는 덱처럼 볼 수 있습니다. 앞쪽과 뒤쪽 삽입/삭제가 모두 가능하고, 노드를 알고 있으면 중간 노드 삭제와 이동도 O(1)에 처리할 수 있습니다.

## Mini Redis에서의 연결

### Pub/Sub 메시지 큐

`pubsub.py`의 `PubSub`은 구독자별 메시지 목록을 `DoublyLinkedList`로 관리합니다.

```text
SUBSCRIBE learner news
PUBLISH news "hello"
PUBLISH news "redis"
MESSAGES learner
```

개념적으로는 아래와 같이 동작합니다.

```text
learner queue: [news: hello] -> [news: redis]
```

메시지는 발행된 순서대로 뒤에 쌓입니다. 그래서 큐처럼 “먼저 들어온 메시지를 먼저 읽는다”는 모델로 이해할 수 있습니다.

### LRU와 덱

LRU는 Least Recently Used의 약자로, 가장 오래 사용되지 않은 key를 먼저 제거하는 정책입니다. Mini Redis에서는 이중 연결 리스트를 다음처럼 사용합니다.

```text
head                                      tail
가장 최근 사용                          가장 오래 사용하지 않음
[user:3] -> [user:2] -> [user:1]
```

`GET user:1`이 성공하면 `user:1`을 head로 이동합니다.

```text
head                                      tail
[user:1] -> [user:3] -> [user:2]
```

메모리 제한을 초과하면 tail의 key부터 삭제합니다. 즉, `remove_back`과 같은 덱 연산으로 가장 오래된 key를 빠르게 제거할 수 있습니다.

## LRU를 배열로 구현하면 어려운 이유

배열로 LRU 순서를 관리할 수도 있지만, 중간 원소를 앞으로 옮기거나 삭제할 때 많은 원소를 밀어야 합니다.

```text
[user:3, user:2, user:1]
GET user:1
```

배열에서는 `user:1`을 앞쪽으로 옮기기 위해 기존 원소들의 위치를 조정해야 하므로 O(N)이 되기 쉽습니다. 반면 이중 연결 리스트는 노드의 `prev`, `next` 포인터만 바꾸면 되므로 O(1)에 이동과 삭제가 가능합니다.

## 해시맵과 함께 써야 하는 이유

이중 연결 리스트만 있으면 오래된 key를 찾고 제거하기는 쉽지만, 특정 key가 리스트 어디에 있는지 찾으려면 처음부터 순회해야 합니다. 이때 해시맵을 함께 사용합니다.

```text
HashMap
user:1 -> RedisValue(value="Alice", lru_node=<node>)

LRU List
head [user:1] -> [user:3] -> [user:2] tail
```

해시맵은 key로 `RedisValue`를 평균 O(1)에 찾고, `RedisValue`는 LRU 리스트의 노드 포인터를 보관합니다. 그래서 `GET`이나 `SET` 성공 시 해당 노드를 바로 앞으로 옮길 수 있습니다.

## 정리

- 스택은 “마지막 작업부터 처리”할 때 좋습니다.
- 큐는 “먼저 온 작업부터 처리”할 때 좋습니다.
- 덱은 “양쪽 끝을 모두 빠르게 다뤄야 할 때” 좋습니다.
- Mini Redis의 Pub/Sub 메시지 버퍼는 큐처럼 이해할 수 있습니다.
- Mini Redis의 LRU 리스트는 덱처럼 동작하며, 해시맵과 결합해 평균 O(1) 갱신을 가능하게 합니다.

# 온라인 상태 관리 시스템 (Online Presence System)

## 개요

이 시스템은 **SSE (Server-Sent Events) + Redis Pub/Sub**을 사용하여 실시간으로 사용자의 온라인 상태를 추적하고 친구들에게 브로드캐스트합니다.

## 아키텍처

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  Client A   │         │   Server    │         │    Redis    │
│             │         │             │         │             │
│  1. 로그인   ├────────>│ set_online()├────────>│  SET key    │
│             │         │             │         │  PUBLISH    │
│             │         │             │         │             │
│  2. SSE연결  ├────────>│ /presence/  │         │             │
│             │<────────┤  stream     │         │             │
│             │  events │             │         │             │
│             │         │      ▲      │         │             │
│             │         │      │      │         │      │      │
│             │         │  SUBSCRIBE  │<────────┘  PUB/SUB   │
│             │         │      │      │            messages  │
│  3. 친구    │         │      │      │                      │
│  상태 수신   │<────────┤  Broadcast  │                      │
│             │         │             │                      │
└─────────────┘         └─────────────┘         └─────────────┘

┌─────────────┐
│  Client B   │
│  (친구)     │
│  로그인     ├────> set_online() ────> PUBLISH ────> Client A에게
│             │                                        상태 변화 전송
└─────────────┘
```

## 핵심 컴포넌트

### 1. Redis 상태 저장

**키 구조:**
```
user:online:{user_id}     - 온라인 상태 (TTL: 5분)
user:last_seen:{user_id}  - 마지막 접속 시간 (TTL: 7일)
online_users              - 온라인 유저 Set
user:websocket:{user_id}  - WebSocket 세션 (선택)
```

**Pub/Sub 채널:**
```
user:status:{user_id}     - 특정 유저의 상태 변화
presence:broadcast        - 전체 브로드캐스트
```

### 2. API 엔드포인트

#### SSE 스트림 (실시간 업데이트)
```
GET /api/presence/stream
Authorization: Bearer {token}
또는
GET /api/presence/stream?token={token}
```

**이벤트 타입:**
- `connected`: 연결 성공
- `initial`: 초기 친구 목록 상태
- `status_change`: 친구의 상태 변화
- `heartbeat`: 30초마다 연결 유지

#### REST API (상태 조회)
```
# 여러 유저 상태 조회
POST /api/online-status/users
Body: {"user_ids": [1, 2, 3, 4, 5]}

# 단일 유저 상태 조회
GET /api/online-status/user/{user_id}

# 친구 목록 상태 조회
GET /api/online-status/friends

# 수동 Heartbeat
POST /api/online-status/heartbeat
```

### 3. 상태 변경 흐름

#### 로그인 시
```python
# app/api/auth.py
async def login():
    # 1. 토큰 생성
    access_token = create_access_token(...)

    # 2. Redis에 온라인 상태 저장
    await set_online(user.id, session_id=f"login_{user.id}_{access_token[:10]}")

    # 3. Redis Pub/Sub 브로드캐스트 (자동)
    # -> user:status:{user_id} 채널에 메시지 발행
```

#### SSE 연결 시
```python
# app/api/presence.py
async def presence_stream():
    # 1. 친구 목록 조회
    friends = await FriendshipService.get_friends_list(db, current_user.id)
    friend_ids = [friend.id for friend, _ in friends]

    # 2. Redis Pub/Sub 채널 구독
    channels = [f"user:status:{friend_id}" for friend_id in friend_ids]
    await pubsub.subscribe(*channels)

    # 3. 초기 상태 전송
    initial_statuses = await get_users_status(friend_ids)
    yield f"event: initial\ndata: {json.dumps(initial_statuses)}\n\n"

    # 4. 상태 변화 수신 및 전송
    while True:
        message = await pubsub.get_message()
        if message:
            yield f"event: status_change\ndata: {message['data']}\n\n"
```

#### 자동 Heartbeat
```python
# app/api/auth.py
async def get_current_user(token):
    # 모든 인증된 API 요청마다 자동 실행
    user = await verify_token(token)

    # 활동 시간 업데이트 (TTL 연장)
    await update_activity(user.id)

    return user
```

#### 로그아웃 시
```python
# app/api/auth.py
async def logout():
    # 1. Redis에서 온라인 상태 제거
    await set_offline(current_user.id)

    # 2. Redis Pub/Sub 브로드캐스트 (자동)
    # -> user:status:{user_id} 채널에 오프라인 메시지 발행
```

## 클라이언트 통합

### React 예시

```typescript
import { useEffect, useState } from 'react';
import { EventSourcePolyfill } from 'event-source-polyfill';

function usePresence(accessToken: string) {
  const [friendStatuses, setFriendStatuses] = useState({});
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const eventSource = new EventSourcePolyfill(
      'http://localhost:8000/api/presence/stream',
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      }
    );

    eventSource.addEventListener('connected', (e) => {
      console.log('Connected:', e.data);
      setIsConnected(true);
    });

    eventSource.addEventListener('initial', (e) => {
      const statuses = JSON.parse(e.data);
      setFriendStatuses(statuses);
    });

    eventSource.addEventListener('status_change', (e) => {
      const change = JSON.parse(e.data);
      setFriendStatuses(prev => ({
        ...prev,
        [change.user_id]: change
      }));
    });

    return () => eventSource.close();
  }, [accessToken]);

  return { friendStatuses, isConnected };
}
```

### 일반 REST API 조회 (SSE 없이)

```javascript
// 친구 목록 조회
const friends = await fetch('/api/friends/list', {
  headers: { 'Authorization': `Bearer ${token}` }
}).then(r => r.json());

// 친구들의 온라인 상태 조회
const friendIds = friends.map(f => f.user_id);
const statuses = await fetch('/api/online-status/users', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ user_ids: friendIds })
}).then(r => r.json());

console.log(statuses);
// {
//   "1": {"is_online": true, "last_activity": "2024-01-21T10:30:00"},
//   "2": {"is_online": false, "last_seen": "2024-01-21T09:00:00"}
// }
```

## 성능 최적화

### 1. TTL 기반 자동 만료
- 5분간 활동 없으면 자동 오프라인 처리
- 별도의 정리 작업 불필요

### 2. Redis Pipeline 사용
```python
pipe = redis.pipeline()
pipe.setex(...)
pipe.sadd(...)
pipe.publish(...)
await pipe.execute()
```

### 3. Batch 조회
```python
# 한 번에 여러 유저 상태 조회
statuses = await get_users_status([1, 2, 3, 4, 5])
```

## 확장성

### 다중 서버 인스턴스

Redis Pub/Sub 덕분에 여러 서버가 동시에 실행되어도 상태 동기화가 자동으로 이루어집니다:

```
┌─────────┐         ┌─────────┐
│Server 1 │         │Server 2 │
│         │         │         │
│  SSE ───┼────┐    │  SSE ───┼────┐
└─────────┘    │    └─────────┘    │
               ▼                    ▼
            ┌────────────────────────┐
            │    Redis Pub/Sub       │
            │                        │
            │  user:status:123       │
            │  {"is_online": true}   │
            └────────────────────────┘
```

## WebSocket과의 비교

| 특징 | SSE | WebSocket |
|------|-----|-----------|
| 방향성 | 단방향 (서버→클라이언트) | 양방향 |
| 프로토콜 | HTTP/1.1, HTTP/2 | WebSocket Protocol |
| 재연결 | 자동 | 수동 구현 필요 |
| 방화벽 통과 | 쉬움 (HTTP) | 어려울 수 있음 |
| 브라우저 지원 | 대부분 | 대부분 |
| 서버 부하 | 낮음 | 중간 |
| 구현 복잡도 | 낮음 | 높음 |
| 최적 사용처 | 상태 업데이트, 알림 | 채팅, 게임 |

**온라인 상태 관리에 SSE가 적합한 이유:**
- 서버에서 클라이언트로만 상태를 전달하면 됨 (단방향)
- 자동 재연결로 안정적
- HTTP 기반이라 프록시/방화벽 통과 용이
- 구현이 간단하고 유지보수 쉬움

## 모니터링

### Redis 명령어로 상태 확인

```bash
# 온라인 유저 수
redis-cli SCARD online_users

# 온라인 유저 목록
redis-cli SMEMBERS online_users

# 특정 유저 상태
redis-cli GET user:online:123

# Pub/Sub 채널 모니터링
redis-cli SUBSCRIBE user:status:*
```

### API로 확인

```bash
# 온라인 유저 수
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/online-status/count

# 온라인 유저 목록
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/online-status/online
```

## 문제 해결

### SSE 연결이 자주 끊김

**원인:** Nginx 등 리버스 프록시의 버퍼링

**해결:**
```nginx
location /api/presence/stream {
    proxy_pass http://backend;
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
}
```

### CORS 에러

**해결:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### EventSource가 헤더를 지원하지 않음

**해결 1:** 쿼리 파라미터 사용
```javascript
const eventSource = new EventSource(
  `http://localhost:8000/api/presence/stream?token=${token}`
);
```

**해결 2:** EventSource Polyfill 사용
```bash
npm install event-source-polyfill
```

```javascript
import { EventSourcePolyfill } from 'event-source-polyfill';

const eventSource = new EventSourcePolyfill(
  'http://localhost:8000/api/presence/stream',
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);
```

## 테스트

### 단위 테스트

```python
import pytest
from app.services.online_status_service import set_online, set_offline, get_user_status

@pytest.mark.asyncio
async def test_set_online():
    # 온라인 설정
    result = await set_online(user_id=1, session_id="test_session")
    assert result is True

    # 상태 확인
    status = await get_user_status(1)
    assert status["is_online"] is True
    assert status["session_id"] == "test_session"

@pytest.mark.asyncio
async def test_set_offline():
    await set_online(user_id=1)

    # 오프라인 설정
    result = await set_offline(user_id=1)
    assert result is True

    # 상태 확인
    status = await get_user_status(1)
    assert status["is_online"] is False
```

### 통합 테스트

```bash
# 1. 로그인
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login/json \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}' \
  | jq -r '.access_token')

# 2. SSE 연결
curl -N -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/presence/stream

# 3. 다른 터미널에서 친구 로그인
# -> SSE 스트림에 status_change 이벤트 수신
```

## 향후 개선사항

1. **타이핑 인디케이터**: 친구가 메시지 작성 중인지 표시
2. **마지막 접속 시간 표시**: "5분 전", "1시간 전" 등
3. **커스텀 상태**: "자리비움", "회의중", "방해금지" 등
4. **모바일 푸시**: 오프라인일 때 푸시 알림
5. **위치 기반 상태**: "근처에 있음" 등

## 관련 파일

- `app/api/presence.py` - SSE 스트림 엔드포인트
- `app/api/online_status.py` - REST API 엔드포인트
- `app/services/online_status_service.py` - 비즈니스 로직
- `app/api/auth.py` - 로그인/로그아웃 시 상태 관리
- `docs/presence_client_example.md` - 클라이언트 예시 코드

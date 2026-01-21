# 온라인 상태 관리 클라이언트 예시

## SSE + Redis Pub/Sub 방식

이 시스템은 **Server-Sent Events (SSE)**와 **Redis Pub/Sub**을 사용하여 실시간으로 친구들의 온라인 상태를 추적합니다.

## 아키텍처 개요

```
클라이언트                    서버                    Redis
    │                         │                       │
    ├─ 1. 로그인 ────────────>│                       │
    │  POST /auth/login       │                       │
    │<─────── token ──────────┤                       │
    │                         │                       │
    ├─ 2. SSE 연결 ──────────>│                       │
    │  GET /presence/stream   │                       │
    │  (with token)           ├─ set_online() ───────>│
    │                         │                       │
    │<─ connected event ──────┤                       │
    │<─ initial statuses ─────┤                       │
    │                         │                       │
    │  [친구가 온라인 됨]       │                       │
    │                         │<─ Pub/Sub message ────┤
    │<─ status_change ────────┤                       │
    │                         │                       │
    │  [30초마다 heartbeat]    │                       │
    │<─ heartbeat ────────────┤                       │
    │                         ├─ update_activity() ──>│
    │                         │                       │
    │  [연결 종료]             │                       │
    │  Close connection       ├─ set_offline() ──────>│
    └─────────────────────────┴───────────────────────┘
```

## JavaScript/TypeScript 클라이언트

### React 예시 (Hooks)

```typescript
import { useEffect, useState, useRef } from 'react';

interface FriendStatus {
  user_id: number;
  is_online: boolean;
  last_activity?: string;
  last_seen?: string;
}

interface PresenceState {
  [userId: number]: FriendStatus;
}

export function usePresence(token: string) {
  const [presenceState, setPresenceState] = useState<PresenceState>({});
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!token) return;

    // SSE 연결 생성
    const eventSource = new EventSource(
      `http://localhost:8000/api/presence/stream`,
      {
        // Note: EventSource 표준은 헤더를 지원하지 않음
        // 따라서 토큰을 쿼리 파라미터로 전달하거나
        // 쿠키 인증을 사용해야 함
      }
    );

    eventSourceRef.current = eventSource;

    // 연결 성공 이벤트
    eventSource.addEventListener('connected', (event) => {
      console.log('Presence stream connected:', event.data);
      setIsConnected(true);
    });

    // 초기 친구 목록 상태
    eventSource.addEventListener('initial', (event) => {
      const statuses: PresenceState = JSON.parse(event.data);
      console.log('Initial friend statuses:', statuses);
      setPresenceState(statuses);
    });

    // 친구 상태 변화
    eventSource.addEventListener('status_change', (event) => {
      const change = JSON.parse(event.data);
      console.log('Friend status changed:', change);

      setPresenceState((prev) => ({
        ...prev,
        [change.user_id]: change
      }));
    });

    // Heartbeat
    eventSource.addEventListener('heartbeat', (event) => {
      const data = JSON.parse(event.data);
      console.log('Heartbeat received:', data.timestamp);
    });

    // 에러 처리
    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      setIsConnected(false);

      // 자동 재연결 (EventSource가 자동으로 처리)
      if (eventSource.readyState === EventSource.CLOSED) {
        console.log('Connection closed, will retry...');
      }
    };

    // 정리 함수
    return () => {
      console.log('Closing presence stream');
      eventSource.close();
      setIsConnected(false);
    };
  }, [token]);

  return {
    presenceState,
    isConnected,
    disconnect: () => eventSourceRef.current?.close()
  };
}

// 사용 예시
function FriendsList() {
  const { token } = useAuth(); // 로그인 토큰
  const { presenceState, isConnected } = usePresence(token);

  return (
    <div>
      <h2>Friends {isConnected ? '🟢' : '🔴'}</h2>
      {Object.values(presenceState).map((friend) => (
        <div key={friend.user_id}>
          {friend.user_id} - {friend.is_online ? '온라인' : '오프라인'}
          {friend.last_activity && ` (${friend.last_activity})`}
        </div>
      ))}
    </div>
  );
}
```

### 토큰 인증 문제 해결

EventSource는 기본적으로 커스텀 헤더를 지원하지 않으므로, 다음 방법 중 하나를 사용해야 합니다:

#### 방법 1: 쿼리 파라미터로 토큰 전달 (간단)

```typescript
const eventSource = new EventSource(
  `http://localhost:8000/api/presence/stream?token=${token}`
);
```

이 경우 서버 코드를 다음과 같이 수정:

```python
@router.get("/stream")
async def presence_stream(
    request: Request,
    token: str = Query(...),  # 쿼리 파라미터로 받기
    db: AsyncSession = Depends(get_async_session)
):
    # 토큰 검증
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = int(payload.get("sub"))
    user = await auth_service.find_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # ... 나머지 로직
```

#### 방법 2: EventSource 폴리필 사용 (권장)

```bash
npm install event-source-polyfill
```

```typescript
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

## Vanilla JavaScript 예시

```javascript
class PresenceManager {
  constructor(token) {
    this.token = token;
    this.eventSource = null;
    this.presenceState = {};
    this.listeners = [];
  }

  connect() {
    // EventSource 생성
    this.eventSource = new EventSource(
      `http://localhost:8000/api/presence/stream?token=${this.token}`
    );

    // 이벤트 리스너 등록
    this.eventSource.addEventListener('connected', (event) => {
      console.log('Connected:', event.data);
      this.notifyListeners('connected', JSON.parse(event.data));
    });

    this.eventSource.addEventListener('initial', (event) => {
      this.presenceState = JSON.parse(event.data);
      this.notifyListeners('initial', this.presenceState);
    });

    this.eventSource.addEventListener('status_change', (event) => {
      const change = JSON.parse(event.data);
      this.presenceState[change.user_id] = change;
      this.notifyListeners('status_change', change);
    });

    this.eventSource.addEventListener('heartbeat', (event) => {
      console.log('Heartbeat:', event.data);
    });

    this.eventSource.onerror = (error) => {
      console.error('Connection error:', error);
      this.notifyListeners('error', error);
    };
  }

  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  onPresenceChange(callback) {
    this.listeners.push(callback);
  }

  notifyListeners(event, data) {
    this.listeners.forEach(callback => callback(event, data));
  }

  getStatus(userId) {
    return this.presenceState[userId] || null;
  }

  getAllStatuses() {
    return this.presenceState;
  }
}

// 사용 예시
const presenceManager = new PresenceManager(accessToken);

presenceManager.onPresenceChange((event, data) => {
  if (event === 'status_change') {
    console.log(`User ${data.user_id} is now ${data.is_online ? 'online' : 'offline'}`);
    updateUI(data);
  }
});

presenceManager.connect();

// 페이지 종료 시 연결 해제
window.addEventListener('beforeunload', () => {
  presenceManager.disconnect();
});
```

## Flutter/Dart 클라이언트

```dart
import 'package:http/http.dart' as http;
import 'dart:async';
import 'dart:convert';

class PresenceManager {
  final String token;
  final String baseUrl;

  http.Client? _client;
  StreamController<Map<String, dynamic>>? _controller;

  PresenceManager(this.token, this.baseUrl);

  Stream<Map<String, dynamic>> get presenceStream {
    if (_controller == null) {
      _controller = StreamController<Map<String, dynamic>>();
      _connect();
    }
    return _controller!.stream;
  }

  Future<void> _connect() async {
    _client = http.Client();

    final request = http.Request(
      'GET',
      Uri.parse('$baseUrl/api/presence/stream'),
    );
    request.headers['Authorization'] = 'Bearer $token';
    request.headers['Accept'] = 'text/event-stream';

    final response = await _client!.send(request);

    response.stream
        .transform(utf8.decoder)
        .transform(LineSplitter())
        .listen(
      (line) {
        if (line.startsWith('event:')) {
          final event = line.substring(7).trim();
          // 다음 라인이 data
        } else if (line.startsWith('data:')) {
          final data = line.substring(6).trim();
          _controller!.add(json.decode(data));
        }
      },
      onError: (error) {
        print('SSE error: $error');
        _controller!.addError(error);
      },
      onDone: () {
        print('SSE connection closed');
        _controller!.close();
      },
    );
  }

  void disconnect() {
    _client?.close();
    _controller?.close();
  }
}

// 사용 예시
final presenceManager = PresenceManager(accessToken, 'http://localhost:8000');

presenceManager.presenceStream.listen((data) {
  print('Presence update: $data');
});
```

## 주요 특징

### 1. 자동 재연결
EventSource는 연결이 끊어지면 자동으로 재연결을 시도합니다.

### 2. 낮은 오버헤드
WebSocket보다 단순하며, HTTP/1.1 기반이므로 프록시/방화벽 통과가 용이합니다.

### 3. 확장성
Redis Pub/Sub를 사용하므로 여러 서버 인스턴스에서 동작 가능합니다.

## 테스트

### cURL로 테스트

```bash
# 로그인
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login/json \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}' \
  | jq -r '.access_token')

# SSE 스트림 연결 (쿼리 파라미터 방식)
curl -N -H "Accept: text/event-stream" \
  "http://localhost:8000/api/presence/stream?token=$TOKEN"
```

### 브라우저 콘솔에서 테스트

```javascript
// 1. 로그인
const response = await fetch('http://localhost:8000/api/auth/login/json', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'password'
  })
});
const { access_token } = await response.json();

// 2. SSE 연결
const eventSource = new EventSource(
  `http://localhost:8000/api/presence/stream?token=${access_token}`
);

eventSource.addEventListener('initial', (e) => {
  console.log('Initial statuses:', JSON.parse(e.data));
});

eventSource.addEventListener('status_change', (e) => {
  console.log('Status changed:', JSON.parse(e.data));
});
```

## 성능 고려사항

1. **연결 수 제한**: 브라우저는 도메인당 최대 6개의 SSE 연결만 허용
2. **Heartbeat**: 30초마다 heartbeat로 연결 유지
3. **메모리**: 클라이언트는 모든 친구의 상태를 메모리에 유지
4. **네트워크**: SSE는 단방향이므로 WebSocket보다 대역폭 효율적

## 문제 해결

### CORS 에러
서버의 CORS 설정 확인:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 연결이 자주 끊김
Nginx 등 리버스 프록시 사용 시 버퍼링 비활성화:
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

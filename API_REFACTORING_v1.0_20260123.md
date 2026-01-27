# API 분석 및 개선 문서 v1.0

**작성일**: 2026-01-23
**프로젝트**: bigtech_chat-be
**목적**: MVP 단계 API 정리 및 최적화

---

## 📋 목차

1. [개요](#개요)
2. [auth API](#auth-api)
3. [friends API](#friends-api)
4. [profile API](#profile-api)
5. [health API](#health-api)
6. [online_status API](#online_status-api)
7. [온라인 상태 관리 시스템](#온라인-상태-관리-시스템)
8. [변경 사항 요약](#변경-사항-요약)

---

## 개요

### 목표
- 불필요한 엔드포인트 제거
- 중복 기능 정리
- 실시간 온라인 상태 시스템 구축
- MySQL과 Redis 하이브리드 상태 관리

### 주요 변경 사항
- **로그인/로그아웃 시 MySQL DB 동기화 추가**
- **친구 목록에 상대적 시간 표기 추가** (예: "30분 전")
- **SSE 기반 실시간 온라인 상태 스트리밍 구현**
- **Heartbeat 타임아웃 자동 감지 및 처리**

---

## auth API

### 엔드포인트 현황

#### ✅ 유지된 엔드포인트

1. **POST /auth/register** (회원가입)
   - 새로운 사용자 계정 생성
   - 이메일/사용자명 중복 검증
   - 비밀번호 해싱

2. **POST /auth/login/json** (JSON 로그인) ⭐
   - 실제 클라이언트 앱용 로그인
   - `application/json` 형식
   - JWT 토큰 발급
   - **개선**: Redis + MySQL 모두에 온라인 상태 저장

3. **POST /auth/login** (OAuth2 로그인)
   - Swagger UI 테스트용
   - `application/x-www-form-urlencoded` 형식
   - **개선**: Redis + MySQL 모두에 온라인 상태 저장

4. **POST /auth/logout** (로그아웃) ⭐
   - 사용자 로그아웃 처리
   - **개선**: MySQL DB에 오프라인 상태 및 `last_seen_at` 자동 업데이트

5. **get_current_user** (의존성 함수)
   - JWT 토큰 검증 및 사용자 조회
   - 다른 API에서 인증용으로 사용

6. **get_optional_user** (의존성 함수)
   - 선택적 인증 (토큰 없어도 허용)

### 주요 개선 사항

#### 1. 로그인 시 MySQL 동기화 추가
```python
# 로그인 시 (login_oauth2, login_json)
await set_online(user.id, session_id=...)  # Redis
await auth_service.update_online_status(db, user.id, is_online=True)  # MySQL ✅
```

#### 2. 로그아웃 시 last_seen_at 자동 업데이트
```python
# 로그아웃 시
await set_offline(current_user.id)  # Redis
await auth_service.update_online_status(db, current_user.id, is_online=False)  # MySQL ✅
# → is_online = False, last_seen_at = datetime.utcnow() 자동 업데이트
```

**파일**: `app/api/auth.py`

---

## friends API

### 엔드포인트 현황

#### ✅ 유지된 엔드포인트 (6개)

1. **POST /friends/request** (친구 요청 전송)
   - 다른 사용자에게 친구 요청
   - 자기 자신/중복 요청 방지

2. **PUT /friends/status/{requester_user_id}** (친구 요청 수락/거절) ⭐
   - **변경**: `friendship_id` → `requester_user_id` 파라미터로 변경
   - Body: `{"action": "accept"}` 또는 `{"action": "reject"}`
   - 더 직관적인 API 설계

3. **GET /friends/list** (친구 목록 조회) ⭐
   - **개선**: `friendship_created_at` → `last_seen_at` + `last_seen_display`
   - 상대적 시간 표기 (예: "방금전", "30분 전", "2시간 전", "3일 전")

4. **GET /friends/requests** (친구 요청 목록)
   - 받은 요청/보낸 요청 분리 조회

5. **DELETE /friends/request/{target_user_id}** (친구 요청 취소)
   - 자신이 보낸 pending 요청 취소

6. **GET /friends/search** (친구 추가용 사용자 검색)
   - 최소 3글자 이상 검색
   - 이미 친구/차단된 사용자 자동 제외

### 주요 개선 사항

#### 1. 친구 요청 API 파라미터 변경
**변경 전:**
```
PUT /friends/{friendship_id}/status
```

**변경 후:**
```
PUT /friends/status/{requester_user_id}
Body: {"action": "accept"}
```

**이유**:
- 클라이언트는 보통 friendship_id를 모름
- 요청을 보낸 사용자 ID는 쉽게 알 수 있음
- 더 직관적인 API 설계

#### 2. 친구 목록에 상대적 시간 표기 추가

**변경 전 응답:**
```json
{
  "user_id": 123,
  "username": "john_doe",
  "email": "john@example.com",
  "friendship_created_at": "2026-01-20T10:00:00"
}
```

**변경 후 응답:**
```json
{
  "user_id": 123,
  "username": "john_doe",
  "email": "john@example.com",
  "last_seen_at": "2026-01-23T09:30:00",
  "last_seen_display": "30분 전"
}
```

**시간 표기 규칙** (`app/utils/time_utils.py`):
- 5분 이내: "방금전"
- 5분~59분: "n분 전"
- 1시간~23시간: "n시간 전"
- 1일 이상: "n일 전"

#### 3. 서비스 레이어 메서드 추가

**새로운 메서드** (`app/services/friendship_service.py`):
- `accept_friend_request_by_requester()` - 요청자 ID로 수락
- `reject_friend_request_by_requester()` - 요청자 ID로 거절

**파일**: `app/api/friend.py`, `app/services/friendship_service.py`, `app/schemas/friendship.py`

---

## profile API

### 엔드포인트 현황

#### ✅ 유지된 엔드포인트 (5개)

1. **GET /profile/me** (내 프로필 조회)
2. **GET /profile/{user_id}** (다른 사용자 프로필 조회)
3. **PUT /profile/me** (프로필 수정)
4. **POST /profile/me/image** (프로필 이미지 업로드)
5. **DELETE /profile/me/image** (프로필 이미지 삭제)

#### ❌ 제거된 엔드포인트 (2개)

1. **PUT /profile/status** (온라인 상태 수동 업데이트)
   - **제거 이유**: 로그인/로그아웃에서 자동 관리됨

2. **POST /profile/last-seen** (마지막 접속 시간 수동 업데이트)
   - **제거 이유**: 로그아웃 및 heartbeat 타임아웃 시 자동 업데이트됨

### 변경 사항
- 중복/불필요한 수동 상태 관리 엔드포인트 제거
- 자동화된 상태 관리로 대체

**파일**: `app/api/profile.py`

---

## health API

### 엔드포인트 현황

#### ✅ 모든 엔드포인트 유지 (5개)

1. **GET /health** (전체 헬스 체크)
   - MySQL, MongoDB, Redis 연결 상태

2. **GET /health/ready** (Readiness Probe)
   - Kubernetes용 트래픽 라우팅 결정

3. **GET /health/live** (Liveness Probe)
   - Kubernetes용 컨테이너 재시작 결정

4. **GET /health/redis** (Redis 상세 상태)
   - 관리자용 디버깅

5. **POST /health/redis/test** (Redis 동작 테스트)
   - 개발자용 테스트

### 평가
- 잘 설계되어 있으며 향후 Kubernetes 배포 시 필수
- 모든 엔드포인트 유지

**파일**: `app/api/health.py`

---

## online_status API

### 엔드포인트 현황

#### ✅ 최종 엔드포인트 (4개)

1. **GET /online-status/user/{user_id}** (특정 사용자 온라인 상태)
   - Redis에서 실시간 상태 조회
   ```json
   {
     "user_id": 123,
     "status": "online",
     "is_online": true,
     "last_activity": "2026-01-23T10:00:00"
   }
   ```

2. **POST /online-status/heartbeat** (하트비트) ⭐
   - 클라이언트가 30초마다 호출
   - Redis TTL 연장 (5분)
   - 온라인 상태 유지

3. **GET /online-status/friends** (친구들 온라인 상태) ⭐
   - accepted 상태의 친구만 조회
   - **간소화된 응답**: `user_id`, `is_online`만 포함
   ```json
   [
     {"user_id": 456, "is_online": true},
     {"user_id": 789, "is_online": false}
   ]
   ```

4. **GET /online-status/stream** (SSE 실시간 스트리밍) ⭐ 신규
   - Server-Sent Events 기반
   - Redis Pub/Sub 구독
   - 친구들의 온라인 상태 변화를 실시간으로 푸시

#### ❌ 제거된 엔드포인트 (6개)

1. **GET /online-status/users** (전체 온라인 사용자 목록)
   - **제거 이유**: 확장성 문제 (사용자 많아지면 부하)

2. **GET /online-status/count** (온라인 사용자 수)
   - **제거 이유**: 불필요

3. **POST /online-status/set-online** (수동 온라인 설정)
   - **제거 이유**: 로그인 시 자동 처리

4. **POST /online-status/set-offline** (수동 오프라인 설정)
   - **제거 이유**: 로그아웃 시 자동 처리

5. **GET /online-status/cleanup** (만료 사용자 정리)
   - **제거 이유**: HeartbeatMonitor가 자동 처리

6. **POST /online-status/users** (여러 사용자 상태 일괄 조회)
   - **제거 이유**: SSE 스트리밍으로 대체

### 주요 개선 사항

#### 1. SSE 실시간 스트리밍 구현

**특징**:
- Redis Pub/Sub 기반 실시간 이벤트 전송
- 친구 목록 자동 구독
- 초기 상태 + 실시간 변화 모두 전송

**React 사용 예시**:
```javascript
const eventSource = new EventSource('/api/online-status/stream?token=...');

eventSource.addEventListener('status', (event) => {
  const data = JSON.parse(event.data);
  // { user_id: 123, is_online: true }
  updateFriendStatus(data.user_id, data.is_online);
});
```

**이벤트 타입**:
- `connected`: 연결 성공
- `status`: 친구 온라인 상태 변화
- `error`: 에러 발생

#### 2. 친구 온라인 상태 응답 간소화

**변경 전**:
```json
{
  "user_id": 456,
  "username": "john_doe",
  "display_name": "John",
  "profile_image_url": "...",
  "status": "online",
  "is_online": true,
  "last_activity": "...",
  "last_seen": "..."
}
```

**변경 후**:
```json
{
  "user_id": 456,
  "is_online": true
}
```

**이유**:
- 친구 상세 정보는 `/friends/list`에서 이미 제공
- 온라인 상태 조회는 가볍게 유지
- 응답 크기 감소, 성능 향상

**파일**: `app/api/online_status.py`

---

## 온라인 상태 관리 시스템

### 아키텍처

#### Redis + MySQL 하이브리드 구조

| 항목 | Redis | MySQL |
|------|-------|-------|
| **역할** | 실시간 상태 관리 | 영구 저장 및 백업 |
| **업데이트** | 로그인/heartbeat | 로그인/로그아웃/타임아웃 |
| **TTL** | 5분 (자동 만료) | 영구 저장 |
| **조회** | 모든 상태 조회 API | 프로필 조회 시 |
| **Pub/Sub** | ✅ 실시간 브로드캐스트 | ❌ |

### 전체 흐름

```
1. 로그인
   POST /auth/login
   ↓
   Redis: user:online:{user_id} (TTL 5분) ✅
   MySQL: is_online = true ✅
   Pub/Sub: {"user_id": 1, "is_online": true} ✅
   ↓
   SSE 구독자들에게 실시간 전송

2. Heartbeat (30초마다)
   POST /online-status/heartbeat
   ↓
   Redis: TTL 연장 (5분) ✅

3. 정상 로그아웃
   POST /auth/logout
   ↓
   Redis: user:online:{user_id} 삭제 ✅
   MySQL: is_online = false, last_seen_at = now ✅
   Pub/Sub: {"user_id": 1, "is_online": false} ✅
   ↓
   SSE 구독자들에게 실시간 전송

4. Heartbeat 타임아웃 (5분 경과, 신규) ⭐
   HeartbeatMonitor가 Redis Keyspace Notification 감지
   ↓
   Redis: user:online:{user_id} 자동 만료 ✅
   MySQL: is_online = false, last_seen_at = now ✅
   Pub/Sub: {"user_id": 1, "is_online": false} ✅
   ↓
   SSE 구독자들에게 실시간 전송
```

### Heartbeat 모니터링 시스템 ⭐ 신규

**파일**: `app/services/heartbeat_monitor.py`

**기능**:
- Redis Keyspace Notifications 활용
- `user:online:{user_id}` 키의 TTL 만료 자동 감지
- 만료 시 자동 처리:
  1. Redis 온라인 집합에서 제거
  2. Redis `last_seen` 업데이트
  3. **MySQL `is_online`, `last_seen_at` 업데이트** ✅
  4. Pub/Sub 오프라인 상태 브로드캐스트

**시작**:
- `app/main.py`의 `lifespan` 이벤트에서 자동 시작
- 애플리케이션 종료 시 자동 중지

**Redis 설정 (자동 활성화)**:
```python
await redis.config_set('notify-keyspace-events', 'Ex')
```

### Redis 키 구조

```
user:online:{user_id}           # 온라인 상태 (TTL: 5분)
user:last_seen:{user_id}        # 마지막 접속 시간 (TTL: 7일)
online_users                    # 온라인 사용자 집합
user:websocket:{user_id}        # WebSocket 세션 ID (TTL: 5분)
user:status:{user_id}           # Pub/Sub 채널
```

### MySQL 테이블 구조

**users 테이블**:
```sql
is_online       BOOLEAN         -- 온라인 상태 (로그인/로그아웃/타임아웃 시 업데이트)
last_seen_at    DATETIME        -- 마지막 접속 시간 (로그아웃/타임아웃 시 업데이트)
is_active       BOOLEAN         -- 계정 활성화 상태 (친구 검색 필터링에 사용)
```

---

## 변경 사항 요약

### 신규 파일

1. **`app/utils/time_utils.py`**
   - `format_relative_time()`: 상대적 시간 표기 함수

2. **`app/services/heartbeat_monitor.py`**
   - `HeartbeatMonitor`: TTL 만료 자동 감지 및 처리
   - Redis Keyspace Notifications 활용

### 수정된 파일

1. **`app/api/auth.py`**
   - 로그인 시 MySQL 온라인 상태 업데이트 추가
   - 로그아웃 시 MySQL 오프라인 상태 및 `last_seen_at` 업데이트 추가

2. **`app/api/friend.py`**
   - 친구 요청 API 파라미터 변경 (`friendship_id` → `requester_user_id`)
   - 친구 목록 응답 변경 (`friendship_created_at` → `last_seen_at` + `last_seen_display`)
   - `format_relative_time()` 유틸 사용

3. **`app/api/profile.py`**
   - 불필요한 엔드포인트 2개 제거
   - 코드 간소화 (269줄 → 197줄)

4. **`app/api/online_status.py`**
   - 대폭 정리 (266줄 → 214줄)
   - SSE 스트리밍 엔드포인트 추가
   - 불필요한 엔드포인트 6개 제거
   - 친구 온라인 상태 응답 간소화

5. **`app/services/friendship_service.py`**
   - `accept_friend_request_by_requester()` 추가
   - `reject_friend_request_by_requester()` 추가

6. **`app/schemas/friendship.py`**
   - `FriendListResponse`: `last_seen_at`, `last_seen_display` 필드 추가

7. **`app/main.py`**
   - `online_status_router` 추가
   - `HeartbeatMonitor` 시작/중지 로직 추가
   - Lifespan 이벤트에서 자동 관리

### 제거된 엔드포인트

- **profile**: 2개 제거
- **online_status**: 6개 제거
- **총 8개 엔드포인트 제거**

### 추가된 엔드포인트

- **online_status**: `GET /online-status/stream` (SSE)
- **총 1개 엔드포인트 추가**

### 통계

| 항목 | 변경 전 | 변경 후 | 차이 |
|------|---------|---------|------|
| 엔드포인트 수 | ~35개 | ~28개 | -7개 |
| profile.py | 269줄 | 197줄 | -72줄 |
| online_status.py | 266줄 | 214줄 | -52줄 |
| 신규 파일 | - | 2개 | +2개 |

---

## 의존성 추가

### requirements.txt

```txt
sse-starlette>=1.6.5  # SSE 지원
```

**설치**:
```bash
pip install sse-starlette
```

---

## 테스트 가이드

### 1. 온라인 상태 확인

```bash
# 로그인
curl -X POST http://localhost:8000/api/auth/login/json \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'

# Heartbeat 전송
curl -X POST http://localhost:8000/api/online-status/heartbeat \
  -H "Authorization: Bearer YOUR_TOKEN"

# 특정 사용자 상태 조회
curl http://localhost:8000/api/online-status/user/123 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 2. SSE 스트리밍 테스트

```bash
# 터미널에서 SSE 연결
curl -N -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/online-status/stream
```

**출력 예시**:
```
event: status
data: {"user_id": 123, "is_online": true}

event: connected
data: {"message": "Monitoring 5 friends", "friend_ids": [123, 456, 789]}

event: status
data: {"user_id": 456, "is_online": false}
```

### 3. Heartbeat 타임아웃 테스트

1. 로그인
2. Heartbeat 전송 중지
3. 5분 후 자동으로 오프라인 처리
4. MySQL `is_online`, `last_seen_at` 확인

```sql
SELECT id, username, is_online, last_seen_at
FROM users
WHERE id = 1;
```

---

## 향후 개선 사항

### 단기 (1-2주)

1. **WebSocket 통합**
   - 채팅 메시지와 온라인 상태를 하나의 WebSocket 연결로 통합
   - SSE는 폴백용으로 유지

2. **친구 삭제 기능**
   - `DELETE /friends/{user_id}` 추가

3. **알림 시스템**
   - 친구 요청, 메시지 알림

### 중기 (1-2개월)

1. **DDD 패턴 적용**
   - 도메인별 모듈 분리
   - Repository 패턴 도입

2. **모니터링 강화**
   - Prometheus + Grafana
   - 온라인 사용자 수 메트릭
   - API 응답 시간 추적

3. **캐싱 전략**
   - 친구 목록 캐싱
   - 프로필 캐싱

### 장기 (3-6개월)

1. **MSA 전환**
   - Auth Service
   - Chat Service
   - Friend Service
   - Notification Service

2. **Kafka 도입**
   - Redis Pub/Sub → Kafka로 전환
   - 이벤트 소싱

3. **Spring Boot 마이그레이션**
   - 최종 목표

---

## 참고 자료

### 파일 위치

```
app/
├── api/
│   ├── auth.py              # 인증 API
│   ├── friend.py            # 친구 API
│   ├── profile.py           # 프로필 API
│   ├── health.py            # 헬스체크 API
│   └── online_status.py     # 온라인 상태 API (SSE 포함)
├── services/
│   ├── auth_service.py
│   ├── friendship_service.py
│   ├── online_status_service.py
│   └── heartbeat_monitor.py # 신규: Heartbeat 모니터
├── utils/
│   └── time_utils.py        # 신규: 시간 유틸리티
└── main.py                  # HeartbeatMonitor 시작
```

### 주요 기술 스택

- **FastAPI**: 웹 프레임워크
- **Redis**: 실시간 상태 관리, Pub/Sub
- **MySQL**: 영구 데이터 저장
- **SQLAlchemy**: ORM
- **SSE (Server-Sent Events)**: 실시간 푸시
- **Pydantic**: 데이터 검증

---

## 결론

### 달성한 목표

✅ API 정리 및 불필요한 엔드포인트 제거 (8개)
✅ Redis + MySQL 하이브리드 온라인 상태 관리
✅ 실시간 온라인 상태 스트리밍 (SSE)
✅ Heartbeat 타임아웃 자동 감지 및 처리
✅ 친구 목록 UX 개선 (상대적 시간 표기)
✅ 코드 간소화 및 유지보수성 향상

### 다음 단계

1. 의존성 설치 (`sse-starlette`)
2. 서버 재시작 및 테스트
3. 프론트엔드 SSE 연동
4. 모니터링 설정
5. 문서화 완료

---

**작성자**: Claude Code
**버전**: v1.0
**최종 수정**: 2026-01-23

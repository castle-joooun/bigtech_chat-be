# Redis & Security Features 가이드

이 문서는 BigTech Chat Backend에 새로 추가된 Redis 연동과 보안 기능들에 대한 가이드입니다.

## 🚀 새로 추가된 기능들

### Redis 연동
- **캐싱 시스템**: 성능 향상을 위한 데이터 캐싱
- **Rate Limiting**: API 요청 제한으로 서버 보호
- **세션 관리**: 사용자 세션 데이터 저장
- **연결 풀**: 효율적인 Redis 연결 관리

### 보안 기능
- **API Rate Limiting**: IP 기반 요청 제한
- **XSS 방어**: Cross-Site Scripting 공격 방어
- **SQL Injection 방어**: SQL 인젝션 공격 탐지 및 차단
- **보안 헤더**: OWASP 권장 보안 헤더 자동 설정

## 📦 설치 및 설정

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

새로 추가된 패키지:
- `redis==5.0.1`: Redis 클라이언트
- `aioredis==2.0.1`: 비동기 Redis 클라이언트
- `slowapi==0.1.8`: Rate limiting 라이브러리

### 2. 환경 변수 설정

`.env` 파일에 Redis 관련 설정을 추가하세요:

```env
# Redis 연결
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=20
REDIS_RETRY_ON_TIMEOUT=true
REDIS_SOCKET_KEEPALIVE=true

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10
```

### 3. Docker Compose로 실행

```bash
# 모든 서비스 시작 (Redis, MySQL, MongoDB, RedisInsight 포함)
docker-compose up -d

# 특정 서비스만 시작
docker-compose up -d redis
docker-compose up -d redisinsight
```

## 🔧 Redis 설정

### 연결 설정
Redis는 다음과 같이 최적화되어 있습니다:

```yaml
# docker-compose.yml
redis:
  image: redis:7.2-alpine
  command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru --tcp-keepalive 60 --timeout 300
```

주요 설정:
- **appendonly yes**: 데이터 영속성 보장
- **maxmemory 512mb**: 최대 메모리 사용량 제한
- **maxmemory-policy allkeys-lru**: LRU 방식으로 메모리 관리
- **tcp-keepalive 60**: TCP 연결 유지
- **timeout 300**: 연결 타임아웃 5분

### RedisInsight 관리 도구
Redis를 시각적으로 관리할 수 있는 RedisInsight가 포함되어 있습니다:

- **접속 URL**: http://localhost:8001
- **Redis 서버**: redis (Docker 네트워크 내에서)
- **포트**: 6379

## 🛡️ 보안 기능

### 1. API Rate Limiting

IP 주소 기반으로 API 요청을 제한합니다:

```python
# 기본 설정 (분당 60회 요청)
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# 엔드포인트별 다른 제한
/api/auth/login: 5회/분
/api/auth/register: 3회/분
/api/messages/upload-image: 10회/분
```

**응답 헤더**:
- `X-RateLimit-Limit`: 제한 수
- `X-RateLimit-Remaining`: 남은 요청 수
- `X-RateLimit-Reset`: 리셋 시간

### 2. XSS 방어

악성 스크립트 삽입을 방지합니다:

```python
# 탐지 패턴 예시
<script>, javascript:, onload=, <iframe>, <object> 등
```

**보안 헤더**:
```
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'; ...
```

### 3. SQL Injection 방어

SQL 인젝션 패턴을 탐지하고 차단합니다:

```python
# 탐지 패턴 예시
UNION SELECT, DROP TABLE, OR 1=1, --comment 등
```

### 4. 보안 헤더

OWASP 권장 보안 헤더를 자동으로 설정합니다:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000; includeSubDomains
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

## 📊 모니터링 및 헬스체크

### 헬스체크 엔드포인트

```bash
# 전체 서비스 상태 확인
GET /health

# Redis 상세 상태 확인
GET /health/redis

# Redis 기본 동작 테스트
POST /health/redis/test
```

### Redis 통계 확인

Redis 상태와 성능 지표를 실시간으로 확인할 수 있습니다:

```json
{
  "server": {
    "version": "7.2.0",
    "uptime_days": 1
  },
  "memory": {
    "used_memory_human": "2.5M",
    "used_memory_peak_human": "3.1M"
  },
  "clients": {
    "connected_clients": 5
  },
  "stats": {
    "total_commands_processed": 12340,
    "instantaneous_ops_per_sec": 15
  }
}
```

## 🔍 사용 예시

### 1. 캐시 사용

```python
from app.database.redis import set_cache, get_cache

# 데이터 캐싱
await set_cache("user:123", user_data, expire=3600)

# 캐시 조회
cached_data = await get_cache("user:123")
```

### 2. Rate Limiting 확인

```python
from app.database.redis import check_rate_limit

# Rate limit 확인
allowed, count, reset_time = await check_rate_limit(
    identifier="user:123",
    limit=60,
    window=60
)
```

### 3. 보안 로그 확인

보안 이벤트는 구조화된 로그로 기록됩니다:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "WARNING",
  "event_type": "security",
  "event": "rate_limit_exceeded",
  "severity": "medium",
  "ip_address": "192.168.1.100",
  "path": "/api/messages",
  "user_agent": "Mozilla/5.0..."
}
```

## 🚨 문제 해결

### Redis 연결 실패

```bash
# Redis 컨테이너 상태 확인
docker-compose ps redis

# Redis 로그 확인
docker-compose logs redis

# Redis 연결 테스트
docker-compose exec redis redis-cli ping
```

### Rate Limiting 문제

```bash
# Rate limit 상태 확인
curl -X POST http://localhost:8000/health/redis/test

# 특정 IP의 rate limit 리셋
# Redis CLI에서:
DEL rate_limit:192.168.1.100
```

### 보안 로그 확인

```bash
# 보안 이벤트 로그 확인
tail -f logs/app.log | grep "security"

# 특정 보안 이벤트 검색
grep "xss_attempt\|sql_injection_attempt\|rate_limit_exceeded" logs/app.log
```

## ⚙️ 성능 최적화

### Redis 성능 팁

1. **연결 풀 사용**: 연결 재사용으로 성능 향상
2. **적절한 TTL 설정**: 메모리 사용량 최적화
3. **파이프라이닝**: 다중 명령어 배치 실행
4. **적절한 데이터 구조**: Redis 데이터 타입 최적 활용

### Rate Limiting 최적화

1. **적응형 제한**: 사용자 패턴에 따른 동적 조정
2. **화이트리스트**: 신뢰할 수 있는 IP 예외 처리
3. **분산 환경**: Redis Cluster 사용 시 고려사항

## 📚 추가 리소스

- [Redis 공식 문서](https://redis.io/documentation)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [OWASP Security Headers](https://owasp.org/www-project-secure-headers/)
- [Rate Limiting Best Practices](https://cloud.google.com/architecture/rate-limiting-strategies-techniques)

## 🤝 기여하기

보안 기능 개선이나 Redis 최적화에 대한 제안이 있으시면 이슈를 생성하거나 풀 리퀘스트를 보내주세요.

---

**보안 참고사항**: 프로덕션 환경에서는 반드시 강력한 비밀키를 사용하고, 정기적인 보안 업데이트를 진행하세요.
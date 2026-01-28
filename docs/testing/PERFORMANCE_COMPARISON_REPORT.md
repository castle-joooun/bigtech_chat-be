# FastAPI vs Spring Boot 성능 비교 보고서

> **테스트 일자**: 2026-01-28
> **테스트 환경**: Docker Compose (로컬 개발 환경)
> **테스트 도구**: k6 v0.44.1

---

## 1. 테스트 개요

### 1.1 목적
동일한 기능을 구현한 FastAPI와 Spring Boot 마이크로서비스의 성능을 비교하여 프레임워크별 특성을 파악

### 1.2 테스트 시나리오 (User Flow)
1. **회원가입** (Register) - POST /auth/register
2. **로그인** (Login) - POST /auth/login
3. **프로필 조회** (Profile) - GET /profile/me

### 1.3 부하 패턴
```
stages:
  - 30초: 0 → 50 VUs (Ramp Up)
  - 60초: 100 VUs 유지 (Sustained Load)
  - 30초: 100 → 0 VUs (Ramp Down)

총 테스트 시간: 2분
최대 동시 사용자: 100 VUs
```

---

## 2. 테스트 환경

### 2.1 하드웨어
- **Machine**: MacBook (Apple Silicon)
- **Docker Desktop**: 리소스 제한 적용

### 2.2 FastAPI 구성
| 항목 | 설정 |
|------|------|
| Python | 3.11 |
| Framework | FastAPI 0.116.1 |
| WSGI Server | Gunicorn 23.0.0 |
| Worker | UvicornWorker × 4 |
| DB Pool | SQLAlchemy (pool_size=50, max_overflow=100) |
| Password Hashing | bcrypt (ThreadPoolExecutor 비동기) |

### 2.3 Spring Boot 구성
| 항목 | 설정 |
|------|------|
| Java | 17 |
| Framework | Spring Boot 3.x |
| Server | Embedded Tomcat |
| Thread Pool | max=400, min-spare=50 |
| DB Pool | HikariCP (maximum-pool-size=50) |
| Password Hashing | BCryptPasswordEncoder |
| JVM Options | -Xms512m -Xmx768m -XX:+UseG1GC |

### 2.4 인프라
| 서비스 | 버전 |
|--------|------|
| MySQL | 8.0 |
| Redis | 7.x |
| MongoDB | 6.0 |
| Kafka | Confluent 7.6.0 / Redpanda 23.3.5 |

---

## 3. 테스트 결과

### 3.1 종합 비교

| 지표 | FastAPI | Spring Boot | 차이 | 승자 |
|------|---------|-------------|------|------|
| **에러율** | 0.00% | 0.00% | - | 동점 |
| **총 반복 횟수** | 727 | 1,743 | +139.6% | 🏆 Spring Boot |
| **총 요청 수** | 2,181 | 5,229 | +139.7% | 🏆 Spring Boot |
| **평균 응답시간** | 2,684ms | 658ms | -75.5% | 🏆 Spring Boot |
| **p95 응답시간** | 7,842ms | 2,504ms | -68.1% | 🏆 Spring Boot |
| **최대 응답시간** | 9,598ms | 6,202ms | -35.4% | 🏆 Spring Boot |

### 3.2 작업별 상세 비교

| 작업 | FastAPI | Spring Boot | 배율 | 승자 |
|------|---------|-------------|------|------|
| **Registration (avg)** | 3,975ms | 956ms | 4.2× | 🏆 Spring Boot |
| **Login (avg)** | 4,070ms | 921ms | 4.4× | 🏆 Spring Boot |
| **Profile (avg)** | 8ms | 97ms | 12× | 🏆 FastAPI |

### 3.3 처리량 (Throughput)

```
FastAPI:    727 iterations / 122초 = 5.96 req/s
Spring Boot: 1,743 iterations / 121초 = 14.40 req/s

Spring Boot가 약 2.4배 더 많은 요청 처리
```

---

## 4. 결과 분석

### 4.1 Spring Boot가 빠른 이유

#### 1) BCrypt 처리 효율성
- **Spring Boot**: JVM의 네이티브 BCrypt 구현이 최적화됨
- **FastAPI**: Python의 bcrypt 라이브러리는 C 확장이지만 GIL 제약 존재
- bcrypt는 CPU-intensive 작업으로, JVM이 더 효율적으로 처리

#### 2) 스레드 풀 아키텍처
```
Spring Boot Tomcat:
  └── 400 threads 동시 처리 가능
  └── 각 요청이 독립적인 스레드에서 처리

FastAPI Gunicorn:
  └── 4 workers (프로세스)
  └── 각 프로세스 내에서 비동기 처리
  └── CPU-bound 작업 시 병목 발생
```

#### 3) JVM vs Python 인터프리터
- JVM의 JIT 컴파일러가 핫스팟 코드를 네이티브로 최적화
- Python은 인터프리터 오버헤드 존재

### 4.2 FastAPI가 빠른 이유 (Profile 조회)

#### 단순 I/O 작업에서의 강점
- FastAPI의 비동기(async/await) 모델이 I/O-bound 작업에 최적화
- DB 조회 후 응답 반환하는 단순 작업에서 오버헤드 최소화
- Spring Boot는 스레드 컨텍스트 스위칭 비용 발생

---

## 5. 개선 전후 비교 (FastAPI)

### 5.1 최적화 적용 내역

| 개선 항목 | 이전 | 이후 |
|-----------|------|------|
| WSGI Server | Uvicorn (단일) | Gunicorn + 4 Workers |
| bcrypt 처리 | 동기 (blocking) | ThreadPoolExecutor (비동기) |
| DB Pool Size | 10 | 50 |
| DB Max Overflow | 20 | 100 |

### 5.2 성능 개선 결과

| 지표 | 최적화 전 | 최적화 후 | 개선율 |
|------|-----------|-----------|--------|
| 에러율 | 39% ~ 96% | **0%** | ✅ 해결 |
| 평균 응답시간 | 18,700ms | 2,684ms | **85.6% 개선** |
| p95 응답시간 | 30,000ms+ | 7,842ms | **73.9% 개선** |

---

## 6. 권장 사항

### 6.1 FastAPI 선택 시
- ✅ I/O-bound 작업 위주 (API Gateway, Proxy)
- ✅ 빠른 프로토타이핑 및 개발
- ✅ 머신러닝/AI 서비스 (Python 생태계 활용)
- ✅ 단순 CRUD API
- ⚠️ CPU-intensive 작업 시 워커 수 충분히 확보 필요

### 6.2 Spring Boot 선택 시
- ✅ CPU-bound 작업 위주 (암호화, 대량 데이터 처리)
- ✅ 대규모 트래픽 처리
- ✅ 엔터프라이즈 환경 (트랜잭션 관리, 보안)
- ✅ 장기 운영 서비스
- ⚠️ 초기 개발 속도는 FastAPI보다 느림

### 6.3 하이브리드 아키텍처 제안
```
┌─────────────────────────────────────────────────────┐
│                   API Gateway                        │
│              (Kong / Spring Cloud)                   │
└──────────────┬───────────────────┬──────────────────┘
               │                   │
    ┌──────────▼──────────┐ ┌─────▼─────────────┐
    │   Spring Boot MSA   │ │   FastAPI MSA     │
    │                     │ │                   │
    │ • User Service      │ │ • ML/AI Service   │
    │ • Auth Service      │ │ • Real-time API   │
    │ • Payment Service   │ │ • Webhook Handler │
    └─────────────────────┘ └───────────────────┘
```

---

## 7. 추가 테스트 제안

### 7.1 향후 테스트 항목
- [ ] Kubernetes 환경에서의 오토스케일링 테스트
- [ ] 메모리 사용량 및 CPU 사용률 비교
- [ ] Cold Start 시간 비교
- [ ] 장시간 부하 테스트 (Soak Test)
- [ ] 스파이크 테스트 (Spike Test)

### 7.2 추가 최적화 방안

#### FastAPI
- PyPy 인터프리터 사용 검토
- Cython으로 핫스팟 코드 컴파일
- 워커 수 증가 (CPU 코어 × 2 + 1)
- Redis 캐싱 적극 활용

#### Spring Boot
- GraalVM Native Image 적용
- Virtual Threads (Java 21) 적용
- Reactive Stack (WebFlux) 전환 검토

---

## 8. 결론

### 8.1 성능 요약
```
┌────────────────────────────────────────────────────────┐
│              성능 비교 요약 (2분 테스트)                │
├────────────────────────────────────────────────────────┤
│                                                        │
│  처리량:     Spring Boot 2.4배 우수                    │
│  응답속도:   Spring Boot 4배 빠름 (CPU 작업)           │
│              FastAPI 12배 빠름 (I/O 작업)              │
│  안정성:     둘 다 에러율 0% 달성                      │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### 8.2 최종 판단

| 평가 항목 | FastAPI | Spring Boot |
|-----------|---------|-------------|
| 개발 생산성 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| CPU 성능 | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| I/O 성능 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 확장성 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 생태계 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 러닝 커브 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

**결론**: 인증/암호화 같은 CPU-intensive 작업이 많은 User Service에서는 **Spring Boot**가 더 적합하며, 단순 I/O 작업 위주의 서비스에서는 **FastAPI**도 충분히 경쟁력 있음.

---

## 부록: 테스트 스크립트

### k6 테스트 설정
```javascript
export const options = {
  stages: [
    { duration: '30s', target: 50 },
    { duration: '1m', target: 100 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<3000'],
    errors: ['rate<0.3'],
  },
};
```

### 실행 명령어
```bash
# FastAPI 테스트
k6 run fastapi-user-flow-test.js

# Spring Boot 테스트
k6 run spring-user-flow-test.js
```

---

*문서 작성: Claude Code*
*최종 수정: 2026-01-28*

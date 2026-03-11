# BigTech Chat Backend

실시간 채팅 플랫폼 백엔드. Monolithic FastAPI에서 MSA로 전환하고, Spring Boot로 재구현한 프로젝트.

## 기술 스택

| 영역 | 기술 |
|------|------|
| Backend | FastAPI (Python), Spring Boot 3 (Java 21) |
| Database | MySQL (사용자/친구), MongoDB (메시지) |
| Cache | Redis |
| Messaging | Apache Kafka |
| Container | Docker, Kubernetes (Kustomize) |
| Monitoring | Prometheus, Grafana |
| Auth | JWT (access token) |
| Test | K6 (부하 테스트), JUnit5, pytest |

## 프로젝트 구조

```
bigtech_chat-be/
├── legacy/                    # Monolithic FastAPI
│   ├── app/
│   │   ├── api/               # REST endpoints
│   │   ├── core/              # config, validators
│   │   ├── database/          # MySQL, MongoDB, Redis
│   │   ├── models/            # ORM models
│   │   ├── services/          # business logic
│   │   ├── middleware/        # error handler, rate limit, CORS
│   │   ├── domain/            # domain events
│   │   └── infrastructure/    # Kafka producer/consumer
│   └── tests/
│
├── microservices/             # FastAPI MSA
│   ├── user-service/          # port 8005
│   ├── friend-service/        # port 8003
│   ├── chat-service/          # port 8002
│   ├── api-gateway/           # Kong gateway
│   ├── shared_lib/            # 공용 라이브러리
│   ├── infrastructure/        # Docker Compose, 모니터링
│   ├── k8s/                   # Kubernetes manifests
│   └── tests/                 # e2e, load test (K6)
│
└── spring-boot-services/      # Spring Boot MSA
    ├── user-service/          # port 8081
    ├── friend-service/        # port 8003
    ├── chat-service/          # port 8002
    ├── api-gateway/           # Spring Cloud Gateway
    ├── common-lib/            # 공용 모듈 (JWT, Kafka, exception)
    ├── infrastructure/        # Prometheus, Grafana 설정
    └── k8s/                   # Kubernetes Kustomize (dev/prod)
```

## 아키텍처 진화

### 1단계: Monolithic FastAPI
- 단일 FastAPI 앱, MySQL + MongoDB + Redis
- JWT 인증, WebSocket 실시간 메시징

### 2단계: FastAPI MSA + Event-Driven
- 도메인별 서비스 분리 (User, Friend, Chat)
- Kafka 기반 비동기 이벤트 처리
- Docker Compose 환경 구성

### 3단계: Spring Boot MSA
- Java 21 + Virtual Thread 적용
- CompletableFuture 비동기 BCrypt 처리 (Thread Pool Starvation 해결)
- 코드 레벨 성능 최적화 (N+1 제거, 서비스 간 HTTP 호출 최소화)
- Kubernetes Kustomize 배포 구성

## 실행 방법

### Legacy (Monolithic)
```bash
cd legacy
cp .env.example .env
docker-compose up -d
uvicorn app.main:app --reload
```

### FastAPI MSA
```bash
cd microservices
docker-compose up -d
```

### Spring Boot MSA
```bash
cd spring-boot-services
docker-compose up -d
```

## 부하 테스트

K6를 사용한 벤치마크 (50 VU / 60초, 9단계 사용자 플로우):

```bash
# FastAPI MSA
k6 run -e TARGET=fastapi microservices/tests/load/fastapi-vs-spring-benchmark.js

# Spring Boot MSA
k6 run -e TARGET=spring microservices/tests/load/fastapi-vs-spring-benchmark.js
```

테스트 시나리오: 회원가입 → 로그인 → 프로필 조회 → 사용자 검색 → 친구 요청 → 친구 승인 → 채팅방 생성 → 메시지 발송(5회) → 메시지 조회

## 주요 성능 최적화

- **BCrypt 비동기 격리**: CompletableFuture + 전용 스레드 풀로 Tomcat 스레드 해방 (일반 API 25.7배 개선)
- **N+1 쿼리 제거**: 개별 MongoDB 쿼리를 `findByMessageIdIn` 배치로 전환
- **서비스 간 HTTP 최소화**: JWT payload에서 사용자 정보 추출, 불필요한 inter-service 호출 제거
- **Virtual Thread**: Java 21 Virtual Thread로 I/O-bound 동시성 개선

## License

MIT

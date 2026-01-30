# MSA 마이그레이션 현황

> **작성일**: 2026-01-27
> **현재 단계**: ✅ **MSA 마이그레이션 완료**

---

## 📊 전체 진행 상황

| Week | 작업 | 상태 | 완료율 |
|------|------|------|--------|
| Week 1-2 | DDD Lite 적용 | ✅ 완료 | 100% |
| Week 3-4 | Kafka 통합 | ✅ 완료 | 100% |
| Week 5 | MSA 서비스 분리 | ✅ 완료 | 100% |
| Week 6 | API Gateway 구성 | ✅ 완료 | 100% |
| Week 7-8 | 모니터링 & CI/CD | ✅ 완료 | 100% |

---

## ✅ 완료된 작업

### Week 1-2: DDD Lite 적용
- ✅ Bounded Context 문서화
- ✅ Aggregate 설계
- ✅ Domain Events 정의
- ✅ Event Storming 다이어그램

### Week 3-4: Kafka 통합
- ✅ Kafka Docker Compose 설정 (3 brokers)
- ✅ Kafka Producer/Consumer 구현
- ✅ Redis Pub/Sub → Kafka 마이그레이션
  - ✅ 메시지 전송 (MessageSent 이벤트)
  - ✅ 메시지 SSE 스트리밍
  - ✅ 온라인 상태 변경 (UserOnlineStatusChanged 이벤트)
  - ✅ 온라인 상태 SSE 스트리밍
- ✅ Kafka 테스트 스크립트 작성
- ✅ Topic 생성 및 검증

### Week 5: MSA 서비스 분리
- ✅ 3개 마이크로서비스 완전 구현
  - ✅ User Service (Port 8005) - **완전 동작**
  - ✅ Friend Service (Port 8003) - **완전 동작**
  - ✅ Chat Service (Port 8002) - **완전 동작**
- ✅ User Service API 구현 완료
  - ✅ 인증 API (회원가입, 로그인, 로그아웃)
  - ✅ 프로필 API (조회, 수정, 이미지 관리)
  - ✅ 사용자 검색 API
- ✅ Friend Service API 구현 완료
  - ✅ 친구 요청/수락/거절/취소 API
  - ✅ 친구 목록/검색 API
- ✅ Chat Service API 구현 완료
  - ✅ 채팅방 관리 API
  - ✅ 메시지 CRUD API
  - ✅ 실시간 SSE 스트리밍
- ✅ MSA 전체 문서 작성 (services/README.md)

### Week 6: API Gateway 구성
- ✅ Kong API Gateway 설정
- ✅ 라우팅 규칙 설정
  - `/api/auth/*`, `/api/users/*`, `/api/profile/*` → User Service (8005)
  - `/api/chat-rooms/*`, `/api/messages/*` → Chat Service (8002)
  - `/api/friends/*` → Friend Service (8003)
- ✅ 플러그인 설정 (CORS, Rate Limiting)
- ✅ Docker Compose 통합 (docker-compose.msa.yml)

### Week 7-8: 모니터링 & CI/CD
- ✅ Prometheus 설정
  - ✅ 서비스 메트릭 수집 설정
  - ✅ 알림 규칙 정의 (alert-rules.yml)
- ✅ Grafana 설정
  - ✅ 데이터소스 자동 프로비저닝
  - ✅ MSA Overview 대시보드
- ✅ 중앙 로깅 (Loki + Promtail)
  - ✅ Loki 로그 저장소 설정
  - ✅ Promtail 로그 수집 에이전트 설정
- ✅ Alertmanager 알림 설정
  - ✅ 알림 라우팅 (Critical/Warning)
  - ✅ 웹훅 수신자 설정
- ✅ CI/CD 파이프라인 (GitHub Actions)
  - ✅ CI: Lint, Type Check, 서비스별 테스트, Docker 빌드
  - ✅ CD: GHCR 푸시, Staging/Production 배포

---

## ⏳ 추후 구현 예정 (신규 기능)

### Notification Service (Port 8004)
> 기존 Monolithic 앱에 없던 신규 서비스. MSA 전환 후 추가 기능으로 구현 예정.

**예정 기능:**
- ⏳ 알림 API 신규 구현 (목록 조회, 읽음 처리)
- ⏳ 실시간 알림 SSE 스트리밍
- ⏳ Kafka Consumer 연동 (friend.events, message.events)

### 추가 개선 사항 (추후)
- ✅ Kafka Producer 통합 (각 서비스) - 완료
- ⏳ 분산 트레이싱 (Jaeger) - 추후 검토
- ⏳ E2E 테스트 자동화

---

## 🏗️ 현재 아키텍처 (완료)

```
                         ┌─────────────────────┐
                         │   API Gateway       │
                         │   Kong (80/443)     │
                         │   Admin API (8001)  │
                         └──────────┬──────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
          ▼                         ▼                         ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  User Service    │    │  Chat Service    │    │ Friend Service   │
│  (Port 8005)     │    │  (Port 8002)     │    │  (Port 8003)     │
│                  │    │                  │    │                  │
│  ✅ 인증 API      │    │  ✅ 채팅방 API    │    │  ✅ 친구 요청 API │
│  ✅ 프로필 API    │    │  ✅ 메시지 API    │    │  ✅ 친구 목록 API │
│  ✅ 사용자 검색   │    │  ✅ SSE 스트리밍  │    │  ✅ 사용자 검색   │
└────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │   Kafka Event Bus       │
                    │   (3 brokers)           │
                    │   Topics: message.events│
                    │   user.online_status,   │
                    │   friend.events, ...    │
                    └─────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     Observability Stack                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐│
│  │ Prometheus  │  │   Grafana   │  │    Loki     │  │Alertmanager ││
│  │  (9090)     │  │   (3000)    │  │   (3100)    │  │  (9093)     ││
│  │  Metrics    │  │  Dashboard  │  │   Logging   │  │   Alerts    ││
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘│
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        CI/CD Pipeline                               │
│  GitHub Actions: Lint → Test → Build → Push (GHCR) → Deploy        │
│  Environments: Staging (main branch) / Production (tags v*)         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔑 주요 결정사항

### 기술 스택
- **언어**: Python 3.11+
- **프레임워크**: FastAPI
- **데이터베이스**: MySQL (User, Chat, Friend), MongoDB (Messages), Redis (Cache)
- **메시지 브로커**: Kafka (3 brokers)
- **API Gateway**: Kong ✅
- **컨테이너**: Docker, Docker Compose
- **모니터링**: Prometheus + Grafana + Loki + Alertmanager ✅
- **CI/CD**: GitHub Actions ✅
- **오케스트레이션**: Kubernetes (미래)

### Port 할당
| 서비스 | Port | 용도 | 상태 |
|--------|------|------|------|
| Kong API Gateway | 80/443 | 외부 진입점 | ✅ 완료 |
| Kong Admin API | 8001 | Gateway 관리 | ✅ 완료 |
| User Service | 8005 | 사용자 인증/프로필 | ✅ 완료 |
| Chat Service | 8002 | 채팅/메시지 | ✅ 완료 |
| Friend Service | 8003 | 친구 관계 | ✅ 완료 |
| Notification Service | 8004 | 알림 | ⏳ 신규 |
| Kafka UI | 8080 | Kafka 모니터링 | ✅ 완료 |
| Prometheus | 9090 | 메트릭 수집 | ✅ 완료 |
| Grafana | 3000 | 메트릭 시각화 | ✅ 완료 |
| Loki | 3100 | 로그 저장소 | ✅ 완료 |
| Alertmanager | 9093 | 알림 관리 | ✅ 완료 |
| Monolithic API | 8000 | 레거시 (deprecated) | ⚠️ |

### Kafka Topics
| Topic | Producer | Consumer | 설명 |
|-------|----------|----------|------|
| `message.events` | Chat Service | Chat Service (SSE), Notification Service | 메시지 전송 이벤트 |
| `user.online_status` | User Service | Notification Service | 온라인 상태 변경 |
| `user.events` | User Service | - | 사용자 등록/수정 |
| `chat.events` | Chat Service | - | 채팅방 생성 |
| `friend.events` | Friend Service | Chat Service, Notification Service | 친구 요청/수락 |
| `notification.events` | Notification Service | - | 알림 전송 완료 |

---

## 📝 참고 문서

- [DDD Bounded Context](./docs/architecture/01-bounded-context.md)
- [Aggregate 설계](./docs/architecture/02-aggregate-design.md)
- [Domain Events](./docs/architecture/03-domain-events.md)
- [MSA 마이그레이션 전략](./docs/architecture/04-msa-migration.md)
- [Kafka Topic 설계](./docs/kafka/topic-design.md)
- [Kubernetes 배포 가이드](./k8s/README.md)
- [Dockerfile 최적화](./docs/optimization/01-dockerfile-optimization.md)
- [빠른 시작 가이드](./docs/QUICK_START.md)

---

## 🚀 빠른 시작

### 전체 MSA 스택 실행 (권장)
```bash
# 전체 스택 실행 (Kong + 서비스 + 인프라)
docker-compose -f docker-compose.msa.yml up -d

# Kong 라우팅 설정
chmod +x infrastructure/docker/kong/kong-config.sh
./infrastructure/docker/kong/kong-config.sh
```

### 개별 서비스 실행 (개발용)
```bash
# User Service
cd services/user-service
python -m uvicorn main:app --host 0.0.0.0 --port 8005 --reload

# Friend Service
cd services/friend-service
python -m uvicorn main:app --host 0.0.0.0 --port 8003 --reload

# Chat Service
cd services/chat-service
python -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

### 모니터링 스택 실행
```bash
docker-compose -f infrastructure/docker/docker-compose-monitoring.yml up -d
```

### Kafka 클러스터 실행
```bash
docker-compose -f infrastructure/docker/docker-compose-kafka.yml up -d
```

### 서비스 접속 URL
| 서비스 | URL |
|--------|-----|
| API Gateway | http://localhost |
| User Service Swagger | http://localhost:8005/docs |
| Friend Service Swagger | http://localhost:8003/docs |
| Chat Service Swagger | http://localhost:8002/docs |
| Grafana | http://localhost:3000 (admin/admin) |
| Prometheus | http://localhost:9090 |
| Kafka UI | http://localhost:8080 |

---

## 📁 주요 파일 구조

```
bigtech_chat-be/
├── services/
│   ├── user-service/          # User Service (Port 8005)
│   ├── friend-service/        # Friend Service (Port 8003)
│   └── chat-service/          # Chat Service (Port 8002)
├── infrastructure/
│   └── docker/
│       ├── kong/              # Kong Gateway 설정
│       ├── prometheus/        # Prometheus 설정
│       ├── grafana/           # Grafana 대시보드/데이터소스
│       ├── loki/              # Loki 로그 저장소 설정
│       ├── promtail/          # Promtail 로그 수집 설정
│       └── alertmanager/      # Alertmanager 알림 설정
├── .github/
│   └── workflows/
│       ├── ci.yml             # CI 파이프라인
│       └── cd.yml             # CD 파이프라인
├── docker-compose.msa.yml     # 전체 MSA 스택
└── MSA_MIGRATION_STATUS.md    # 이 문서
```

---

## 📞 Contact

문제가 발생하거나 질문이 있으면 GitHub Issues에 등록해주세요.

**마지막 업데이트**: 2026-01-27
**문서 버전**: v2.0 (MSA 마이그레이션 완료)

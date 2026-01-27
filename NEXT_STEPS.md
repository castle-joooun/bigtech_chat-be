# 다음 작업 로드맵

> **작성일**: 2026-01-27
> **마지막 업데이트**: 2026-01-27
> **진행률**: 4/6 단계 완료 (67%)

---

## 📋 작업 현황 요약

| 단계 | 작업 | 상태 | 우선순위 |
|------|------|------|----------|
| 1 | Dockerfile 최적화 (Multi-stage build) | ✅ 완료 | 높음 |
| 2 | Kubernetes Manifests 작성 | ✅ 완료 | 높음 |
| 3 | Grafana 대시보드 추가 | ✅ 완료 | 중간 |
| 4 | E2E 테스트 자동화 | ✅ 완료 | 중간 |
| 5 | 분산 트레이싱 (Jaeger) | ⏳ 추후 검토 | 낮음 |
| 6 | Spring Boot 전환 | ⏳ 추후 | 낮음 |

---

## ✅ 1단계: Dockerfile 최적화

**상태**: ✅ 완료 (2026-01-27)

**목표**: Multi-stage build로 이미지 크기 및 빌드 시간 최적화

**작업 내용**:
- [x] User Service Dockerfile 최적화
- [x] Friend Service Dockerfile 최적화
- [x] Chat Service Dockerfile 최적화
- [x] 이미지 크기 비교 (Before/After)
- [x] .dockerignore 파일 추가

**결과**:

| 서비스 | Before | After | 절감률 |
|--------|--------|-------|--------|
| User Service | 425MB | 251MB | **-41%** |
| Friend Service | 425MB | 251MB | **-41%** |
| Chat Service | 471MB | 297MB | **-37%** |

**최적화 내용**:
1. Multi-stage build (builder → runtime 분리)
2. Builder 스테이지에서만 gcc, libffi-dev 설치
3. Runtime 스테이지에는 curl만 설치 (헬스체크용)
4. 비-root 사용자 (appuser)로 보안 강화
5. .dockerignore로 불필요한 파일 제외

---

## ✅ 2단계: Kubernetes 배포

**상태**: ✅ 완료 (2026-01-27)

**목표**: Kubernetes 매니페스트 작성 및 배포 준비

**작업 내용**:
- [x] 디렉토리 구조 생성 (`k8s/manifests/`)
- [x] Namespace 정의
- [x] ConfigMap / Secret 작성
- [x] Deployment 작성 (User, Friend, Chat Service)
- [x] Service 작성 (ClusterIP)
- [x] StatefulSet 작성 (MySQL, MongoDB, Redis, Kafka)
- [x] HPA 설정 (CPU 70% 기준 Auto Scaling)
- [x] Ingress 설정 (Nginx + Kong 둘 다 지원)

**산출물**:
```
k8s/
├── manifests/
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml
│   ├── services/
│   │   ├── user-service.yaml
│   │   ├── friend-service.yaml
│   │   └── chat-service.yaml
│   ├── statefulsets/
│   │   ├── mysql.yaml
│   │   ├── mongodb.yaml
│   │   ├── redis.yaml
│   │   └── kafka.yaml
│   ├── hpa/
│   │   └── hpa.yaml
│   └── ingress/
│       └── ingress.yaml
└── README.md
```

**주요 설정**:
| 리소스 | 설정 |
|--------|------|
| Namespace | `bigtech-chat` |
| Services Replicas | 2 (min) → 10~15 (max, HPA) |
| HPA CPU Target | 70% |
| Kafka Brokers | 3 (KRaft mode) |
| Ingress | Nginx + Kong 지원 |

---

## ✅ 3단계: Grafana 대시보드 추가

**상태**: ✅ 완료 (2026-01-27)

**목표**: 비즈니스 메트릭 및 서비스별 대시보드 작성

**작업 내용**:
- [x] User Service 대시보드 (가입자 수, 로그인 현황, 응답 시간)
- [x] Friend Service 대시보드 (친구 요청, 수락률, 트래픽)
- [x] Chat Service 대시보드 (메시지 처리량, 채팅방 생성, SSE)
- [x] Infrastructure 대시보드 (MySQL, MongoDB, Redis, Kafka)

**산출물**:
- `infrastructure/docker/grafana/dashboards/user-service.json`
- `infrastructure/docker/grafana/dashboards/friend-service.json`
- `infrastructure/docker/grafana/dashboards/chat-service.json`
- `infrastructure/docker/grafana/dashboards/infrastructure.json`

**대시보드 구성**:
| 대시보드 | 주요 패널 |
|----------|-----------|
| User Service | 서비스 상태, RPS, P95 지연, 에러율, 가입자/로그인(24h) |
| Friend Service | 서비스 상태, 친구 요청/수락(24h), 엔드포인트별 트래픽 |
| Chat Service | 서비스 상태, 메시지 전송(1h), 채팅방 생성(24h), SSE 트래픽 |
| Infrastructure | MySQL/MongoDB/Redis/Kafka 상태, 연결 수, 메모리, 처리량 |

---

## ✅ 4단계: E2E 테스트 자동화

**상태**: ✅ 완료 (2026-01-27)

**목표**: 통합 테스트 작성 및 CI 파이프라인 연동

**작업 내용**:
- [x] 테스트 환경 구성 (docker-compose.test.yml)
- [x] User Service E2E 테스트 (인증, 프로필, 검색)
- [x] Friend Service E2E 테스트 (요청, 수락, 거절, 목록)
- [x] Chat Service E2E 테스트 (채팅방, 메시지, 읽음 처리)
- [x] GitHub Actions CI에 E2E 테스트 추가

**산출물**:
```
tests/e2e/
├── conftest.py              # 공통 설정 및 Fixtures
├── test_user_service.py     # User Service 테스트 (15+ 케이스)
├── test_friend_service.py   # Friend Service 테스트 (10+ 케이스)
├── test_chat_service.py     # Chat Service 테스트 (12+ 케이스)
├── requirements.txt         # 테스트 의존성
├── pytest.ini               # Pytest 설정
└── Dockerfile               # 테스트 러너 이미지
docker-compose.test.yml      # 테스트 환경 (격리된 DB/Kafka)
```

**테스트 커버리지**:
| 서비스 | 테스트 케이스 |
|--------|--------------|
| User Service | Health, Registration, Auth, Profile, Search |
| Friend Service | Health, Request, Accept/Reject, List, Search |
| Chat Service | Health, Room CRUD, Message CRUD, Read Status |

---

## ⚪ 5단계: 분산 트레이싱 (Jaeger)

**상태**: ⏳ 추후 검토

**목표**: 서비스 간 요청 추적 및 성능 분석

**작업 내용**:
- [ ] Jaeger 설정 (docker-compose)
- [ ] OpenTelemetry 연동 (각 서비스)
- [ ] 트레이싱 대시보드 구성

**비고**: 현재 Prometheus + Loki로 기본 모니터링 가능. 필요시 추후 도입.

---

## ⚪ 6단계: Spring Boot 전환

**상태**: ⏳ 추후

**목표**: FastAPI → Spring Boot 마이그레이션

**비고**: 로드맵 상 최종 단계. MSA 안정화 후 진행.

---

## 📝 참고 사항

### 작업 시작 전 체크리스트
1. Docker Desktop 실행 확인
2. 기존 컨테이너 상태 확인: `docker-compose -f docker-compose.msa.yml ps`
3. 로컬 MySQL 충돌 확인 (Port 3306)

### 유용한 명령어
```bash
# MSA 스택 실행
docker-compose -f docker-compose.msa.yml up -d

# 모니터링 스택 실행
docker-compose -f infrastructure/docker/docker-compose-monitoring.yml up -d

# 서비스 로그 확인
docker logs bigtech-user-service -f
docker logs bigtech-chat-service -f

# Kafka UI
http://localhost:8080

# Grafana
http://localhost:3000 (admin/admin123)

# Prometheus
http://localhost:9090
```

---

## 📚 관련 문서

| 문서 | 설명 |
|------|------|
| [빠른 시작 가이드](./docs/QUICK_START.md) | 로컬 개발 환경 실행 |
| [Dockerfile 최적화](./docs/optimization/01-dockerfile-optimization.md) | Docker 최적화 상세 |
| [K8s 배포 가이드](./k8s/README.md) | Kubernetes 배포 가이드 |
| [MSA 마이그레이션 현황](./MSA_MIGRATION_STATUS.md) | 전체 마이그레이션 현황 |

---

**다음 작업**: 5단계 (분산 트레이싱 - Jaeger) 또는 6단계 (Spring Boot 전환) 진행

> ✅ **주요 작업 완료**: Dockerfile 최적화, K8s Manifests, Grafana 대시보드, E2E 테스트 모두 완료됨

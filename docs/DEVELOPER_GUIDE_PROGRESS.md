# 신입 개발자 온보딩 가이드 작성 진행 상황

> **목표**: Python/FastAPI만 알고 있는 신입 개발자가 이 프로젝트를 이해하고, Spring Boot 마이그레이션을 준비할 수 있는 통합 가이드 문서 작성
>
> **최종 산출물**: `docs/DEVELOPER_GUIDE.md`
>
> **작성일**: 2026-01-27

---

## 작업 진행 현황

| 단계 | 작업 | 상태 | 완료일 |
|------|------|------|--------|
| 0 | 문서 분석 및 계획 수립 | ✅ 완료 | 2026-01-27 |
| 1 | Part 1: 시작하기 | ⏳ 대기 | - |
| 2 | Part 2: FastAPI 코드 이해 | ⏳ 대기 | - |
| 3 | Part 3: MSA 아키텍처 | ⏳ 대기 | - |
| 4 | Part 4: Kafka | ⏳ 대기 | - |
| 5 | Part 5: Docker & K8s | ⏳ 대기 | - |
| 6 | Part 6: Observability | ⏳ 대기 | - |
| 7 | Part 7: 테스트 & CI/CD | ⏳ 대기 | - |
| 8 | Part 8: Spring Boot 준비 | ⏳ 대기 | - |
| 9 | Part 9: 실습 + 부록 | ⏳ 대기 | - |

---

## 완료된 작업 상세

### 0. 문서 분석 및 계획 수립 ✅

**완료일**: 2026-01-27

**수행 내용**:
1. 기존 문서 구조 분석
   - 루트: README.md, MSA_MIGRATION_STATUS.md, NEXT_STEPS.md
   - docs/architecture/ (DDD 문서 4개)
   - docs/kafka/ (Kafka 문서 2개)
   - docs/observability/ (모니터링 문서 4개)
   - docs/optimization/ (Docker 최적화 1개)
   - docs/api/ (온라인 상태 시스템 1개)
   - docs/spring-boot/, docs/testing/, docs/redis-security.md
   - k8s/README.md, docs/QUICK_START.md

2. 코드 구조 분석
   - services/user-service/ (Port 8005)
   - services/friend-service/ (Port 8003)
   - services/chat-service/ (Port 8002)
   - infrastructure/docker/ (Docker Compose, Grafana, Prometheus, Kong)
   - tests/e2e/ (E2E 테스트)

3. 신입 개발자가 어려워할 개념 식별
   - MSA, DDD, Bounded Context, Aggregate
   - Kafka (Topic, Partition, Consumer Group, Consumer Lag)
   - Kubernetes (Pod, Deployment, StatefulSet, HPA, Ingress)
   - 모니터링 (Prometheus, Grafana, PromQL)

---

## 문서 구조 계획

### Part 1: 시작하기 (Day 1-3) - 예상 ~200줄
- 프로젝트 소개 및 목표
- 기술 스택 개요 (익숙한 것 vs 새로 배울 것)
- 로컬 개발 환경 설정 (Docker, 서비스 실행)
- 참조: `docs/QUICK_START.md`

### Part 2: FastAPI 코드 이해하기 (Day 4-7) - 예상 ~300줄
- async/await, Pydantic, Depends 패턴
- MySQL/MongoDB/Redis 연동 코드 분석
- 서비스별 핵심 코드 설명
- 참조: `services/*/app/` 코드 발췌

### Part 3: MSA 아키텍처 (Day 8-14) - 예상 ~250줄
- Monolithic vs MSA 비교
- DDD 기초 (Bounded Context, Aggregate)
- 서비스 간 통신 (REST, Kafka)
- 참조: `docs/architecture/*.md`

### Part 4: Kafka Event Streaming (Day 15-21) - 예상 ~200줄
- Kafka 기초 (Producer, Consumer, Topic)
- 이 프로젝트의 Topic 설계
- 실습: Kafka UI로 이벤트 추적
- 참조: `docs/kafka/*.md`

### Part 5: Docker & Kubernetes (Day 22-28) - 예상 ~200줄
- Dockerfile 구조 (Multi-stage build)
- K8s 기초 (Pod, Deployment, Service)
- 이 프로젝트의 K8s 매니페스트
- 참조: `docs/optimization/01-dockerfile-optimization.md`, `k8s/README.md`

### Part 6: Observability (Day 29-35) - 예상 ~150줄
- Prometheus + Grafana 메트릭
- Loki 중앙 로깅
- Alertmanager 알림
- 참조: `docs/observability/*.md`

### Part 7: 테스트 및 CI/CD (Day 36-42) - 예상 ~150줄
- Unit/Integration/E2E 테스트 구조
- GitHub Actions CI/CD 파이프라인
- 참조: `tests/e2e/`, `.github/workflows/ci.yml`

### Part 8: Spring Boot 마이그레이션 준비 (Day 43-49) - 예상 ~150줄
- FastAPI vs Spring Boot 비교
- 학습 로드맵 및 마이그레이션 전략
- 참조: `docs/spring-boot/fastapi-vs-springboot.md`

### Part 9: 실습 과제 및 부록 - 예상 ~200줄
- 주차별 실습 과제
- 용어집 (Glossary)
- 명령어 치트시트
- FAQ

---

## 작성 원칙

1. **비유와 다이어그램 활용**: Kafka = 우체국, MSA = 팀 분리 등
2. **Before/After 비교**: Monolithic → MSA, 단일 DB → 다중 DB
3. **코드 예시 포함**: 실제 프로젝트 코드 발췌 + 주석 설명
4. **Spring Boot 연결**: 각 섹션 끝에 "Spring Boot에서는?" 박스
5. **기존 문서 링크**: 상세 내용은 기존 문서로 유도 (중복 최소화)

---

## 참조할 핵심 파일

| 카테고리 | 파일 | 용도 |
|----------|------|------|
| 프로젝트 개요 | `README.md` | Part 1 |
| 빠른 시작 | `docs/QUICK_START.md` | Part 1 |
| DDD 아키텍처 | `docs/architecture/*.md` (4개) | Part 3 |
| Kafka 설계 | `docs/kafka/*.md` (2개) | Part 4 |
| Docker 최적화 | `docs/optimization/01-dockerfile-optimization.md` | Part 5 |
| K8s 배포 | `k8s/README.md` | Part 5 |
| 모니터링 | `docs/observability/*.md` (4개) | Part 6 |
| 테스트 | `tests/e2e/`, `.github/workflows/ci.yml` | Part 7 |
| Spring Boot | `docs/spring-boot/fastapi-vs-springboot.md` | Part 8 |
| 코드 예시 | `services/user-service/` | Part 2 |

---

## 신입 개발자가 어려워할 핵심 개념 (설명 필요)

### MSA/DDD 관련
- Bounded Context: 비즈니스 도메인의 경계
- Aggregate Root: 트랜잭션 일관성 경계의 진입점
- Domain Events: 비즈니스에서 중요한 사건

### Kafka 관련
- Topic vs Partition: 주제 vs 병렬 처리 단위
- Consumer Group: 같은 group_id의 consumer들은 partition 분배
- Consumer Lag: 생산 속도 > 소비 속도일 때 지연

### Kubernetes 관련
- Pod: 컨테이너 실행 단위
- Deployment vs StatefulSet: 무상태 vs 상태 유지
- HPA: CPU/Memory 기반 자동 스케일링
- Ingress: 외부 트래픽 → 내부 서비스 라우팅

### 모니터링 관련
- Counter vs Gauge: 누적값 vs 현재값
- PromQL: Prometheus 쿼리 언어

---

**다음 작업**: Part 1 (시작하기) 작성

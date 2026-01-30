# 📚 BigTech Chat Backend - 문서 학습 가이드

> **목적**: 문서를 효율적으로 읽고 전체 아키텍처를 이해하기 위한 로드맵
> **대상**: 이 프로젝트를 처음 접하는 개발자
> **소요 시간**: 약 3-4주 (하루 2-3시간 기준)

---

## 🎯 학습 목표

이 가이드를 완료하면 다음을 이해할 수 있습니다:
- ✅ FastAPI 기반 채팅 서비스의 전체 아키텍처
- ✅ Monolithic → DDD → MSA로의 진화 과정
- ✅ Kafka 기반 이벤트 드리븐 아키텍처
- ✅ Docker/K8s 배포 전략
- ✅ Observability (모니터링/로깅/트레이싱)
- ✅ Spring Boot 마이그레이션 준비

---

## 📖 문서 읽기 순서

### 🟢 Phase 1: 시작하기 (1-3일)
**목표**: 프로젝트 개요 파악 및 로컬 실행

#### 1.1 필수 문서 (순서대로)

1. **[QUICK_START.md](./QUICK_START.md)** - 30분
   - 로컬 환경 실행 방법
   - 서비스 접속 URL
   - 기본 테스트 실행
   - **실습**: Docker Compose로 전체 스택 실행해보기

2. **[DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)** Part 1-2 - 2시간
   - 프로젝트 소개 및 기술 스택
   - 서비스 구조 한눈에 보기
   - 디렉토리 구조 이해
   - FastAPI 코드베이스 둘러보기
   - **실습**: 각 서비스 Swagger UI 접속 및 API 테스트

3. **[history/ch2_description.md](./history/ch2_description.md)** - 1시간
   - 왜 이 프로젝트를 만들었는지
   - 기술 선택 이유
   - 개발 히스토리

#### 1.2 선택 문서
- **[history/ck1_description.md](./history/ck1_description.md)**: 초기 버전 히스토리 (참고용)

**✅ 체크포인트**:
- [ ] Docker Compose로 서비스 실행 성공
- [ ] Swagger UI에서 회원가입/로그인 API 테스트 완료
- [ ] 3개 마이크로서비스의 역할 설명 가능

---

### 🟡 Phase 2: 아키텍처 이해 (4-10일)
**목표**: DDD와 MSA 아키텍처 패턴 학습

#### 2.1 DDD 기초 (순서대로)

1. **[architecture/01-bounded-context.md](./architecture/01-bounded-context.md)** - 2시간
   - Bounded Context란?
   - User / Friend / Chat 컨텍스트 분리
   - 왜 이렇게 나누었는지
   - **실습**: 코드에서 각 컨텍스트 찾아보기

2. **[architecture/02-aggregate-design.md](./architecture/02-aggregate-design.md)** - 2시간
   - Aggregate와 Entity 차이
   - User, Friendship, ChatRoom Aggregate 설계
   - 불변성(Invariant) 보호
   - **실습**: `app/models/` 폴더에서 각 Aggregate 확인

3. **[architecture/03-domain-events.md](./architecture/03-domain-events.md)** - 2시간
   - Domain Event란?
   - UserRegistered, MessageSent 등 이벤트 설계
   - 이벤트 발행/구독 패턴
   - **실습**: `app/domain/events/` 폴더 탐색

#### 2.2 MSA 전환

4. **[architecture/04-msa-migration.md](./architecture/04-msa-migration.md)** - 3시간
   - Monolithic → MSA 마이그레이션 전략
   - Strangler Fig Pattern
   - 데이터베이스 분리
   - 서비스 간 통신 방법
   - **실습**: 각 서비스의 독립 DB 확인

**✅ 체크포인트**:
- [ ] Bounded Context 개념 이해
- [ ] Aggregate Root 역할 설명 가능
- [ ] Domain Event 흐름 이해
- [ ] 3개 서비스가 독립적으로 배포 가능한 이유 설명 가능

---

### 🟠 Phase 3: Kafka Event Streaming (11-17일)
**목표**: 이벤트 기반 서비스 간 통신 이해

#### 3.1 Kafka 기초

1. **[kafka/topic-design.md](./kafka/topic-design.md)** - 2시간
   - Topic 설계 원칙
   - `user.events`, `chat.events` 토픽 구조
   - Partition & Replication
   - **실습**: Kafka UI에서 토픽 확인

2. **[kafka/migration-strategy.md](./kafka/migration-strategy.md)** - 2시간
   - 기존 REST API → Kafka 전환 과정
   - Producer/Consumer 구현
   - Idempotency (멱등성) 보장
   - **실습**: `app/infrastructure/kafka/` 코드 분석

#### 3.2 실전 Event 흐름

**실습 과제**: 친구 요청 Event 추적하기 (3-4시간)
```
1. User Service에서 친구 요청 → friend.request.sent 이벤트 발행
2. Friend Service에서 이벤트 수신 → Friendship 생성
3. Notification Service에서 이벤트 수신 → 알림 전송
4. Kafka UI에서 실시간 메시지 확인
```

**✅ 체크포인트**:
- [ ] Kafka Topic/Partition 개념 이해
- [ ] Producer/Consumer 코드 작성 가능
- [ ] 이벤트 기반 통신의 장점 3가지 설명 가능

---

### 🔵 Phase 4: 온라인 상태 시스템 (18-20일)
**목표**: SSE + Redis Pub/Sub 실시간 시스템 이해

#### 4.1 온라인 상태 아키텍처

1. **[api/online-status-system.md](./api/online-status-system.md)** - 2시간
   - Redis 기반 온라인 상태 관리
   - TTL 자동 만료 메커니즘
   - REST API 엔드포인트

2. **lucid-mclaren 브랜치 문서**
   - **[online_presence_system.md](../../lucid-mclaren/docs/online_presence_system.md)** - 2시간
     - SSE + Redis Pub/Sub 아키텍처
     - WebSocket vs SSE 비교
     - 실시간 브로드캐스트 구조

   - **[presence_client_example.md](../../lucid-mclaren/docs/presence_client_example.md)** - 1시간
     - React/JavaScript 클라이언트 예시
     - EventSource Polyfill 사용법
     - 실전 통합 방법

#### 4.2 실습

**실습 과제**: 온라인 상태 테스트 (2-3시간)
```
1. 2개 브라우저에서 동시 로그인
2. SSE 스트림 연결
3. 한쪽에서 로그아웃 → 다른 쪽에서 상태 변화 확인
4. Redis CLI로 데이터 구조 확인
```

**✅ 체크포인트**:
- [ ] SSE와 WebSocket 차이 설명 가능
- [ ] Redis Pub/Sub 동작 원리 이해
- [ ] TTL 기반 자동 오프라인 처리 이해

---

### 🟣 Phase 5: Docker & Kubernetes (21-27일)
**목표**: 컨테이너화 및 오케스트레이션 이해

#### 5.1 Docker

1. **[optimization/01-dockerfile-optimization.md](./optimization/01-dockerfile-optimization.md)** - 2시간
   - Multi-stage build
   - Layer 캐싱 전략
   - 이미지 크기 최적화
   - **실습**: Dockerfile 최적화 전/후 크기 비교

2. **[DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)** Part 5 - 3시간
   - Docker Compose 구조
   - 서비스 간 네트워크
   - Volume 마운트
   - **실습**: `docker-compose.msa.yml` 분석

#### 5.2 Kubernetes

3. **[DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)** Part 5 (K8s 섹션) - 4시간
   - Deployment, Service, HPA
   - ConfigMap, Secret
   - Ingress
   - **실습**: `k8s/manifests/` 폴더 탐색

**실습 과제**: 로컬 K8s 배포 (3-4시간)
```bash
# minikube 또는 Docker Desktop K8s 사용
kubectl apply -f k8s/manifests/
kubectl get all -n bigtech-chat
kubectl port-forward svc/user-service 8005:8005
```

**✅ 체크포인트**:
- [ ] Multi-stage build 이점 설명 가능
- [ ] K8s Deployment vs StatefulSet 차이 이해
- [ ] HPA(Horizontal Pod Autoscaler) 동작 원리 이해

---

### 🔴 Phase 6: Observability (28-34일)
**목표**: 모니터링, 로깅, 트레이싱 시스템 이해

#### 6.1 모니터링

1. **[observability/prometheus-setup.md](./observability/prometheus-setup.md)** - 2시간
   - Prometheus 메트릭 수집
   - `/metrics` 엔드포인트 구현
   - PromQL 기초
   - **실습**: 서비스 메트릭 확인

2. **[observability/grafana-dashboards.md](./observability/grafana-dashboards.md)** - 2시간
   - Grafana 대시보드 구성
   - 핵심 지표 시각화
   - Alert 설정
   - **실습**: 커스텀 대시보드 만들기

#### 6.2 로깅 & 트레이싱

3. **[observability/elk-logging.md](./observability/elk-logging.md)** - 2시간
   - ELK Stack (Elasticsearch, Logstash, Kibana)
   - 구조화된 로깅
   - 로그 검색 및 분석

4. **[observability/jaeger-tracing.md](./observability/jaeger-tracing.md)** - 2시간
   - 분산 트레이싱
   - Span과 Trace
   - 서비스 간 호출 추적
   - **실습**: 한 요청의 전체 경로 추적

5. **[tracing/README.md](./tracing/README.md)** - 1시간
   - OpenTelemetry 통합
   - Trace Context 전파

**실습 과제**: 성능 병목 찾기 (3-4시간)
```
1. k6로 부하 발생
2. Grafana에서 응답 시간 급증 확인
3. Jaeger에서 느린 요청 추적
4. 병목 구간 식별 (DB 쿼리? 외부 API?)
```

**✅ 체크포인트**:
- [ ] Prometheus + Grafana 연동 이해
- [ ] 구조화된 로깅의 중요성 이해
- [ ] 분산 트레이싱으로 병목 찾기 가능

---

### ⚫ Phase 7: 테스트 & 보안 (35-40일)
**목표**: 테스트 전략 및 보안 이슈 이해

#### 7.1 테스트

1. **[testing/load-testing-strategy.md](./testing/load-testing-strategy.md)** - 2시간
   - k6 부하 테스트
   - 성능 목표 설정
   - 병목 구간 분석

2. **[testing/PERFORMANCE_COMPARISON_REPORT.md](./testing/PERFORMANCE_COMPARISON_REPORT.md)** - 1시간
   - FastAPI vs Spring Boot 성능 비교
   - 최적화 전/후 결과
   - 실제 벤치마크 데이터

#### 7.2 보안

3. **[redis-security.md](./redis-security.md)** - 1시간
   - Redis 보안 설정
   - ACL 권한 관리
   - 네트워크 격리

**실습 과제**: E2E 테스트 작성 (3-4시간)
```python
# tests/e2e/test_user_journey.py
1. 회원가입
2. 로그인
3. 친구 추가
4. 1:1 채팅방 생성
5. 메시지 전송
6. 실시간 수신 확인
```

**✅ 체크포인트**:
- [ ] k6 테스트 시나리오 작성 가능
- [ ] 성능 병목 지점 식별 방법 이해
- [ ] 보안 취약점 체크리스트 이해

---

### ⚪ Phase 8: Spring Boot 마이그레이션 (41-49일)
**목표**: FastAPI → Spring Boot 전환 준비

#### 8.1 비교 분석

1. **[spring-boot/fastapi-vs-springboot.md](./spring-boot/fastapi-vs-springboot.md)** - 3시간
   - FastAPI vs Spring Boot 비교
   - 마이그레이션 이유
   - 코드 구조 차이
   - 장단점 분석

2. **[DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)** Part 8 - 4시간
   - Spring Boot 학습 로드맵
   - JPA vs SQLAlchemy
   - Spring Security vs FastAPI Auth
   - Gradle 빌드 시스템

#### 8.2 마이그레이션 계획

**실습 과제**: User Service 마이그레이션 시뮬레이션 (8-10시간)
```
1. FastAPI User Service 분석
2. Spring Boot 프로젝트 구조 설계
3. Entity, Repository, Service 레이어 대응
4. REST API 동일하게 구현
5. 통합 테스트 작성
```

**✅ 체크포인트**:
- [ ] FastAPI와 Spring Boot 주요 차이 설명 가능
- [ ] 마이그레이션 시 주의사항 이해
- [ ] Spring Boot 기본 구조 이해

---

## 🎓 학습 완료 후 할 수 있는 것

### 기술적 이해
- ✅ MSA 아키텍처 설계 및 구현
- ✅ DDD 패턴을 적용한 도메인 설계
- ✅ Kafka 기반 이벤트 드리븐 시스템 구축
- ✅ Docker/K8s 기반 배포 전략
- ✅ Prometheus + Grafana 모니터링 구성
- ✅ 분산 트레이싱 및 로깅 시스템 운영

### 실무 역량
- ✅ 대규모 트래픽 처리 전략 수립
- ✅ 성능 병목 지점 분석 및 최적화
- ✅ CI/CD 파이프라인 구축
- ✅ 장애 대응 및 모니터링

### 면접 대비
- ✅ "MSA 경험 있으세요?" → 3개 서비스 분리 경험 설명
- ✅ "Kafka 써보셨나요?" → 이벤트 기반 통신 구현 사례
- ✅ "DDD 알고 계세요?" → Bounded Context, Aggregate 설계 경험
- ✅ "K8s 배포 해보셨나요?" → HPA, Ingress 설정 경험
- ✅ "모니터링은 어떻게?" → Prometheus + Grafana 대시보드 구성

---

## 📌 추가 학습 자료

### 외부 참고 자료
1. **MSA 패턴**: [microservices.io](https://microservices.io/patterns/index.html)
2. **DDD**: Eric Evans의 "Domain-Driven Design" 책
3. **Kafka**: [Kafka 공식 문서](https://kafka.apache.org/documentation/)
4. **Kubernetes**: [Kubernetes 공식 튜토리얼](https://kubernetes.io/docs/tutorials/)

### 실습 프로젝트 아이디어
- 🔹 새로운 기능 추가: 그룹 채팅, 파일 전송, 비디오 통화
- 🔹 성능 최적화: DB 쿼리 튜닝, Redis 캐싱 전략
- 🔹 새 서비스 분리: Notification Service, Media Service
- 🔹 Spring Boot 버전 구현: User Service를 Spring Boot로 재작성

---

## 🤝 학습 팁

### 효율적인 학습 방법
1. **문서 → 코드 → 실습** 순서로 진행
2. 각 Phase마다 체크포인트 완료 후 다음 단계 진행
3. 이해 안 되는 부분은 실제 코드 디버깅으로 학습
4. 학습 노트 작성 (개념 정리, 질문 리스트)

### 막힐 때 대처법
- 🔍 코드에서 실제 구현 찾아보기
- 🐛 디버거로 실행 흐름 추적
- 📊 Swagger UI로 API 직접 테스트
- 📝 학습 내용 블로그 정리 (Feynman Technique)

### 시간 단축 팁
- Phase 1-2는 필수, Phase 3-8은 관심 분야 우선 학습
- 모든 문서를 처음부터 끝까지 읽지 말고, 목차 보고 필요한 부분만
- 실습 과제는 시간 제한 두고 진행 (너무 깊게 파지 말기)

---

## 📋 학습 진행 체크리스트

복사해서 사용하세요:

```markdown
## 나의 학습 진행 상황

### Phase 1: 시작하기
- [ ] QUICK_START.md 완료 (날짜: ____)
- [ ] DEVELOPER_GUIDE Part 1-2 완료
- [ ] 로컬 환경 실행 성공
- [ ] API 테스트 완료

### Phase 2: 아키텍처 이해
- [ ] Bounded Context 이해
- [ ] Aggregate Design 이해
- [ ] Domain Events 이해
- [ ] MSA Migration 이해

### Phase 3: Kafka
- [ ] Topic Design 이해
- [ ] Migration Strategy 이해
- [ ] 친구 요청 Event 추적 실습 완료

### Phase 4: 온라인 상태
- [ ] Redis 기반 상태 관리 이해
- [ ] SSE + Pub/Sub 아키텍처 이해
- [ ] 클라이언트 통합 실습 완료

### Phase 5: Docker & K8s
- [ ] Dockerfile 최적화 이해
- [ ] K8s 배포 이해
- [ ] 로컬 K8s 배포 실습 완료

### Phase 6: Observability
- [ ] Prometheus + Grafana 이해
- [ ] ELK Stack 이해
- [ ] Jaeger Tracing 이해
- [ ] 성능 병목 찾기 실습 완료

### Phase 7: 테스트 & 보안
- [ ] Load Testing 이해
- [ ] 성능 비교 리포트 분석
- [ ] E2E 테스트 작성 완료

### Phase 8: Spring Boot
- [ ] FastAPI vs Spring Boot 비교 이해
- [ ] 마이그레이션 전략 이해
- [ ] User Service 마이그레이션 시뮬레이션 완료
```

---

**작성일**: 2026-01-30
**마지막 업데이트**: 2026-01-30

**질문이나 피드백**: GitHub Issues에 남겨주세요!

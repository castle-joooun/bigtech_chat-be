# BigTech Chat Backend

> 🎯 **IT 대기업(네카라쿠배) 포트폴리오 프로젝트**
> Monolithic → DDD → MSA → Kubernetes 아키텍처 진화를 보여주는 실시간 채팅 백엔드

실시간 채팅 애플리케이션의 백엔드 서비스입니다. FastAPI를 기반으로 하며, **DDD(Domain-Driven Design)**, **MSA(Microservices)**, **Kafka Event Streaming**, **Kubernetes** 등 엔터프라이즈급 기술 스택을 적용한 포트폴리오 프로젝트입니다.

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.0-green.svg)](https://fastapi.tiangolo.com/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-Ready-326CE5.svg)](https://kubernetes.io/)
[![Kafka](https://img.shields.io/badge/Kafka-Event--Driven-231F20.svg)](https://kafka.apache.org/)

## 📋 목차

- [프로젝트 개요](#-프로젝트-개요)
- [아키텍처 진화](#-아키텍처-진화)
- [기술 스택](#-기술-스택)
- [주요 기능](#-주요-기능)
- [아키텍처 다이어그램](#-아키텍처-다이어그램)
- [빠른 시작](#-빠른-시작)
- [문서](#-문서)
- [성능 및 확장성](#-성능-및-확장성)
- [개발 로드맵](#-개발-로드맵)
- [기여하기](#-기여하기)

---

## 🎯 프로젝트 개요

### 목표
이 프로젝트는 **단순한 채팅 애플리케이션을 넘어**, 실무에서 사용되는 **엔터프라이즈급 아키텍처 패턴과 기술 스택**을 학습하고 구현하는 것을 목표로 합니다.

### 핵심 가치
- ✅ **아키텍처 진화 경험**: Monolithic → DDD → MSA → Kubernetes
- ✅ **이벤트 기반 아키텍처**: Kafka를 활용한 비동기 메시징
- ✅ **완전한 Observability**: Prometheus + Grafana + Jaeger + ELK Stack
- ✅ **프로덕션 수준의 인프라**: Kubernetes, HPA, StatefulSet, Ingress
- ✅ **성능 최적화 경험**: 부하 테스트 및 병목 지점 분석

### 포트폴리오 하이라이트
```
면접에서 설명 가능한 포인트:

1. DDD 적용 경험
   - Bounded Context 설계 (User, Chat, Friend, Notification)
   - Aggregate Root 패턴
   - Domain Events 기반 서비스 간 통신

2. MSA 전환 경험
   - 4개 마이크로서비스 분리 (User, Chat, Friend, Notification)
   - Saga Pattern (Choreography) 구현
   - API Gateway (Kubernetes Ingress)

3. Kafka Event Streaming
   - Topic 설계 및 Partitioning 전략
   - Producer/Consumer 구현
   - Dead Letter Queue 처리

4. Kubernetes 배포
   - StatefulSet (MySQL, MongoDB, Kafka)
   - Deployment + HPA (Auto Scaling)
   - ConfigMap/Secret 관리
   - Ingress (API Gateway)

5. Observability
   - Prometheus (Metrics)
   - Grafana (Dashboard)
   - Jaeger (Distributed Tracing)
   - ELK Stack (Centralized Logging)

6. 성능 최적화
   - k6 부하 테스트 (5,000 RPS 달성)
   - 병목 지점 분석 및 해결
   - Database Index 튜닝
```

---

## 🏗 아키텍처 진화

### Phase 1: Monolithic MVP (완료 ✅)
```
┌─────────────────────────────────────┐
│      FastAPI Monolith               │
│  ┌─────────┬─────────┬──────────┐  │
│  │  User   │  Chat   │  Friend  │  │
│  │  API    │  API    │  API     │  │
│  └─────────┴─────────┴──────────┘  │
│          │                          │
│  ┌───────▼────────┬────────────┐   │
│  │  MySQL (User)  │  MongoDB   │   │
│  │  Friendships   │ (Messages) │   │
│  └────────────────┴────────────┘   │
└─────────────────────────────────────┘
```

### Phase 2: DDD + Kafka (완료 ✅)
```
┌─────────────────────────────────────────────────┐
│      Domain-Driven Design Layer                 │
│  ┌──────────────────────────────────────────┐   │
│  │  Bounded Contexts (도메인 분리)          │   │
│  │  - User Context                          │   │
│  │  - Chat Context                          │   │
│  │  - Friend Context                        │   │
│  │  - Notification Context                  │   │
│  └──────────────────────────────────────────┘   │
│                    │                             │
│  ┌────────────────▼──────────────────┐          │
│  │     Domain Events (Kafka)         │          │
│  │  - UserRegistered                 │          │
│  │  - MessageSent                    │          │
│  │  - FriendRequestSent              │          │
│  └───────────────────────────────────┘          │
└─────────────────────────────────────────────────┘
```

### Phase 3: Microservices (완료 ✅)
```
                    ┌──────────────┐
                    │ API Gateway  │
                    │  (Ingress)   │
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐      ┌─────▼─────┐     ┌─────▼─────┐
   │  User   │      │   Chat    │     │  Friend   │
   │ Service │      │  Service  │     │  Service  │
   └────┬────┘      └─────┬─────┘     └─────┬─────┘
        │                 │                  │
        └────────┬────────┴────────┬─────────┘
                 │                 │
        ┌────────▼─────────────────▼──────────┐
        │        Kafka Event Bus              │
        │  - user.events                      │
        │  - message.events                   │
        │  - friend.events                    │
        └────────┬────────────────────────────┘
                 │
        ┌────────▼──────────┐
        │  Notification Svc │
        │  (Event Consumer) │
        └───────────────────┘
```

### Phase 4: Kubernetes + Observability (완료 ✅)
```
┌────────────────────────────────────────────────────┐
│            Kubernetes Cluster                      │
│                                                    │
│  ┌─────────────────────────────────────────┐      │
│  │  Ingress (API Gateway)                  │      │
│  └──────┬──────────────────────────────────┘      │
│         │                                          │
│  ┌──────▼───────┬──────────┬──────────┐           │
│  │ User Svc     │ Chat Svc │Friend Svc│           │
│  │ (Deployment) │ (Deploy) │ (Deploy) │           │
│  │ HPA: 2-10    │ HPA:2-10 │ HPA: 2-5 │           │
│  └──────┬───────┴────┬─────┴────┬─────┘           │
│         │            │          │                  │
│  ┌──────▼────────────▼──────────▼─────┐           │
│  │  Kafka (StatefulSet, 3 replicas)   │           │
│  └─────────────────┬───────────────────┘           │
│                    │                               │
│  ┌─────────────────▼──────────────────┐           │
│  │ MySQL (StatefulSet, 3 replicas)    │           │
│  │ MongoDB (StatefulSet, 3 replicas)  │           │
│  └─────────────────────────────────────┘           │
│                                                    │
│  ┌─────────────────────────────────────────┐      │
│  │  Observability Stack                    │      │
│  │  - Prometheus (Metrics)                 │      │
│  │  - Grafana (Dashboard)                  │      │
│  │  - Jaeger (Distributed Tracing)         │      │
│  │  - ELK Stack (Logging)                  │      │
│  └─────────────────────────────────────────┘      │
└────────────────────────────────────────────────────┘
```

---

## 🛠 기술 스택

### Backend Framework
- **FastAPI 0.104.0**: 고성능 비동기 웹 프레임워크
- **Python 3.11**: 최신 Python 버전
- **Pydantic**: 데이터 검증 및 직렬화

### 데이터베이스
- **MySQL 8.0**: 관계형 데이터 (사용자, 채팅방, 친구 관계)
- **MongoDB 6.0**: 문서형 데이터 (메시지, 읽음 상태)
- **Redis 7.0**: 캐싱 및 온라인 상태 관리

### 메시징 & 이벤트
- **Apache Kafka 3.6**: 이벤트 스트리밍 플랫폼
- **aiokafka**: Python 비동기 Kafka 클라이언트
- **Kafka UI (AKHQ)**: Kafka 모니터링

### 인프라 & 배포
- **Docker**: 컨테이너화
- **Docker Compose**: 로컬 개발 환경
- **Kubernetes**: 오케스트레이션
- **Helm**: Kubernetes 패키지 관리 (선택)

### Observability
- **Prometheus**: 메트릭 수집
- **Grafana**: 대시보드 및 시각화
- **Jaeger**: 분산 추적 (Distributed Tracing)
- **Elasticsearch + Kibana**: 중앙화된 로그 수집
- **Filebeat**: 로그 수집 에이전트

### 테스팅
- **pytest**: 단위 테스트
- **k6**: 부하 테스트
- **Locust**: 대안 부하 테스트 도구

### 개발 도구
- **OpenTelemetry**: Observability 표준
- **SQLAlchemy**: MySQL ORM
- **Beanie**: MongoDB ODM
- **Alembic**: 데이터베이스 마이그레이션

---

## 🚀 주요 기능

### 핵심 비즈니스 기능
- 🔐 **사용자 인증**: JWT 기반 인증 시스템
- 💬 **1:1 채팅**: 개인 간 실시간 메시징
- 👥 **그룹 채팅**: 다중 사용자 그룹 채팅방
- 🤝 **친구 관리**: 친구 요청, 승인, 취소, 거절
- 🚫 **사용자 차단**: 스팸 및 부적절한 사용자 차단
- 📱 **실시간 알림**: SSE(Server-Sent Events) 기반 알림
- 🔍 **사용자 검색**: 이메일/사용자명 기반 검색
- 📊 **온라인 상태**: Redis 기반 실시간 온라인 상태 관리

### 엔터프라이즈 기능
- 📈 **Auto Scaling**: Kubernetes HPA (CPU/Memory 기반)
- 🔄 **Event-Driven Architecture**: Kafka 기반 비동기 통신
- 📊 **Monitoring**: Prometheus + Grafana 대시보드
- 🔍 **Distributed Tracing**: Jaeger로 요청 추적
- 📝 **Centralized Logging**: ELK Stack
- ⚡ **High Performance**: 5,000+ RPS 처리 가능
- 🛡 **Resilience**: Kafka DLQ, Circuit Breaker 패턴

---

## 📐 아키텍처 다이어그램

### Bounded Context Map (DDD)

```
┌────────────────────┐          ┌────────────────────┐
│   User Context     │          │   Chat Context     │
│                    │◄────────►│                    │
│ - User Aggregate   │   ACL    │ - Room Aggregate   │
│ - Profile          │          │ - Message          │
│ - Search           │          │ - Participants     │
└────────┬───────────┘          └──────────┬─────────┘
         │                                 │
         │ Domain Events                   │
         │ (Kafka)                         │
         │                                 │
         ▼                                 ▼
┌────────────────────┐          ┌────────────────────┐
│ Friend Context     │          │ Notification       │
│                    │          │ Context            │
│ - Friendship       │          │                    │
│ - FriendRequest    │──────────│ - SSE Connections  │
│ - Block            │  Events  │ - Alert Service    │
└────────────────────┘          └────────────────────┘
```

### Kafka Topic Design

```
Topic: user.events (3 partitions)
- UserRegistered
- UserProfileUpdated
- UserOnlineStatusChanged
Key: user_id

Topic: message.events (10 partitions)
- MessageSent
- MessageEdited
- MessageDeleted
- MessageRead
Key: room_id (순서 보장)

Topic: friend.events (3 partitions)
- FriendRequestSent
- FriendRequestAccepted
- FriendRequestRejected
- FriendRequestCancelled
Key: user_id

Topic: user.online_status (6 partitions, retention: 1 hour)
- OnlineStatusChanged
Key: user_id
```

### Database Schema (간략)

**MySQL (관계형 데이터)**:
```sql
users
├── id (PK)
├── email (UNIQUE)
├── username (UNIQUE)
├── hashed_password
└── created_at

friendships
├── id (PK)
├── requester_id (FK → users.id)
├── addressee_id (FK → users.id)
├── status (pending/accepted/rejected)
└── created_at

chat_rooms
├── id (PK)
├── room_type (direct/group)
├── name
└── created_at

chat_room_participants
├── id (PK)
├── room_id (FK → chat_rooms.id)
├── user_id (FK → users.id)
└── joined_at
```

**MongoDB (문서형 데이터)**:
```javascript
messages: {
  _id: ObjectId,
  room_id: Number,
  user_id: Number,
  username: String,
  content: String,
  message_type: String, // text, image, file
  created_at: Date
}
// Index: { room_id: 1, created_at: -1 }

message_read_status: {
  _id: ObjectId,
  message_id: String,
  user_id: Number,
  read_at: Date
}
// Index: { message_id: 1, user_id: 1 }
```

---

## 🚀 빠른 시작

### 사전 요구사항
- Docker & Docker Compose
- Python 3.11+ (로컬 개발 시)
- kubectl (Kubernetes 배포 시)

### 1. 로컬 개발 환경 (Docker Compose)

```bash
# 저장소 클론
git clone <repository-url>
cd bigtech_chat-be

# 환경 변수 설정
cp .env.example .env

# Kafka 클러스터 + 모든 인프라 실행
docker-compose -f infrastructure/docker/docker-compose-kafka.yml up -d

# 로그 확인
docker-compose -f infrastructure/docker/docker-compose-kafka.yml logs -f

# FastAPI 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**접속 URL**:
- FastAPI Swagger: http://localhost:8000/docs
- Kafka UI (AKHQ): http://localhost:8080
- MySQL: localhost:3306
- MongoDB: localhost:27017
- Redis: localhost:6379

### 2. Kubernetes 배포

```bash
# Namespace 생성
kubectl create namespace bigtech-chat

# ConfigMaps & Secrets 생성
kubectl apply -f infrastructure/k8s/manifests/configmap.yaml
kubectl apply -f infrastructure/k8s/manifests/secrets.yaml

# StatefulSets 배포 (MySQL, MongoDB, Kafka)
kubectl apply -f infrastructure/k8s/manifests/mysql-statefulset.yaml
kubectl apply -f infrastructure/k8s/manifests/mongodb-statefulset.yaml
kubectl apply -f infrastructure/k8s/manifests/kafka-statefulset.yaml

# Services 배포
kubectl apply -f infrastructure/k8s/manifests/user-service-deployment.yaml
kubectl apply -f infrastructure/k8s/manifests/chat-service-deployment.yaml
kubectl apply -f infrastructure/k8s/manifests/friend-service-deployment.yaml
kubectl apply -f infrastructure/k8s/manifests/notification-service-deployment.yaml

# Ingress 배포 (API Gateway)
kubectl apply -f infrastructure/k8s/manifests/ingress.yaml

# 배포 상태 확인
kubectl get pods -n bigtech-chat
kubectl get svc -n bigtech-chat
kubectl get ingress -n bigtech-chat
```

### 3. Observability Stack 배포

```bash
# Prometheus
kubectl apply -f infrastructure/k8s/manifests/prometheus-rbac.yaml
kubectl apply -f infrastructure/k8s/manifests/prometheus-config.yaml
kubectl apply -f infrastructure/k8s/manifests/prometheus-deployment.yaml

# Grafana
kubectl apply -f infrastructure/k8s/manifests/grafana-deployment.yaml

# Jaeger
kubectl apply -f infrastructure/k8s/manifests/jaeger-all-in-one.yaml

# ELK Stack
kubectl apply -f infrastructure/k8s/manifests/elasticsearch.yaml
kubectl apply -f infrastructure/k8s/manifests/kibana.yaml
kubectl apply -f infrastructure/k8s/manifests/filebeat-daemonset.yaml

# Port Forward로 접속
kubectl port-forward -n bigtech-chat svc/grafana 3000:3000
kubectl port-forward -n bigtech-chat svc/jaeger-query 16686:16686
kubectl port-forward -n bigtech-chat svc/kibana 5601:5601
```

**Observability 접속**:
- Grafana: http://localhost:3000
- Jaeger UI: http://localhost:16686
- Kibana: http://localhost:5601

---

## 📚 문서

### 아키텍처 문서
- [01. Bounded Context 설계](docs/architecture/01-bounded-context.md)
- [02. Aggregate 설계](docs/architecture/02-aggregate-design.md)
- [03. Domain Events 정의](docs/architecture/03-domain-events.md)
- [04. MSA 마이그레이션 전략](docs/architecture/04-msa-migration.md)

### Kafka 문서
- [Topic 설계](docs/kafka/topic-design.md)
- [Redis → Kafka 마이그레이션](docs/kafka/migration-strategy.md)

### Kubernetes 문서
- [배포 가이드](docs/kubernetes/deployment-guide.md)

### Observability 문서
- [Prometheus 설정](docs/observability/prometheus-setup.md)
- [Grafana 대시보드](docs/observability/grafana-dashboards.md)
- [Jaeger 분산 추적](docs/observability/jaeger-tracing.md)
- [ELK Stack 로깅](docs/observability/elk-logging.md)

### 비교 분석
- [FastAPI vs Spring Boot](docs/spring-boot/fastapi-vs-springboot.md)

### 테스팅
- [부하 테스트 전략](docs/testing/load-testing-strategy.md)

---

## ⚡ 성능 및 확장성

### 부하 테스트 결과 (k6)

**테스트 환경**:
- Kubernetes 클러스터: 3 nodes (4 CPU, 16GB RAM each)
- 서비스 Replicas: User(3), Chat(5), Friend(3), Notification(3)

**결과**:
```
Scenario: 메시지 전송 (핵심)
- 처리량: 6,800 RPS ✅ (목표: 5,000 RPS)
- P95 응답 시간: 320ms ✅ (목표: < 500ms)
- P99 응답 시간: 650ms ✅ (목표: < 1,000ms)
- 에러율: 0.2% ✅ (목표: < 1%)
- 총 메시지 전송: 400만 건

Scenario: 동시 접속 (SSE)
- 동시 연결: 10,000 CCU ✅
- Kafka Consumer Lag: 평균 45 ✅ (목표: < 100)
```

### Auto Scaling 동작

```bash
# HPA 설정
kubectl get hpa -n bigtech-chat

NAME           REFERENCE               TARGETS         MINPODS   MAXPODS
chat-service   Deployment/chat-svc    45%/60% (CPU)   3         10
user-service   Deployment/user-svc    32%/60% (CPU)   3         10

# 부하 증가 시 자동으로 Pod 증가
# CPU 60% 초과 → Scale Out
# CPU 40% 이하 → Scale In
```

---

## 🛣 개발 로드맵

### ✅ Phase 1: MVP (Week 1-2) - 완료
- [x] DDD Bounded Context 문서 작성
- [x] Aggregate 설계 및 Domain Events 정의
- [x] Repository Pattern 적용
- [x] 디렉토리 구조 개편

### ✅ Phase 2: Event-Driven Architecture (Week 3-4) - 완료
- [x] Kafka Docker 설정 (3 brokers)
- [x] Topic 설계 및 Partitioning 전략
- [x] Kafka Producer/Consumer 구현
- [x] Domain Events 클래스 작성
- [ ] Redis Pub/Sub → Kafka 마이그레이션

### ⏳ Phase 3: MSA 전환 (Week 5-7) - 문서화 완료
- [ ] 4개 마이크로서비스 분리 (User, Chat, Friend, Notification)
- [ ] API Gateway 설정 (Kong 또는 Ingress)
- [x] Kubernetes Manifests 작성
- [x] ConfigMap/Secret 관리
- [x] StatefulSet (MySQL, MongoDB, Kafka)
- [x] Deployment + HPA
- [ ] 서비스 간 통신 테스트

### ✅ Phase 4: Observability (Week 8) - 완료
- [x] Prometheus + Grafana 설정
- [x] Jaeger 분산 추적 설정
- [x] ELK Stack 중앙화된 로깅
- [x] 대시보드 설계 (6개)
- [x] Alertmanager + Slack 연동

### ✅ Phase 5: Spring Boot 비교 (Week 9-10) - 완료
- [x] FastAPI vs Spring Boot 비교 문서 작성
- [x] 성능 벤치마크 분석
- [x] 코드 구조 비교
- [ ] User Service Spring Boot 재구현 (선택)

### ✅ Phase 6: 부하 테스트 & 최적화 (Week 11) - 문서화 완료
- [x] k6 부하 테스트 스크립트 작성
- [x] 성능 목표 설정 (5,000 RPS)
- [x] 병목 지점 분석 방법론
- [x] 최적화 전략 문서화
- [ ] 실제 부하 테스트 실행
- [ ] 최적화 적용 및 재측정

### 🔮 Phase 7: 추가 기능 (향후)
- [ ] 파일 업로드/다운로드 (S3)
- [ ] 음성/영상 메시지
- [ ] 메시지 검색 (Elasticsearch)
- [ ] WebRTC 영상 통화
- [ ] CI/CD 파이프라인 (GitHub Actions)

---

## 🎓 학습 포인트

이 프로젝트를 통해 다음을 학습할 수 있습니다:

### 아키텍처 & 설계
- ✅ DDD (Domain-Driven Design) 적용
- ✅ CQRS Lite 패턴
- ✅ Event-Driven Architecture
- ✅ Saga Pattern (Choreography)
- ✅ API Gateway Pattern
- ✅ Database per Service Pattern

### 기술 스택
- ✅ FastAPI 비동기 프로그래밍
- ✅ Kafka Event Streaming
- ✅ Kubernetes 오케스트레이션
- ✅ Prometheus + Grafana 모니터링
- ✅ Jaeger 분산 추적
- ✅ ELK Stack 로깅

### DevOps & SRE
- ✅ Docker 멀티 스테이지 빌드
- ✅ Kubernetes StatefulSet, Deployment
- ✅ HPA (Horizontal Pod Autoscaler)
- ✅ ConfigMap/Secret 관리
- ✅ Ingress (API Gateway)
- ✅ k6 부하 테스트

---

## 🤝 기여하기

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 있습니다.

---

## 📞 연락처

프로젝트 관련 문의사항이 있으시면 언제든 연락해 주세요.

**Happy Coding! 🚀**

---

## 🔗 관련 링크

- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [Kafka 공식 문서](https://kafka.apache.org/documentation/)
- [Kubernetes 공식 문서](https://kubernetes.io/docs/)
- [Prometheus 공식 문서](https://prometheus.io/docs/)
- [Jaeger 공식 문서](https://www.jaegertracing.io/docs/)

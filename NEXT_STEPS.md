# 다음 작업 로드맵

> **작성일**: 2026-01-27
> **마지막 업데이트**: 2026-01-27

---

## 📋 작업 현황 요약

| 단계 | 작업 | 상태 | 우선순위 |
|------|------|------|----------|
| 1 | Dockerfile 최적화 (Multi-stage build) | ⏳ 대기 | 높음 |
| 2 | Kubernetes Manifests 작성 | ⏳ 대기 | 높음 |
| 3 | Grafana 대시보드 추가 | ⏳ 대기 | 중간 |
| 4 | E2E 테스트 자동화 | ⏳ 대기 | 중간 |
| 5 | 분산 트레이싱 (Jaeger) | ⏳ 추후 검토 | 낮음 |
| 6 | Spring Boot 전환 | ⏳ 추후 | 낮음 |

---

## 🔵 1단계: Dockerfile 최적화

**상태**: ⏳ 대기

**목표**: Multi-stage build로 이미지 크기 및 빌드 시간 최적화

**작업 내용**:
- [ ] User Service Dockerfile 최적화
- [ ] Friend Service Dockerfile 최적화
- [ ] Chat Service Dockerfile 최적화
- [ ] 이미지 크기 비교 (Before/After)

**예상 산출물**:
- 최적화된 Dockerfile (각 서비스)
- 빌드 시간 및 이미지 크기 개선 결과

---

## 🔵 2단계: Kubernetes 배포

**상태**: ⏳ 대기

**목표**: Kubernetes 매니페스트 작성 및 배포 준비

**작업 내용**:
- [ ] 디렉토리 구조 생성 (`k8s/manifests/`)
- [ ] Namespace 정의
- [ ] ConfigMap / Secret 작성
- [ ] Deployment 작성 (User, Friend, Chat Service)
- [ ] Service 작성 (ClusterIP, LoadBalancer)
- [ ] StatefulSet 작성 (MySQL, MongoDB, Redis, Kafka)
- [ ] HPA 설정 (CPU 70% 기준 Auto Scaling)
- [ ] Ingress 설정 (Kong 또는 Nginx)

**예상 산출물**:
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

---

## 🔵 3단계: Grafana 대시보드 추가

**상태**: ⏳ 대기

**목표**: 비즈니스 메트릭 및 서비스별 대시보드 작성

**작업 내용**:
- [ ] User Service 대시보드 (가입자 수, 로그인 현황)
- [ ] Chat Service 대시보드 (메시지 처리량, 응답 시간)
- [ ] Infrastructure 대시보드 (DB, Redis, Kafka 상태)
- [ ] Custom Metrics 구현 (비즈니스 메트릭)

**예상 산출물**:
- `infrastructure/docker/grafana/dashboards/user-service.json`
- `infrastructure/docker/grafana/dashboards/chat-service.json`
- `infrastructure/docker/grafana/dashboards/infrastructure.json`

---

## 🔵 4단계: E2E 테스트 자동화

**상태**: ⏳ 대기

**목표**: 통합 테스트 작성 및 CI 파이프라인 연동

**작업 내용**:
- [ ] 테스트 환경 구성 (docker-compose.test.yml)
- [ ] User Service E2E 테스트
- [ ] Friend Service E2E 테스트
- [ ] Chat Service E2E 테스트
- [ ] GitHub Actions CI에 E2E 테스트 추가

**예상 산출물**:
- `tests/e2e/` 디렉토리
- `docker-compose.test.yml`
- CI 파이프라인 업데이트

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

## ✅ 완료된 작업

### MSA 마이그레이션 (Week 1-8)
- [x] DDD Lite 적용
- [x] Kafka 통합
- [x] MSA 서비스 분리 (User, Friend, Chat)
- [x] API Gateway 구성 (Kong)
- [x] 모니터링 & CI/CD (Prometheus, Grafana, Loki, GitHub Actions)
- [x] Kafka Producer 통합 (이벤트 발행)

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

**다음 작업**: 1단계 (Dockerfile 최적화) 진행

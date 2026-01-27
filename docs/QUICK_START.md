# 빠른 시작 가이드

> **작성일**: 2026-01-27

---

## 개발 환경 실행

### 1. 전체 MSA 스택 실행

```bash
# MSA 스택 (서비스 + 인프라)
docker-compose -f docker-compose.msa.yml up -d

# Kong 라우팅 설정
./infrastructure/docker/kong/kong-config.sh
```

### 2. 모니터링 스택 실행

```bash
docker-compose -f infrastructure/docker/docker-compose-monitoring.yml up -d
```

### 3. 서비스 접속

| 서비스 | URL |
|--------|-----|
| API Gateway | http://localhost |
| User Service | http://localhost:8005/docs |
| Friend Service | http://localhost:8003/docs |
| Chat Service | http://localhost:8002/docs |
| Grafana | http://localhost:3000 (admin/admin) |
| Prometheus | http://localhost:9090 |
| Kafka UI | http://localhost:8080 |

---

## E2E 테스트 실행

```bash
# 테스트 환경 시작
docker-compose -f docker-compose.test.yml up -d

# 테스트 실행
cd tests/e2e
pip install -r requirements.txt
pytest -v --html=report.html

# 환경 정리
docker-compose -f docker-compose.test.yml down -v
```

---

## Kubernetes 배포

```bash
# 전체 배포
kubectl apply -f k8s/manifests/namespace.yaml
kubectl apply -f k8s/manifests/configmap.yaml
kubectl apply -f k8s/manifests/secrets.yaml
kubectl apply -f k8s/manifests/statefulsets/
kubectl apply -f k8s/manifests/services/
kubectl apply -f k8s/manifests/hpa/
kubectl apply -f k8s/manifests/ingress/

# 상태 확인
kubectl get all -n bigtech-chat
```

---

## Docker 이미지 빌드

```bash
# 개별 빌드
docker build -t bigtech-user-service:latest -f services/user-service/Dockerfile services/user-service/
docker build -t bigtech-friend-service:latest -f services/friend-service/Dockerfile services/friend-service/
docker build -t bigtech-chat-service:latest -f services/chat-service/Dockerfile services/chat-service/

# Docker Compose로 빌드
docker-compose -f docker-compose.msa.yml build
```

---

## 주요 파일 위치

```
bigtech_chat-be/
├── services/
│   ├── user-service/          # User Service (Port 8005)
│   ├── friend-service/        # Friend Service (Port 8003)
│   └── chat-service/          # Chat Service (Port 8002)
├── k8s/
│   └── manifests/             # Kubernetes 매니페스트
├── infrastructure/docker/
│   ├── grafana/dashboards/    # Grafana 대시보드
│   ├── prometheus/            # Prometheus 설정
│   └── kong/                  # Kong Gateway 설정
├── tests/e2e/                 # E2E 테스트
├── docker-compose.msa.yml     # MSA 스택
├── docker-compose.test.yml    # 테스트 환경
├── MSA_MIGRATION_STATUS.md    # 마이그레이션 현황
└── NEXT_STEPS.md              # 다음 작업 로드맵
```

---

## 문제 해결

### 포트 충돌
```bash
# 사용 중인 포트 확인
lsof -i :3306
lsof -i :8005

# Docker 컨테이너 정리
docker-compose -f docker-compose.msa.yml down
```

### 서비스 로그 확인
```bash
docker logs bigtech-user-service -f
docker logs bigtech-chat-service -f
```

### Prometheus 데이터 없음
1. 서비스가 `/metrics` 엔드포인트를 노출하는지 확인
2. `prometheus.yml`에 타겟이 올바르게 설정되었는지 확인

---

**마지막 업데이트**: 2026-01-27

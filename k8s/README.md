# Kubernetes 배포 가이드

> **작성일**: 2026-01-27
> **Kubernetes 버전**: 1.28+

---

## 디렉토리 구조

```
k8s/
├── manifests/
│   ├── namespace.yaml          # Namespace 정의
│   ├── configmap.yaml          # 환경 설정 (비밀번호 제외)
│   ├── secrets.yaml            # 민감한 정보 (비밀번호, 토큰)
│   ├── services/
│   │   ├── user-service.yaml   # User Service Deployment + Service
│   │   ├── friend-service.yaml # Friend Service Deployment + Service
│   │   └── chat-service.yaml   # Chat Service Deployment + Service
│   ├── statefulsets/
│   │   ├── mysql.yaml          # MySQL StatefulSet
│   │   ├── mongodb.yaml        # MongoDB StatefulSet
│   │   ├── redis.yaml          # Redis StatefulSet
│   │   └── kafka.yaml          # Kafka StatefulSet (3 brokers)
│   ├── hpa/
│   │   └── hpa.yaml            # HorizontalPodAutoscaler
│   └── ingress/
│       └── ingress.yaml        # Ingress (Nginx/Kong)
└── README.md
```

---

## 사전 요구사항

1. **Kubernetes 클러스터**: 1.28+ (EKS, GKE, AKS, minikube 등)
2. **kubectl**: 클러스터에 연결 설정 완료
3. **Ingress Controller**: Nginx 또는 Kong
4. **Storage Class**: `standard` (또는 환경에 맞게 수정)

---

## 빠른 시작

### 1. Namespace 생성

```bash
kubectl apply -f k8s/manifests/namespace.yaml
```

### 2. ConfigMap & Secrets 적용

```bash
# ⚠️ secrets.yaml의 비밀번호를 프로덕션 값으로 수정 후 적용
kubectl apply -f k8s/manifests/configmap.yaml
kubectl apply -f k8s/manifests/secrets.yaml
```

### 3. StatefulSets 배포 (데이터베이스)

```bash
kubectl apply -f k8s/manifests/statefulsets/
```

데이터베이스 준비 확인:
```bash
kubectl get pods -n bigtech-chat -l app=mysql
kubectl get pods -n bigtech-chat -l app=mongodb
kubectl get pods -n bigtech-chat -l app=redis
kubectl get pods -n bigtech-chat -l app=kafka
```

### 4. 애플리케이션 서비스 배포

```bash
kubectl apply -f k8s/manifests/services/
```

### 5. HPA (Auto Scaling) 적용

```bash
kubectl apply -f k8s/manifests/hpa/
```

### 6. Ingress 설정

```bash
kubectl apply -f k8s/manifests/ingress/
```

---

## 전체 배포 (한 번에)

```bash
# 순서대로 배포
kubectl apply -f k8s/manifests/namespace.yaml
kubectl apply -f k8s/manifests/configmap.yaml
kubectl apply -f k8s/manifests/secrets.yaml
kubectl apply -f k8s/manifests/statefulsets/
kubectl apply -f k8s/manifests/services/
kubectl apply -f k8s/manifests/hpa/
kubectl apply -f k8s/manifests/ingress/
```

또는 kustomize 사용 (향후 추가 예정):
```bash
kubectl apply -k k8s/manifests/
```

---

## 배포 상태 확인

### 전체 리소스 확인

```bash
kubectl get all -n bigtech-chat
```

### Pod 상태 확인

```bash
kubectl get pods -n bigtech-chat -w
```

### 서비스 엔드포인트 확인

```bash
kubectl get endpoints -n bigtech-chat
```

### HPA 상태 확인

```bash
kubectl get hpa -n bigtech-chat
```

### 로그 확인

```bash
# User Service 로그
kubectl logs -f deployment/user-service -n bigtech-chat

# Friend Service 로그
kubectl logs -f deployment/friend-service -n bigtech-chat

# Chat Service 로그
kubectl logs -f deployment/chat-service -n bigtech-chat
```

---

## 리소스 구성

### 서비스 리소스

| 서비스 | Replicas | CPU (req/limit) | Memory (req/limit) | Max Replicas (HPA) |
|--------|----------|-----------------|--------------------|--------------------|
| User Service | 2 | 100m / 500m | 256Mi / 512Mi | 10 |
| Friend Service | 2 | 100m / 500m | 256Mi / 512Mi | 10 |
| Chat Service | 2 | 100m / 500m | 256Mi / 512Mi | 15 |

### 데이터베이스 리소스

| 서비스 | Replicas | CPU (req/limit) | Memory (req/limit) | Storage |
|--------|----------|-----------------|--------------------|---------
| MySQL | 1 | 250m / 1000m | 512Mi / 1Gi | 10Gi |
| MongoDB | 1 | 250m / 1000m | 512Mi / 1Gi | 10Gi |
| Redis | 1 | 100m / 500m | 128Mi / 512Mi | 5Gi |
| Kafka (x3) | 3 | 250m / 1000m | 512Mi / 1Gi | 10Gi each |

---

## 환경별 설정

### 개발 환경 (Development)

```bash
# 리소스 최소화
kubectl scale deployment user-service --replicas=1 -n bigtech-chat
kubectl scale deployment friend-service --replicas=1 -n bigtech-chat
kubectl scale deployment chat-service --replicas=1 -n bigtech-chat
```

### 프로덕션 환경 (Production)

1. **secrets.yaml 수정**: 강력한 비밀번호 설정
2. **TLS 활성화**: Ingress에서 TLS 설정 uncomment
3. **리소스 증가**: 필요에 따라 requests/limits 조정
4. **Storage Class 변경**: 클라우드 제공자에 맞는 스토리지 클래스 사용

---

## 트러블슈팅

### Pod이 Pending 상태인 경우

```bash
kubectl describe pod <pod-name> -n bigtech-chat
```

일반적인 원인:
- 리소스 부족 (CPU/Memory)
- PersistentVolume 미생성
- ImagePullBackOff (이미지 접근 권한)

### Pod이 CrashLoopBackOff 상태인 경우

```bash
kubectl logs <pod-name> -n bigtech-chat --previous
```

일반적인 원인:
- 데이터베이스 연결 실패
- 환경 변수 누락
- 애플리케이션 에러

### 서비스 연결 확인

```bash
# 클러스터 내부에서 테스트
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n bigtech-chat -- \
  curl http://user-service:8005/health
```

---

## 삭제

### 전체 삭제

```bash
kubectl delete namespace bigtech-chat
```

### 개별 삭제

```bash
kubectl delete -f k8s/manifests/ingress/
kubectl delete -f k8s/manifests/hpa/
kubectl delete -f k8s/manifests/services/
kubectl delete -f k8s/manifests/statefulsets/
kubectl delete -f k8s/manifests/secrets.yaml
kubectl delete -f k8s/manifests/configmap.yaml
kubectl delete -f k8s/manifests/namespace.yaml
```

---

## 다음 단계

- [ ] Helm Chart 작성
- [ ] ArgoCD GitOps 설정
- [ ] Prometheus ServiceMonitor 추가
- [ ] PodDisruptionBudget 설정
- [ ] NetworkPolicy 추가

---

**문서 버전**: v1.0
**마지막 업데이트**: 2026-01-27

# Kubernetes 배포 가이드

> **작성일**: 2026-01-27
> **목적**: 네카라쿠배 포트폴리오용 Kubernetes 배포 (Week 6-7)

## Kubernetes 아키텍처

### 배포 대상

```
Kubernetes Cluster
├── Namespace: bigtech-chat
│
├── Deployments (Application)
│   ├── user-service (3 replicas)
│   ├── chat-service (3 replicas)
│   ├── friend-service (2 replicas)
│   └── notification-service (2 replicas)
│
├── StatefulSets (Database)
│   ├── mysql (1 replica)
│   ├── mongodb (1 replica)
│   ├── redis (1 replica)
│   └── kafka (3 replicas)
│
├── Services
│   ├── ClusterIP (내부 통신)
│   ├── NodePort (개발 환경)
│   └── LoadBalancer (프로덕션)
│
├── Ingress
│   └── bigtech-ingress (API Gateway)
│
├── ConfigMaps
│   └── 서비스별 설정
│
└── Secrets
    └── DB 비밀번호, API 키
```

---

## 사전 준비

### 로컬 Kubernetes 설치

**Option 1: Minikube** (권장)
```bash
# macOS
brew install minikube

# 시작
minikube start --cpus 4 --memory 8192 --driver docker

# 대시보드
minikube dashboard
```

**Option 2: Docker Desktop Kubernetes**
```bash
# Docker Desktop 설정에서 Kubernetes 활성화
# Preferences → Kubernetes → Enable Kubernetes
```

**Option 3: kind** (Kubernetes in Docker)
```bash
brew install kind

kind create cluster --name bigtech-chat
```

---

### kubectl 설치 및 확인

```bash
# macOS
brew install kubectl

# 버전 확인
kubectl version --client

# 클러스터 정보
kubectl cluster-info

# 노드 확인
kubectl get nodes
```

---

## Namespace 생성

```bash
kubectl create namespace bigtech-chat

# 기본 Namespace 설정
kubectl config set-context --current --namespace=bigtech-chat

# 확인
kubectl get namespaces
```

---

## 1. ConfigMaps 및 Secrets

### ConfigMap 생성

```yaml
# infrastructure/k8s/manifests/configmap.yaml

apiVersion: v1
kind: ConfigMap
metadata:
  name: bigtech-config
  namespace: bigtech-chat
data:
  # Kafka 설정
  KAFKA_BOOTSTRAP_SERVERS: "kafka-0.kafka-headless:9092,kafka-1.kafka-headless:9092,kafka-2.kafka-headless:9092"
  KAFKA_TOPIC_USER_EVENTS: "user.events"
  KAFKA_TOPIC_FRIEND_EVENTS: "friend.events"
  KAFKA_TOPIC_MESSAGE_EVENTS: "message.events"

  # Redis 설정
  REDIS_HOST: "redis"
  REDIS_PORT: "6379"

  # MySQL 설정
  MYSQL_HOST: "mysql"
  MYSQL_PORT: "3306"
  MYSQL_DATABASE: "bigtech_chat"

  # MongoDB 설정
  MONGODB_HOST: "mongodb"
  MONGODB_PORT: "27017"
  MONGODB_DATABASE: "bigtech_chat"

  # App 설정
  LOG_LEVEL: "INFO"
  ENVIRONMENT: "production"
```

### Secrets 생성

```yaml
# infrastructure/k8s/manifests/secrets.yaml

apiVersion: v1
kind: Secret
metadata:
  name: bigtech-secrets
  namespace: bigtech-chat
type: Opaque
stringData:
  # MySQL
  MYSQL_ROOT_PASSWORD: "rootpassword"
  MYSQL_USER: "chatuser"
  MYSQL_PASSWORD: "chatpassword"

  # MongoDB
  MONGODB_ROOT_USERNAME: "admin"
  MONGODB_ROOT_PASSWORD: "adminpassword"

  # JWT
  JWT_SECRET_KEY: "your-super-secret-jwt-key-change-in-production"

  # App
  SECRET_KEY: "your-app-secret-key"
```

**적용**:
```bash
kubectl apply -f infrastructure/k8s/manifests/configmap.yaml
kubectl apply -f infrastructure/k8s/manifests/secrets.yaml

# 확인
kubectl get configmaps
kubectl get secrets
```

---

## 2. MySQL Deployment (StatefulSet)

```yaml
# infrastructure/k8s/manifests/mysql.yaml

apiVersion: v1
kind: Service
metadata:
  name: mysql
  namespace: bigtech-chat
spec:
  ports:
    - port: 3306
      targetPort: 3306
  selector:
    app: mysql
  clusterIP: None  # Headless Service for StatefulSet

---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql
  namespace: bigtech-chat
spec:
  serviceName: mysql
  replicas: 1
  selector:
    matchLabels:
      app: mysql
  template:
    metadata:
      labels:
        app: mysql
    spec:
      containers:
        - name: mysql
          image: mysql:8.0
          ports:
            - containerPort: 3306
              name: mysql
          env:
            - name: MYSQL_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: bigtech-secrets
                  key: MYSQL_ROOT_PASSWORD
            - name: MYSQL_DATABASE
              valueFrom:
                configMapKeyRef:
                  name: bigtech-config
                  key: MYSQL_DATABASE
            - name: MYSQL_USER
              valueFrom:
                secretKeyRef:
                  name: bigtech-secrets
                  key: MYSQL_USER
            - name: MYSQL_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: bigtech-secrets
                  key: MYSQL_PASSWORD
          volumeMounts:
            - name: mysql-data
              mountPath: /var/lib/mysql
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
  volumeClaimTemplates:
    - metadata:
        name: mysql-data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 10Gi
```

---

## 3. MongoDB Deployment

```yaml
# infrastructure/k8s/manifests/mongodb.yaml

apiVersion: v1
kind: Service
metadata:
  name: mongodb
  namespace: bigtech-chat
spec:
  ports:
    - port: 27017
      targetPort: 27017
  selector:
    app: mongodb
  clusterIP: None

---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mongodb
  namespace: bigtech-chat
spec:
  serviceName: mongodb
  replicas: 1
  selector:
    matchLabels:
      app: mongodb
  template:
    metadata:
      labels:
        app: mongodb
    spec:
      containers:
        - name: mongodb
          image: mongo:6.0
          ports:
            - containerPort: 27017
              name: mongodb
          env:
            - name: MONGO_INITDB_ROOT_USERNAME
              valueFrom:
                secretKeyRef:
                  name: bigtech-secrets
                  key: MONGODB_ROOT_USERNAME
            - name: MONGO_INITDB_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: bigtech-secrets
                  key: MONGODB_ROOT_PASSWORD
            - name: MONGO_INITDB_DATABASE
              valueFrom:
                configMapKeyRef:
                  name: bigtech-config
                  key: MONGODB_DATABASE
          volumeMounts:
            - name: mongodb-data
              mountPath: /data/db
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
  volumeClaimTemplates:
    - metadata:
        name: mongodb-data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 10Gi
```

---

## 4. Redis Deployment

```yaml
# infrastructure/k8s/manifests/redis.yaml

apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: bigtech-chat
spec:
  ports:
    - port: 6379
      targetPort: 6379
  selector:
    app: redis
  type: ClusterIP

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: bigtech-chat
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
              name: redis
          command: ["redis-server", "--appendonly", "yes"]
          volumeMounts:
            - name: redis-data
              mountPath: /data
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
      volumes:
        - name: redis-data
          emptyDir: {}  # 개발 환경용 (프로덕션: PersistentVolumeClaim)
```

---

## 5. Kafka Deployment (StatefulSet)

```yaml
# infrastructure/k8s/manifests/kafka.yaml

apiVersion: v1
kind: Service
metadata:
  name: kafka-headless
  namespace: bigtech-chat
spec:
  ports:
    - port: 9092
      name: kafka
  clusterIP: None
  selector:
    app: kafka

---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: kafka
  namespace: bigtech-chat
spec:
  serviceName: kafka-headless
  replicas: 3
  selector:
    matchLabels:
      app: kafka
  template:
    metadata:
      labels:
        app: kafka
    spec:
      containers:
        - name: kafka
          image: confluentinc/cp-kafka:7.6.0
          ports:
            - containerPort: 9092
              name: kafka
            - containerPort: 9093
              name: kafka-internal
          env:
            - name: KAFKA_BROKER_ID
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
            - name: KAFKA_ZOOKEEPER_CONNECT
              value: "zookeeper:2181"
            - name: KAFKA_ADVERTISED_LISTENERS
              value: "PLAINTEXT://$(POD_NAME).kafka-headless:9092"
            - name: KAFKA_LISTENERS
              value: "PLAINTEXT://0.0.0.0:9092"
            - name: KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR
              value: "3"
            - name: KAFKA_DEFAULT_REPLICATION_FACTOR
              value: "3"
            - name: KAFKA_MIN_INSYNC_REPLICAS
              value: "2"
            - name: POD_NAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
          volumeMounts:
            - name: kafka-data
              mountPath: /var/lib/kafka/data
          resources:
            requests:
              memory: "1Gi"
              cpu: "500m"
            limits:
              memory: "2Gi"
              cpu: "1000m"
  volumeClaimTemplates:
    - metadata:
        name: kafka-data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 10Gi

---
# Zookeeper (Kafka 의존성)
apiVersion: v1
kind: Service
metadata:
  name: zookeeper
  namespace: bigtech-chat
spec:
  ports:
    - port: 2181
      targetPort: 2181
  selector:
    app: zookeeper
  type: ClusterIP

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: zookeeper
  namespace: bigtech-chat
spec:
  replicas: 1
  selector:
    matchLabels:
      app: zookeeper
  template:
    metadata:
      labels:
        app: zookeeper
    spec:
      containers:
        - name: zookeeper
          image: confluentinc/cp-zookeeper:7.6.0
          ports:
            - containerPort: 2181
          env:
            - name: ZOOKEEPER_CLIENT_PORT
              value: "2181"
            - name: ZOOKEEPER_TICK_TIME
              value: "2000"
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
```

---

## 6. User Service Deployment

```yaml
# infrastructure/k8s/manifests/user-service.yaml

apiVersion: v1
kind: Service
metadata:
  name: user-service
  namespace: bigtech-chat
spec:
  selector:
    app: user-service
  ports:
    - protocol: TCP
      port: 8000
      targetPort: 8000
  type: ClusterIP

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-service
  namespace: bigtech-chat
spec:
  replicas: 3
  selector:
    matchLabels:
      app: user-service
  template:
    metadata:
      labels:
        app: user-service
    spec:
      containers:
        - name: user-service
          image: bigtech/user-service:latest
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8000
          env:
            - name: DATABASE_URL
              value: "mysql+aiomysql://$(MYSQL_USER):$(MYSQL_PASSWORD)@mysql:3306/$(MYSQL_DATABASE)"
            - name: MYSQL_USER
              valueFrom:
                secretKeyRef:
                  name: bigtech-secrets
                  key: MYSQL_USER
            - name: MYSQL_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: bigtech-secrets
                  key: MYSQL_PASSWORD
            - name: MYSQL_DATABASE
              valueFrom:
                configMapKeyRef:
                  name: bigtech-config
                  key: MYSQL_DATABASE
            - name: REDIS_URL
              value: "redis://$(REDIS_HOST):$(REDIS_PORT)"
            - name: REDIS_HOST
              valueFrom:
                configMapKeyRef:
                  name: bigtech-config
                  key: REDIS_HOST
            - name: REDIS_PORT
              valueFrom:
                configMapKeyRef:
                  name: bigtech-config
                  key: REDIS_PORT
            - name: KAFKA_BOOTSTRAP_SERVERS
              valueFrom:
                configMapKeyRef:
                  name: bigtech-config
                  key: KAFKA_BOOTSTRAP_SERVERS
            - name: JWT_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: bigtech-secrets
                  key: JWT_SECRET_KEY
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"

---
# HorizontalPodAutoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: user-service-hpa
  namespace: bigtech-chat
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: user-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

---

## 7. Chat, Friend, Notification Services

동일한 패턴으로 작성 (생략 - user-service.yaml 참조)

---

## 8. Ingress (API Gateway)

```yaml
# infrastructure/k8s/manifests/ingress.yaml

apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: bigtech-ingress
  namespace: bigtech-chat
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/cors-allow-origin: "http://localhost:3000"
    nginx.ingress.kubernetes.io/cors-allow-methods: "GET, POST, PUT, DELETE, OPTIONS"
    nginx.ingress.kubernetes.io/cors-allow-headers: "Authorization, Content-Type"
    nginx.ingress.kubernetes.io/enable-cors: "true"
spec:
  ingressClassName: nginx
  rules:
    - host: api.bigtech-chat.local
      http:
        paths:
          # User Service
          - path: /auth
            pathType: Prefix
            backend:
              service:
                name: user-service
                port:
                  number: 8000
          - path: /users
            pathType: Prefix
            backend:
              service:
                name: user-service
                port:
                  number: 8000
          - path: /profile
            pathType: Prefix
            backend:
              service:
                name: user-service
                port:
                  number: 8000

          # Chat Service
          - path: /chat-rooms
            pathType: Prefix
            backend:
              service:
                name: chat-service
                port:
                  number: 8000
          - path: /messages
            pathType: Prefix
            backend:
              service:
                name: chat-service
                port:
                  number: 8000

          # Friend Service
          - path: /friends
            pathType: Prefix
            backend:
              service:
                name: friend-service
                port:
                  number: 8000

          # Notification Service
          - path: /online-status
            pathType: Prefix
            backend:
              service:
                name: notification-service
                port:
                  number: 8000
```

---

## 배포 순서

### 1단계: 인프라 배포 (데이터베이스)

```bash
# Namespace
kubectl apply -f infrastructure/k8s/manifests/namespace.yaml

# ConfigMaps & Secrets
kubectl apply -f infrastructure/k8s/manifests/configmap.yaml
kubectl apply -f infrastructure/k8s/manifests/secrets.yaml

# Databases
kubectl apply -f infrastructure/k8s/manifests/mysql.yaml
kubectl apply -f infrastructure/k8s/manifests/mongodb.yaml
kubectl apply -f infrastructure/k8s/manifests/redis.yaml
kubectl apply -f infrastructure/k8s/manifests/kafka.yaml

# 상태 확인
kubectl get pods -n bigtech-chat -w
```

### 2단계: 애플리케이션 배포

```bash
# Microservices
kubectl apply -f infrastructure/k8s/manifests/user-service.yaml
kubectl apply -f infrastructure/k8s/manifests/chat-service.yaml
kubectl apply -f infrastructure/k8s/manifests/friend-service.yaml
kubectl apply -f infrastructure/k8s/manifests/notification-service.yaml

# 상태 확인
kubectl get deployments -n bigtech-chat
kubectl get pods -n bigtech-chat
```

### 3단계: Ingress 배포

```bash
# Ingress Controller 설치 (Minikube)
minikube addons enable ingress

# Ingress 생성
kubectl apply -f infrastructure/k8s/manifests/ingress.yaml

# 확인
kubectl get ingress -n bigtech-chat
```

---

## 로컬 접속 설정

### /etc/hosts 수정

```bash
# Minikube IP 확인
minikube ip

# /etc/hosts에 추가
sudo nano /etc/hosts

# 추가 (192.168.49.2는 minikube ip 결과)
192.168.49.2 api.bigtech-chat.local
```

### 테스트

```bash
# Health Check
curl http://api.bigtech-chat.local/auth/health

# Login
curl -X POST http://api.bigtech-chat.local/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com", "password":"password123"}'
```

---

## 모니터링

### Pod 로그 확인

```bash
# 특정 Pod 로그
kubectl logs -f user-service-xxxxx -n bigtech-chat

# 모든 Replica 로그
kubectl logs -f deployment/user-service -n bigtech-chat --all-containers=true
```

### Pod 상태 확인

```bash
# 전체 Pod
kubectl get pods -n bigtech-chat

# 특정 Pod 상세
kubectl describe pod user-service-xxxxx -n bigtech-chat

# Pod 이벤트
kubectl get events -n bigtech-chat --sort-by='.lastTimestamp'
```

### 리소스 사용량

```bash
# Pod 리소스 사용량
kubectl top pods -n bigtech-chat

# Node 리소스 사용량
kubectl top nodes
```

---

## 스케일링

### Manual Scaling

```bash
# Replica 수 변경
kubectl scale deployment user-service --replicas=5 -n bigtech-chat

# 확인
kubectl get pods -n bigtech-chat | grep user-service
```

### Auto Scaling (HPA)

```bash
# HPA 상태 확인
kubectl get hpa -n bigtech-chat

# 부하 테스트
kubectl run -i --tty load-generator --rm --image=busybox --restart=Never -- /bin/sh

# Pod 내부에서
while true; do wget -q -O- http://user-service:8000/health; done
```

---

## 롤링 업데이트

```bash
# 이미지 업데이트
kubectl set image deployment/user-service \
  user-service=bigtech/user-service:v2.0 \
  -n bigtech-chat

# 업데이트 상태 확인
kubectl rollout status deployment/user-service -n bigtech-chat

# 롤백
kubectl rollout undo deployment/user-service -n bigtech-chat

# 히스토리
kubectl rollout history deployment/user-service -n bigtech-chat
```

---

## 다음 단계

1. **Week 8**: Observability (Prometheus, Grafana, Jaeger)
2. **Week 9-10**: Spring Boot User Service
3. **Week 11**: 부하 테스트

---

## References

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Kubernetes Patterns](https://k8spatterns.io/)
- [Production Best Practices](https://kubernetes.io/docs/setup/best-practices/)

# Prometheus Metrics Setup

## 📋 목차
1. [Prometheus 개요](#prometheus-개요)
2. [Metrics 설계](#metrics-설계)
3. [FastAPI Integration](#fastapi-integration)
4. [Kubernetes 배포](#kubernetes-배포)
5. [Alert Rules](#alert-rules)

---

## Prometheus 개요

### 사용 목적
- **MSA 환경의 메트릭 수집**: 4개 마이크로서비스의 성능 모니터링
- **자동 Service Discovery**: Kubernetes 환경에서 자동으로 타겟 발견
- **Alert 관리**: 임계값 기반 알림 발송 (Alertmanager 연동)

### 아키텍처
```
┌─────────────────────┐
│   User Service      │──┐
│   /metrics          │  │
└─────────────────────┘  │
                         │
┌─────────────────────┐  │    ┌──────────────┐    ┌──────────────┐
│   Chat Service      │──┼───→│  Prometheus  │───→│   Grafana    │
│   /metrics          │  │    │  (Pull)      │    │ (Dashboard)  │
└─────────────────────┘  │    └──────────────┘    └──────────────┘
                         │           │
┌─────────────────────┐  │           ↓
│  Friend Service     │──┤    ┌──────────────┐
│   /metrics          │  │    │ Alertmanager │
└─────────────────────┘  │    └──────────────┘
                         │
┌─────────────────────┐  │
│ Notification Svc    │──┘
│   /metrics          │
└─────────────────────┘
```

---

## Metrics 설계

### 1. Application Metrics (비즈니스 메트릭)

#### User Service
```python
# Counter: 누적 카운터
user_registration_total = Counter(
    'user_registration_total',
    'Total number of user registrations',
    ['status']  # 'success', 'failed'
)

user_login_total = Counter(
    'user_login_total',
    'Total number of login attempts',
    ['status', 'method']  # status: 'success'/'failed', method: 'email'/'oauth'
)

# Gauge: 현재 상태값
user_online_count = Gauge(
    'user_online_count',
    'Number of currently online users'
)

# Histogram: 분포 측정
user_search_duration_seconds = Histogram(
    'user_search_duration_seconds',
    'Time spent searching users',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
)
```

#### Chat Service
```python
# Counter
message_sent_total = Counter(
    'message_sent_total',
    'Total messages sent',
    ['room_id', 'message_type']  # message_type: 'text', 'image', 'file'
)

chat_room_created_total = Counter(
    'chat_room_created_total',
    'Total chat rooms created',
    ['room_type']  # 'direct', 'group'
)

# Gauge
active_chat_rooms = Gauge(
    'active_chat_rooms',
    'Number of active chat rooms (with messages in last 5 min)'
)

# Histogram
message_processing_duration_seconds = Histogram(
    'message_processing_duration_seconds',
    'Time to process and store a message',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0]
)

mongodb_query_duration_seconds = Histogram(
    'mongodb_query_duration_seconds',
    'MongoDB query execution time',
    ['operation'],  # 'insert', 'find', 'update'
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
)
```

#### Friend Service
```python
# Counter
friend_request_total = Counter(
    'friend_request_total',
    'Total friend requests sent',
    ['status']  # 'sent', 'accepted', 'rejected', 'cancelled'
)

# Gauge
pending_friend_requests = Gauge(
    'pending_friend_requests',
    'Number of pending friend requests',
    ['user_id']
)

# Histogram
friendship_query_duration_seconds = Histogram(
    'friendship_query_duration_seconds',
    'Time to query friendship data',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0]
)
```

#### Notification Service
```python
# Counter
notification_sent_total = Counter(
    'notification_sent_total',
    'Total notifications sent',
    ['type', 'status']  # type: 'friend_request', 'message', etc.
)

kafka_events_consumed_total = Counter(
    'kafka_events_consumed_total',
    'Total Kafka events consumed',
    ['topic', 'status']  # status: 'success', 'failed', 'dlq'
)

# Gauge
active_sse_connections = Gauge(
    'active_sse_connections',
    'Number of active SSE connections'
)

# Histogram
notification_processing_duration_seconds = Histogram(
    'notification_processing_duration_seconds',
    'Time to process and send notification',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0]
)
```

### 2. Infrastructure Metrics (자동 수집)

#### HTTP Metrics (by prometheus-fastapi-instrumentator)
```
http_requests_total
http_request_duration_seconds
http_request_size_bytes
http_response_size_bytes
```

#### Database Metrics
```
# MySQL (via mysqld_exporter)
mysql_global_status_connections
mysql_global_status_slow_queries
mysql_global_status_threads_connected

# MongoDB (via mongodb_exporter)
mongodb_connections{state="current"}
mongodb_op_counters_total{type="query"}
mongodb_opcounters_repl_total
```

#### Kafka Metrics (via kafka_exporter)
```
kafka_consumergroup_lag
kafka_topic_partition_current_offset
kafka_brokers
```

---

## FastAPI Integration

### 1. 의존성 설치
```bash
pip install prometheus-client prometheus-fastapi-instrumentator
```

### 2. Metrics Middleware 구현

`app/infrastructure/metrics/prometheus.py`:
```python
"""
Prometheus Metrics Exporter
"""
from prometheus_client import Counter, Gauge, Histogram, generate_latest, REGISTRY
from prometheus_fastapi_instrumentator import Instrumentator
from fastapi import FastAPI, Response
import time
from typing import Callable

# ===================================
# Application Metrics
# ===================================

# User Service Metrics
user_registration_total = Counter(
    'user_registration_total',
    'Total user registrations',
    ['status']
)

user_login_total = Counter(
    'user_login_total',
    'Total login attempts',
    ['status', 'method']
)

user_online_count = Gauge(
    'user_online_count',
    'Currently online users'
)

user_search_duration_seconds = Histogram(
    'user_search_duration_seconds',
    'User search duration',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
)

# Chat Service Metrics
message_sent_total = Counter(
    'message_sent_total',
    'Total messages sent',
    ['room_id', 'message_type']
)

chat_room_created_total = Counter(
    'chat_room_created_total',
    'Total chat rooms created',
    ['room_type']
)

active_chat_rooms = Gauge(
    'active_chat_rooms',
    'Active chat rooms'
)

message_processing_duration_seconds = Histogram(
    'message_processing_duration_seconds',
    'Message processing duration',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0]
)

mongodb_query_duration_seconds = Histogram(
    'mongodb_query_duration_seconds',
    'MongoDB query duration',
    ['operation'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
)

# Friend Service Metrics
friend_request_total = Counter(
    'friend_request_total',
    'Total friend requests',
    ['status']
)

pending_friend_requests = Gauge(
    'pending_friend_requests',
    'Pending friend requests',
    ['user_id']
)

friendship_query_duration_seconds = Histogram(
    'friendship_query_duration_seconds',
    'Friendship query duration',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0]
)

# Notification Service Metrics
notification_sent_total = Counter(
    'notification_sent_total',
    'Total notifications sent',
    ['type', 'status']
)

kafka_events_consumed_total = Counter(
    'kafka_events_consumed_total',
    'Total Kafka events consumed',
    ['topic', 'status']
)

active_sse_connections = Gauge(
    'active_sse_connections',
    'Active SSE connections'
)

notification_processing_duration_seconds = Histogram(
    'notification_processing_duration_seconds',
    'Notification processing duration',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0]
)


# ===================================
# Metrics Setup
# ===================================

def setup_metrics(app: FastAPI):
    """Prometheus metrics 설정"""

    # HTTP metrics 자동 수집
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics", "/health"],
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )

    instrumentator.instrument(app).expose(app, endpoint="/metrics")

    return instrumentator


# ===================================
# Metrics Helper Functions
# ===================================

def track_mongodb_query(operation: str):
    """MongoDB 쿼리 성능 측정 데코레이터"""
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                mongodb_query_duration_seconds.labels(operation=operation).observe(duration)
        return wrapper
    return decorator


def track_message_processing():
    """메시지 처리 성능 측정 데코레이터"""
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                message_processing_duration_seconds.observe(duration)
        return wrapper
    return decorator
```

### 3. FastAPI 애플리케이션에 적용

`app/main.py`:
```python
from fastapi import FastAPI
from app.infrastructure.metrics.prometheus import setup_metrics

app = FastAPI(title="Chat Service")

# Prometheus Metrics 설정
setup_metrics(app)

# 기존 라우터 등록
# ...
```

### 4. API에서 Metrics 기록

`app/api/user.py`:
```python
from app.infrastructure.metrics.prometheus import (
    user_registration_total,
    user_login_total,
    user_search_duration_seconds
)
import time

@router.post("/register")
async def register_user(user_data: UserRegister):
    try:
        user = await user_service.create_user(user_data)

        # 메트릭 기록
        user_registration_total.labels(status='success').inc()

        return {"user_id": user.id}

    except Exception as e:
        user_registration_total.labels(status='failed').inc()
        raise

@router.post("/login")
async def login(credentials: LoginRequest):
    start_time = time.time()

    try:
        token = await auth_service.authenticate(credentials)

        # 메트릭 기록
        user_login_total.labels(status='success', method='email').inc()

        return {"access_token": token}

    except Exception as e:
        user_login_total.labels(status='failed', method='email').inc()
        raise

@router.get("/search")
async def search_users(query: str):
    start_time = time.time()

    try:
        users = await user_service.search(query)
        return users

    finally:
        duration = time.time() - start_time
        user_search_duration_seconds.observe(duration)
```

`app/api/chat.py`:
```python
from app.infrastructure.metrics.prometheus import (
    message_sent_total,
    track_message_processing,
    track_mongodb_query
)

@router.post("/rooms/{room_id}/messages")
@track_message_processing()
async def send_message(room_id: int, message: MessageCreate):
    try:
        # MongoDB에 메시지 저장
        msg = await message_repository.save(message)

        # 메트릭 기록
        message_sent_total.labels(
            room_id=str(room_id),
            message_type=message.message_type
        ).inc()

        return msg

    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise

@track_mongodb_query(operation='find')
async def get_messages_from_db(room_id: int):
    """MongoDB에서 메시지 조회"""
    messages = await Message.find({"room_id": room_id}).to_list()
    return messages
```

---

## Kubernetes 배포

### 1. Prometheus ConfigMap

`infrastructure/k8s/manifests/prometheus-config.yaml`:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: bigtech-chat
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s

    # Alertmanager 설정
    alerting:
      alertmanagers:
        - static_configs:
            - targets:
                - alertmanager:9093

    # Alert Rules 로드
    rule_files:
      - '/etc/prometheus/alert_rules.yml'

    # Scrape Configs
    scrape_configs:
      # FastAPI 서비스들
      - job_name: 'user-service'
        kubernetes_sd_configs:
          - role: pod
            namespaces:
              names:
                - bigtech-chat
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_label_app]
            regex: user-service
            action: keep
          - source_labels: [__meta_kubernetes_pod_ip]
            target_label: __address__
            replacement: $1:8000

      - job_name: 'chat-service'
        kubernetes_sd_configs:
          - role: pod
            namespaces:
              names:
                - bigtech-chat
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_label_app]
            regex: chat-service
            action: keep
          - source_labels: [__meta_kubernetes_pod_ip]
            target_label: __address__
            replacement: $1:8000

      - job_name: 'friend-service'
        kubernetes_sd_configs:
          - role: pod
            namespaces:
              names:
                - bigtech-chat
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_label_app]
            regex: friend-service
            action: keep
          - source_labels: [__meta_kubernetes_pod_ip]
            target_label: __address__
            replacement: $1:8000

      - job_name: 'notification-service'
        kubernetes_sd_configs:
          - role: pod
            namespaces:
              names:
                - bigtech-chat
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_label_app]
            regex: notification-service
            action: keep
          - source_labels: [__meta_kubernetes_pod_ip]
            target_label: __address__
            replacement: $1:8000

      # MySQL Exporter
      - job_name: 'mysql'
        static_configs:
          - targets:
              - mysql-exporter:9104

      # MongoDB Exporter
      - job_name: 'mongodb'
        static_configs:
          - targets:
              - mongodb-exporter:9216

      # Kafka Exporter
      - job_name: 'kafka'
        static_configs:
          - targets:
              - kafka-exporter:9308
```

### 2. Prometheus Deployment

`infrastructure/k8s/manifests/prometheus-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: bigtech-chat
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      serviceAccountName: prometheus
      containers:
        - name: prometheus
          image: prom/prometheus:v2.48.0
          args:
            - '--config.file=/etc/prometheus/prometheus.yml'
            - '--storage.tsdb.path=/prometheus'
            - '--storage.tsdb.retention.time=15d'
            - '--web.enable-lifecycle'
          ports:
            - containerPort: 9090
              name: http
          volumeMounts:
            - name: config
              mountPath: /etc/prometheus
            - name: storage
              mountPath: /prometheus
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
      volumes:
        - name: config
          configMap:
            name: prometheus-config
        - name: storage
          persistentVolumeClaim:
            claimName: prometheus-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
  namespace: bigtech-chat
spec:
  type: ClusterIP
  ports:
    - port: 9090
      targetPort: 9090
      name: http
  selector:
    app: prometheus
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: prometheus-pvc
  namespace: bigtech-chat
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

### 3. RBAC 설정

`infrastructure/k8s/manifests/prometheus-rbac.yaml`:
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: prometheus
  namespace: bigtech-chat
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: prometheus
rules:
  - apiGroups: [""]
    resources:
      - nodes
      - nodes/proxy
      - services
      - endpoints
      - pods
    verbs: ["get", "list", "watch"]
  - apiGroups:
      - extensions
    resources:
      - ingresses
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: prometheus
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: prometheus
subjects:
  - kind: ServiceAccount
    name: prometheus
    namespace: bigtech-chat
```

### 4. Exporters 배포

`infrastructure/k8s/manifests/exporters.yaml`:
```yaml
# MySQL Exporter
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mysql-exporter
  namespace: bigtech-chat
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mysql-exporter
  template:
    metadata:
      labels:
        app: mysql-exporter
    spec:
      containers:
        - name: mysql-exporter
          image: prom/mysqld-exporter:v0.15.0
          env:
            - name: DATA_SOURCE_NAME
              valueFrom:
                secretKeyRef:
                  name: mysql-exporter-secret
                  key: dsn
          ports:
            - containerPort: 9104
              name: metrics
---
apiVersion: v1
kind: Service
metadata:
  name: mysql-exporter
  namespace: bigtech-chat
spec:
  ports:
    - port: 9104
      targetPort: 9104
      name: metrics
  selector:
    app: mysql-exporter
---
# MongoDB Exporter
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mongodb-exporter
  namespace: bigtech-chat
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mongodb-exporter
  template:
    metadata:
      labels:
        app: mongodb-exporter
    spec:
      containers:
        - name: mongodb-exporter
          image: percona/mongodb_exporter:0.40.0
          env:
            - name: MONGODB_URI
              valueFrom:
                secretKeyRef:
                  name: mongodb-exporter-secret
                  key: uri
          ports:
            - containerPort: 9216
              name: metrics
---
apiVersion: v1
kind: Service
metadata:
  name: mongodb-exporter
  namespace: bigtech-chat
spec:
  ports:
    - port: 9216
      targetPort: 9216
      name: metrics
  selector:
    app: mongodb-exporter
---
# Kafka Exporter
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kafka-exporter
  namespace: bigtech-chat
spec:
  replicas: 1
  selector:
    matchLabels:
      app: kafka-exporter
  template:
    metadata:
      labels:
        app: kafka-exporter
    spec:
      containers:
        - name: kafka-exporter
          image: danielqsj/kafka-exporter:v1.7.0
          args:
            - '--kafka.server=kafka-0.kafka-headless:9092'
            - '--kafka.server=kafka-1.kafka-headless:9092'
            - '--kafka.server=kafka-2.kafka-headless:9092'
          ports:
            - containerPort: 9308
              name: metrics
---
apiVersion: v1
kind: Service
metadata:
  name: kafka-exporter
  namespace: bigtech-chat
spec:
  ports:
    - port: 9308
      targetPort: 9308
      name: metrics
  selector:
    app: kafka-exporter
```

---

## Alert Rules

### Alert Rules ConfigMap

`infrastructure/k8s/manifests/prometheus-alert-rules.yaml`:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-alert-rules
  namespace: bigtech-chat
data:
  alert_rules.yml: |
    groups:
      - name: application_alerts
        interval: 30s
        rules:
          # High Error Rate
          - alert: HighHTTPErrorRate
            expr: |
              (
                sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
                /
                sum(rate(http_requests_total[5m])) by (service)
              ) > 0.05
            for: 5m
            labels:
              severity: critical
            annotations:
              summary: "High HTTP 5xx error rate on {{ $labels.service }}"
              description: "{{ $labels.service }} has {{ $value | humanizePercentage }} error rate"

          # High Response Time
          - alert: HighResponseTime
            expr: |
              histogram_quantile(0.95,
                sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service)
              ) > 1.0
            for: 5m
            labels:
              severity: warning
            annotations:
              summary: "High response time on {{ $labels.service }}"
              description: "95th percentile response time is {{ $value }}s"

          # Database Connection Issues
          - alert: MySQLConnectionPoolExhausted
            expr: mysql_global_status_threads_connected / mysql_global_variables_max_connections > 0.8
            for: 5m
            labels:
              severity: warning
            annotations:
              summary: "MySQL connection pool is 80% exhausted"

          - alert: MongoDBHighConnections
            expr: mongodb_connections{state="current"} > 500
            for: 5m
            labels:
              severity: warning
            annotations:
              summary: "MongoDB has {{ $value }} active connections"

          # Kafka Consumer Lag
          - alert: KafkaConsumerLagHigh
            expr: kafka_consumergroup_lag > 1000
            for: 10m
            labels:
              severity: warning
            annotations:
              summary: "Kafka consumer lag is {{ $value }} on {{ $labels.topic }}"
              description: "Consumer group {{ $labels.consumergroup }} is lagging"

          # Application-Specific Alerts
          - alert: HighFailedLoginRate
            expr: |
              (
                sum(rate(user_login_total{status="failed"}[5m]))
                /
                sum(rate(user_login_total[5m]))
              ) > 0.3
            for: 5m
            labels:
              severity: warning
            annotations:
              summary: "High failed login rate: {{ $value | humanizePercentage }}"

          - alert: LowOnlineUsers
            expr: user_online_count < 10
            for: 30m
            labels:
              severity: info
            annotations:
              summary: "Only {{ $value }} users online"

          - alert: NoActiveSSEConnections
            expr: active_sse_connections == 0
            for: 10m
            labels:
              severity: warning
            annotations:
              summary: "No active SSE connections for notifications"

      - name: infrastructure_alerts
        interval: 30s
        rules:
          # Pod Restarts
          - alert: PodRestarting
            expr: rate(kube_pod_container_status_restarts_total[15m]) > 0
            for: 5m
            labels:
              severity: warning
            annotations:
              summary: "Pod {{ $labels.pod }} is restarting"

          # High CPU Usage
          - alert: HighCPUUsage
            expr: |
              100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
            for: 10m
            labels:
              severity: warning
            annotations:
              summary: "CPU usage is {{ $value }}% on {{ $labels.instance }}"

          # High Memory Usage
          - alert: HighMemoryUsage
            expr: |
              (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85
            for: 10m
            labels:
              severity: warning
            annotations:
              summary: "Memory usage is {{ $value }}% on {{ $labels.instance }}"

          # Disk Space Low
          - alert: DiskSpaceLow
            expr: |
              (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100 < 15
            for: 5m
            labels:
              severity: critical
            annotations:
              summary: "Disk space is {{ $value }}% on {{ $labels.instance }}"
```

---

## 배포 순서

### 1. Exporters 배포
```bash
# Secrets 생성
kubectl create secret generic mysql-exporter-secret \
  --from-literal=dsn='exporter:password@tcp(mysql:3306)/' \
  -n bigtech-chat

kubectl create secret generic mongodb-exporter-secret \
  --from-literal=uri='mongodb://exporter:password@mongodb:27017' \
  -n bigtech-chat

# Exporters 배포
kubectl apply -f infrastructure/k8s/manifests/exporters.yaml
```

### 2. Prometheus RBAC 설정
```bash
kubectl apply -f infrastructure/k8s/manifests/prometheus-rbac.yaml
```

### 3. Prometheus 배포
```bash
# ConfigMap 생성
kubectl apply -f infrastructure/k8s/manifests/prometheus-config.yaml
kubectl apply -f infrastructure/k8s/manifests/prometheus-alert-rules.yaml

# Prometheus 배포
kubectl apply -f infrastructure/k8s/manifests/prometheus-deployment.yaml
```

### 4. 확인
```bash
# Prometheus UI 접속 (Port Forward)
kubectl port-forward -n bigtech-chat svc/prometheus 9090:9090

# 브라우저에서 http://localhost:9090 접속

# Targets 확인
# Status → Targets에서 모든 서비스가 UP 상태인지 확인
```

---

## PromQL 쿼리 예시

### Application Metrics

```promql
# 초당 메시지 전송량
rate(message_sent_total[5m])

# 서비스별 HTTP 요청 성공률
sum(rate(http_requests_total{status!~"5.."}[5m])) by (service)
/
sum(rate(http_requests_total[5m])) by (service)

# 95th percentile 응답 시간
histogram_quantile(0.95,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service)
)

# MongoDB 쿼리 성능 (operation별)
rate(mongodb_query_duration_seconds_sum[5m])
/
rate(mongodb_query_duration_seconds_count[5m])

# Kafka Consumer Lag
kafka_consumergroup_lag{topic="message.events"}
```

### Infrastructure Metrics

```promql
# MySQL 연결 수
mysql_global_status_threads_connected

# MongoDB 현재 연결 수
mongodb_connections{state="current"}

# Kafka Topic별 초당 메시지 수
rate(kafka_topic_partition_current_offset[5m])

# Pod CPU 사용률
sum(rate(container_cpu_usage_seconds_total{pod=~"user-service.*"}[5m])) by (pod)
```

---

## 다음 단계

1. **Grafana Dashboard 설정**: `grafana-dashboards.md` 참고
2. **Alertmanager 설정**: Slack, Email 알림 통합
3. **Jaeger 분산 추적 설정**: `jaeger-tracing.md` 참고

---

## 참고 자료
- [Prometheus 공식 문서](https://prometheus.io/docs/)
- [prometheus-fastapi-instrumentator](https://github.com/trallnag/prometheus-fastapi-instrumentator)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)

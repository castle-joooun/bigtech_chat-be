# Grafana Dashboards

## 📋 목차
1. [Grafana 개요](#grafana-개요)
2. [Kubernetes 배포](#kubernetes-배포)
3. [Dashboard 설계](#dashboard-설계)
4. [Dashboard JSON 예시](#dashboard-json-예시)
5. [Alert 통합](#alert-통합)

---

## Grafana 개요

### 사용 목적
- **시각화**: Prometheus 메트릭을 시각적 대시보드로 표현
- **모니터링**: 실시간 서비스 상태 모니터링
- **알림**: 임계값 기반 알림 (Prometheus Alertmanager와 통합)

### 아키텍처
```
┌──────────────┐
│  Prometheus  │
│  (Data)      │
└──────┬───────┘
       │
       ↓
┌──────────────┐    ┌─────────────────┐
│   Grafana    │───→│  Alertmanager   │
│  (Dashboard) │    │  (Notifications)│
└──────────────┘    └─────────────────┘
       │
       ↓
   Users (Web UI)
```

---

## Kubernetes 배포

### 1. Grafana Deployment

`infrastructure/k8s/manifests/grafana-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana
  namespace: bigtech-chat
spec:
  replicas: 1
  selector:
    matchLabels:
      app: grafana
  template:
    metadata:
      labels:
        app: grafana
    spec:
      containers:
        - name: grafana
          image: grafana/grafana:10.2.0
          ports:
            - containerPort: 3000
              name: http
          env:
            - name: GF_SECURITY_ADMIN_USER
              valueFrom:
                secretKeyRef:
                  name: grafana-secret
                  key: admin-user
            - name: GF_SECURITY_ADMIN_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: grafana-secret
                  key: admin-password
            - name: GF_SERVER_ROOT_URL
              value: "http://grafana.bigtech-chat.com"
            - name: GF_INSTALL_PLUGINS
              value: "grafana-piechart-panel"
          volumeMounts:
            - name: grafana-storage
              mountPath: /var/lib/grafana
            - name: grafana-datasources
              mountPath: /etc/grafana/provisioning/datasources
            - name: grafana-dashboards-config
              mountPath: /etc/grafana/provisioning/dashboards
            - name: grafana-dashboards
              mountPath: /var/lib/grafana/dashboards
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /api/health
              port: 3000
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /api/health
              port: 3000
            initialDelaySeconds: 10
            periodSeconds: 5
      volumes:
        - name: grafana-storage
          persistentVolumeClaim:
            claimName: grafana-pvc
        - name: grafana-datasources
          configMap:
            name: grafana-datasources
        - name: grafana-dashboards-config
          configMap:
            name: grafana-dashboards-config
        - name: grafana-dashboards
          configMap:
            name: grafana-dashboards
---
apiVersion: v1
kind: Service
metadata:
  name: grafana
  namespace: bigtech-chat
spec:
  type: ClusterIP
  ports:
    - port: 3000
      targetPort: 3000
      name: http
  selector:
    app: grafana
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: grafana-pvc
  namespace: bigtech-chat
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
```

### 2. Grafana Secrets

```bash
# Grafana admin 계정 생성
kubectl create secret generic grafana-secret \
  --from-literal=admin-user=admin \
  --from-literal=admin-password='your-secure-password' \
  -n bigtech-chat
```

### 3. Prometheus Datasource 설정

`infrastructure/k8s/manifests/grafana-datasources.yaml`:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-datasources
  namespace: bigtech-chat
data:
  datasources.yaml: |
    apiVersion: 1
    datasources:
      - name: Prometheus
        type: prometheus
        access: proxy
        url: http://prometheus:9090
        isDefault: true
        editable: false
        jsonData:
          timeInterval: "15s"
```

### 4. Dashboard Provisioning 설정

`infrastructure/k8s/manifests/grafana-dashboards-config.yaml`:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-dashboards-config
  namespace: bigtech-chat
data:
  dashboards.yaml: |
    apiVersion: 1
    providers:
      - name: 'Default'
        orgId: 1
        folder: ''
        type: file
        disableDeletion: false
        editable: true
        options:
          path: /var/lib/grafana/dashboards
```

---

## Dashboard 설계

### 1. Overview Dashboard

**목적**: 전체 시스템 상태를 한눈에 파악

**패널 구성**:
```
┌─────────────────────────────────────────────────────┐
│  BigTech Chat - System Overview                    │
├─────────────────────────────────────────────────────┤
│  [Total Users] [Online Users] [Active Rooms]       │
│  [Messages/sec] [HTTP Req/sec] [Error Rate]        │
├─────────────────────────────────────────────────────┤
│  HTTP Request Rate (by Service)                    │
│  [Line Chart]                                       │
├─────────────────────────────────────────────────────┤
│  Response Time (95th percentile)                   │
│  [Line Chart]                                       │
├─────────────────────────────────────────────────────┤
│  Error Rate                                         │
│  [Line Chart]                                       │
├─────────────────────────────────────────────────────┤
│  [User Svc] [Chat Svc] [Friend Svc] [Notif Svc]   │
│  Status: UP  Status: UP  Status: UP  Status: UP     │
└─────────────────────────────────────────────────────┘
```

**주요 메트릭**:
```promql
# Total Users (Stat Panel)
count(user_online_count)

# Online Users (Gauge)
user_online_count

# Active Rooms (Stat Panel)
active_chat_rooms

# Messages per second (Graph)
sum(rate(message_sent_total[5m]))

# HTTP Requests per second (Graph)
sum(rate(http_requests_total[5m])) by (service)

# Error Rate (Graph)
sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
/
sum(rate(http_requests_total[5m])) by (service)

# 95th Percentile Response Time (Graph)
histogram_quantile(0.95,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service)
)
```

### 2. User Service Dashboard

**패널 구성**:
```
┌─────────────────────────────────────────────────────┐
│  User Service - Detailed Metrics                   │
├─────────────────────────────────────────────────────┤
│  [Registrations] [Logins] [Searches] [Online]      │
├─────────────────────────────────────────────────────┤
│  User Registration Rate                             │
│  [Line Chart: success vs failed]                    │
├─────────────────────────────────────────────────────┤
│  Login Success Rate                                 │
│  [Pie Chart: success vs failed]                     │
├─────────────────────────────────────────────────────┤
│  User Search Duration (p50, p95, p99)              │
│  [Line Chart]                                       │
├─────────────────────────────────────────────────────┤
│  Online Users Timeline                              │
│  [Area Chart]                                       │
└─────────────────────────────────────────────────────┘
```

**주요 메트릭**:
```promql
# Registration Rate (by status)
sum(rate(user_registration_total[5m])) by (status)

# Login Success Rate
sum(rate(user_login_total{status="success"}[5m]))
/
sum(rate(user_login_total[5m]))

# User Search Duration Percentiles
histogram_quantile(0.50, sum(rate(user_search_duration_seconds_bucket[5m])) by (le))
histogram_quantile(0.95, sum(rate(user_search_duration_seconds_bucket[5m])) by (le))
histogram_quantile(0.99, sum(rate(user_search_duration_seconds_bucket[5m])) by (le))

# Online Users
user_online_count
```

### 3. Chat Service Dashboard

**패널 구성**:
```
┌─────────────────────────────────────────────────────┐
│  Chat Service - Message & Room Metrics             │
├─────────────────────────────────────────────────────┤
│  [Total Messages] [Msg/sec] [Active Rooms]         │
├─────────────────────────────────────────────────────┤
│  Message Send Rate (by type)                        │
│  [Stacked Area: text, image, file]                  │
├─────────────────────────────────────────────────────┤
│  Message Processing Duration (p95)                  │
│  [Line Chart]                                       │
├─────────────────────────────────────────────────────┤
│  MongoDB Query Duration (by operation)              │
│  [Line Chart: insert, find, update]                 │
├─────────────────────────────────────────────────────┤
│  Chat Room Creation Rate                            │
│  [Line Chart: direct vs group]                      │
├─────────────────────────────────────────────────────┤
│  Top 10 Active Rooms (by message count)            │
│  [Bar Gauge]                                        │
└─────────────────────────────────────────────────────┘
```

**주요 메트릭**:
```promql
# Message Send Rate (by type)
sum(rate(message_sent_total[5m])) by (message_type)

# Message Processing Duration (p95)
histogram_quantile(0.95,
  sum(rate(message_processing_duration_seconds_bucket[5m])) by (le)
)

# MongoDB Query Duration (by operation)
sum(rate(mongodb_query_duration_seconds_sum[5m])) by (operation)
/
sum(rate(mongodb_query_duration_seconds_count[5m])) by (operation)

# Chat Room Creation Rate
sum(rate(chat_room_created_total[5m])) by (room_type)

# Top Active Rooms
topk(10, sum(rate(message_sent_total[1h])) by (room_id))
```

### 4. Friend Service Dashboard

**패널 구성**:
```
┌─────────────────────────────────────────────────────┐
│  Friend Service - Friendship Metrics               │
├─────────────────────────────────────────────────────┤
│  [Pending] [Accepted] [Rejected] [Cancelled]       │
├─────────────────────────────────────────────────────┤
│  Friend Request Rate (by status)                    │
│  [Stacked Bar Chart]                                │
├─────────────────────────────────────────────────────┤
│  Friend Request Acceptance Rate                     │
│  [Gauge: 0-100%]                                    │
├─────────────────────────────────────────────────────┤
│  Friendship Query Duration (p95)                    │
│  [Line Chart]                                       │
└─────────────────────────────────────────────────────┘
```

**주요 메트릭**:
```promql
# Friend Request Rate (by status)
sum(rate(friend_request_total[5m])) by (status)

# Acceptance Rate
sum(rate(friend_request_total{status="accepted"}[5m]))
/
sum(rate(friend_request_total{status="sent"}[5m]))

# Query Duration (p95)
histogram_quantile(0.95,
  sum(rate(friendship_query_duration_seconds_bucket[5m])) by (le)
)
```

### 5. Notification Service Dashboard

**패널 구성**:
```
┌─────────────────────────────────────────────────────┐
│  Notification Service - Event Processing           │
├─────────────────────────────────────────────────────┤
│  [SSE Connections] [Notif/sec] [Kafka Lag]         │
├─────────────────────────────────────────────────────┤
│  Notification Send Rate (by type)                   │
│  [Line Chart: friend_request, message, etc]         │
├─────────────────────────────────────────────────────┤
│  Kafka Events Consumed (by topic)                   │
│  [Stacked Area Chart]                               │
├─────────────────────────────────────────────────────┤
│  Kafka Consumer Lag (by topic)                      │
│  [Line Chart]                                       │
├─────────────────────────────────────────────────────┤
│  Active SSE Connections                             │
│  [Area Chart]                                       │
├─────────────────────────────────────────────────────┤
│  Notification Processing Duration (p95)             │
│  [Line Chart]                                       │
└─────────────────────────────────────────────────────┘
```

**주요 메트릭**:
```promql
# Notification Send Rate
sum(rate(notification_sent_total[5m])) by (type)

# Kafka Events Consumed
sum(rate(kafka_events_consumed_total[5m])) by (topic)

# Kafka Consumer Lag
kafka_consumergroup_lag{consumergroup="notification-consumer-group"}

# Active SSE Connections
active_sse_connections

# Processing Duration (p95)
histogram_quantile(0.95,
  sum(rate(notification_processing_duration_seconds_bucket[5m])) by (le)
)
```

### 6. Infrastructure Dashboard

**패널 구성**:
```
┌─────────────────────────────────────────────────────┐
│  Infrastructure - Database & Kafka Metrics         │
├─────────────────────────────────────────────────────┤
│  MySQL Connections                                  │
│  [Gauge: current / max]                             │
├─────────────────────────────────────────────────────┤
│  MySQL Slow Queries                                 │
│  [Line Chart]                                       │
├─────────────────────────────────────────────────────┤
│  MongoDB Connections                                │
│  [Line Chart]                                       │
├─────────────────────────────────────────────────────┤
│  MongoDB Operations                                 │
│  [Stacked Area: query, insert, update]              │
├─────────────────────────────────────────────────────┤
│  Kafka Broker Status                                │
│  [Stat: broker count]                               │
├─────────────────────────────────────────────────────┤
│  Kafka Message Rate (by topic)                      │
│  [Line Chart]                                       │
└─────────────────────────────────────────────────────┘
```

**주요 메트릭**:
```promql
# MySQL Connections
mysql_global_status_threads_connected
mysql_global_variables_max_connections

# MySQL Slow Queries
rate(mysql_global_status_slow_queries[5m])

# MongoDB Connections
mongodb_connections{state="current"}

# MongoDB Operations
rate(mongodb_op_counters_total[5m])

# Kafka Brokers
kafka_brokers

# Kafka Message Rate
rate(kafka_topic_partition_current_offset[5m])
```

---

## Dashboard JSON 예시

### Overview Dashboard JSON

`infrastructure/k8s/dashboards/overview-dashboard.json`:
```json
{
  "dashboard": {
    "id": null,
    "uid": "overview",
    "title": "BigTech Chat - System Overview",
    "tags": ["overview", "bigtech-chat"],
    "timezone": "browser",
    "schemaVersion": 27,
    "version": 1,
    "refresh": "30s",
    "panels": [
      {
        "id": 1,
        "gridPos": {"h": 4, "w": 6, "x": 0, "y": 0},
        "type": "stat",
        "title": "Online Users",
        "targets": [
          {
            "expr": "user_online_count",
            "refId": "A"
          }
        ],
        "options": {
          "graphMode": "area",
          "colorMode": "value",
          "orientation": "auto",
          "textMode": "value_and_name"
        },
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"color": "red", "value": null},
                {"color": "yellow", "value": 50},
                {"color": "green", "value": 100}
              ]
            }
          }
        }
      },
      {
        "id": 2,
        "gridPos": {"h": 4, "w": 6, "x": 6, "y": 0},
        "type": "stat",
        "title": "Active Chat Rooms",
        "targets": [
          {
            "expr": "active_chat_rooms",
            "refId": "A"
          }
        ]
      },
      {
        "id": 3,
        "gridPos": {"h": 4, "w": 6, "x": 12, "y": 0},
        "type": "stat",
        "title": "Messages/sec",
        "targets": [
          {
            "expr": "sum(rate(message_sent_total[5m]))",
            "refId": "A"
          }
        ]
      },
      {
        "id": 4,
        "gridPos": {"h": 4, "w": 6, "x": 18, "y": 0},
        "type": "stat",
        "title": "Error Rate",
        "targets": [
          {
            "expr": "sum(rate(http_requests_total{status=~\"5..\"}[5m])) / sum(rate(http_requests_total[5m]))",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percentunit",
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 0.01},
                {"color": "red", "value": 0.05}
              ]
            }
          }
        }
      },
      {
        "id": 5,
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 4},
        "type": "graph",
        "title": "HTTP Request Rate (by Service)",
        "targets": [
          {
            "expr": "sum(rate(http_requests_total[5m])) by (service)",
            "refId": "A",
            "legendFormat": "{{service}}"
          }
        ],
        "yaxes": [
          {"format": "reqps", "label": "Requests/sec"},
          {"format": "short"}
        ]
      },
      {
        "id": 6,
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 4},
        "type": "graph",
        "title": "Response Time (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))",
            "refId": "A",
            "legendFormat": "{{service}} p95"
          }
        ],
        "yaxes": [
          {"format": "s", "label": "Duration"},
          {"format": "short"}
        ],
        "alert": {
          "conditions": [
            {
              "evaluator": {"params": [1.0], "type": "gt"},
              "operator": {"type": "and"},
              "query": {"params": ["A", "5m", "now"]},
              "reducer": {"params": [], "type": "avg"},
              "type": "query"
            }
          ],
          "executionErrorState": "alerting",
          "frequency": "1m",
          "handler": 1,
          "name": "High Response Time",
          "noDataState": "no_data",
          "notifications": []
        }
      }
    ]
  }
}
```

### ConfigMap으로 Dashboard 배포

`infrastructure/k8s/manifests/grafana-dashboards.yaml`:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-dashboards
  namespace: bigtech-chat
data:
  overview-dashboard.json: |
    {
      "dashboard": {
        "id": null,
        "uid": "overview",
        "title": "BigTech Chat - System Overview",
        ...
      }
    }

  user-service-dashboard.json: |
    {
      "dashboard": {
        "id": null,
        "uid": "user-service",
        "title": "User Service - Detailed Metrics",
        ...
      }
    }

  chat-service-dashboard.json: |
    {
      "dashboard": {
        "id": null,
        "uid": "chat-service",
        "title": "Chat Service - Message & Room Metrics",
        ...
      }
    }
```

---

## Alert 통합

### 1. Alertmanager 배포

`infrastructure/k8s/manifests/alertmanager-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: alertmanager
  namespace: bigtech-chat
spec:
  replicas: 1
  selector:
    matchLabels:
      app: alertmanager
  template:
    metadata:
      labels:
        app: alertmanager
    spec:
      containers:
        - name: alertmanager
          image: prom/alertmanager:v0.26.0
          args:
            - '--config.file=/etc/alertmanager/alertmanager.yml'
            - '--storage.path=/alertmanager'
          ports:
            - containerPort: 9093
              name: http
          volumeMounts:
            - name: config
              mountPath: /etc/alertmanager
            - name: storage
              mountPath: /alertmanager
      volumes:
        - name: config
          configMap:
            name: alertmanager-config
        - name: storage
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: alertmanager
  namespace: bigtech-chat
spec:
  type: ClusterIP
  ports:
    - port: 9093
      targetPort: 9093
      name: http
  selector:
    app: alertmanager
```

### 2. Alertmanager 설정 (Slack 통합)

`infrastructure/k8s/manifests/alertmanager-config.yaml`:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: alertmanager-config
  namespace: bigtech-chat
data:
  alertmanager.yml: |
    global:
      resolve_timeout: 5m
      slack_api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'

    route:
      group_by: ['alertname', 'service']
      group_wait: 10s
      group_interval: 10s
      repeat_interval: 12h
      receiver: 'slack-notifications'

      routes:
        - match:
            severity: critical
          receiver: 'slack-critical'

        - match:
            severity: warning
          receiver: 'slack-warnings'

    receivers:
      - name: 'slack-notifications'
        slack_configs:
          - channel: '#bigtech-chat-alerts'
            title: '{{ .GroupLabels.alertname }}'
            text: '{{ range .Alerts }}{{ .Annotations.summary }}\n{{ .Annotations.description }}\n{{ end }}'
            send_resolved: true

      - name: 'slack-critical'
        slack_configs:
          - channel: '#bigtech-chat-critical'
            title: '🚨 CRITICAL: {{ .GroupLabels.alertname }}'
            text: '{{ range .Alerts }}{{ .Annotations.summary }}\n{{ .Annotations.description }}\n{{ end }}'
            send_resolved: true
            color: 'danger'

      - name: 'slack-warnings'
        slack_configs:
          - channel: '#bigtech-chat-alerts'
            title: '⚠️ WARNING: {{ .GroupLabels.alertname }}'
            text: '{{ range .Alerts }}{{ .Annotations.summary }}\n{{ .Annotations.description }}\n{{ end }}'
            send_resolved: true
            color: 'warning'
```

### 3. Grafana에서 Alert 설정

Grafana Panel에서 Alert 설정 예시:
```json
{
  "alert": {
    "name": "High Response Time Alert",
    "conditions": [
      {
        "evaluator": {
          "params": [1.0],
          "type": "gt"
        },
        "operator": {
          "type": "and"
        },
        "query": {
          "params": ["A", "5m", "now"]
        },
        "reducer": {
          "params": [],
          "type": "avg"
        },
        "type": "query"
      }
    ],
    "executionErrorState": "alerting",
    "frequency": "1m",
    "handler": 1,
    "message": "95th percentile response time exceeded 1 second",
    "noDataState": "no_data",
    "notifications": [
      {"uid": "slack-notifications"}
    ]
  }
}
```

---

## 배포 순서

### 1. Grafana 배포
```bash
# Secrets 생성
kubectl create secret generic grafana-secret \
  --from-literal=admin-user=admin \
  --from-literal=admin-password='your-password' \
  -n bigtech-chat

# ConfigMaps 생성
kubectl apply -f infrastructure/k8s/manifests/grafana-datasources.yaml
kubectl apply -f infrastructure/k8s/manifests/grafana-dashboards-config.yaml
kubectl apply -f infrastructure/k8s/manifests/grafana-dashboards.yaml

# Grafana 배포
kubectl apply -f infrastructure/k8s/manifests/grafana-deployment.yaml
```

### 2. Alertmanager 배포
```bash
kubectl apply -f infrastructure/k8s/manifests/alertmanager-config.yaml
kubectl apply -f infrastructure/k8s/manifests/alertmanager-deployment.yaml
```

### 3. 접속 확인
```bash
# Grafana UI 접속
kubectl port-forward -n bigtech-chat svc/grafana 3000:3000

# 브라우저에서 http://localhost:3000 접속
# 로그인: admin / your-password

# Alertmanager UI 접속
kubectl port-forward -n bigtech-chat svc/alertmanager 9093:9093

# 브라우저에서 http://localhost:9093 접속
```

---

## 다음 단계

1. **Jaeger 분산 추적 설정**: `jaeger-tracing.md` 참고
2. **ELK Stack 로그 수집**: `elk-logging.md` 참고

---

## 참고 자료
- [Grafana 공식 문서](https://grafana.com/docs/)
- [Prometheus Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [Grafana Dashboard Best Practices](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/)

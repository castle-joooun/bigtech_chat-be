# ELK Stack Centralized Logging

## 📋 목차
1. [로깅 아키텍처](#로깅-아키텍처)
2. [Structured Logging 설정](#structured-logging-설정)
3. [Filebeat 설정](#filebeat-설정)
4. [Elasticsearch & Kibana 배포](#elasticsearch--kibana-배포)
5. [Log 분석 및 대시보드](#log-분석-및-대시보드)

---

## 로깅 아키텍처

### 전체 구조
```
┌──────────────────┐
│  User Service    │──┐
│  (FastAPI)       │  │
│  logs → stdout   │  │
└──────────────────┘  │
                      │
┌──────────────────┐  │    ┌─────────────┐    ┌──────────────┐
│  Chat Service    │  │    │  Filebeat   │───→│Elasticsearch │
│  logs → stdout   │──┼───→│  (Sidecar)  │    │   (Index)    │
└──────────────────┘  │    └─────────────┘    └──────┬───────┘
                      │                              │
┌──────────────────┐  │                              ↓
│ Friend Service   │  │                       ┌──────────────┐
│  logs → stdout   │──┤                       │   Kibana     │
└──────────────────┘  │                       │ (Dashboard)  │
                      │                       └──────────────┘
┌──────────────────┐  │
│ Notif Service    │──┘
│  logs → stdout   │
└──────────────────┘
```

### 로깅 원칙
1. **Structured Logging**: JSON 형식으로 로그 출력
2. **Correlation ID**: Trace ID로 요청 추적 (Jaeger 연동)
3. **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
4. **Centralized**: 모든 서비스 로그를 Elasticsearch에 집중

---

## Structured Logging 설정

### 1. 로깅 라이브러리 설치

`requirements.txt`:
```txt
python-json-logger==2.0.7
```

```bash
pip install python-json-logger
```

### 2. Structured Logger 구현

`app/infrastructure/logging/logger.py`:
```python
"""
Structured Logging 설정
"""
import logging
import sys
from pythonjsonlogger import jsonlogger
from opentelemetry import trace
import os


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """커스텀 JSON Formatter (Trace Context 포함)"""

    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)

        # 기본 필드
        log_record['service'] = os.getenv('SERVICE_NAME', 'unknown-service')
        log_record['environment'] = os.getenv('ENVIRONMENT', 'development')
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['timestamp'] = self.formatTime(record, self.datefmt)

        # OpenTelemetry Trace Context 추가
        span = trace.get_current_span()
        if span and span.is_recording():
            span_context = span.get_span_context()
            log_record['trace_id'] = format(span_context.trace_id, '032x')
            log_record['span_id'] = format(span_context.span_id, '016x')

        # 에러 정보 추가
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)


def setup_logging(
    service_name: str,
    log_level: str = "INFO",
    enable_json: bool = True
):
    """
    Structured Logging 설정

    Args:
        service_name: 서비스 이름
        log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_json: JSON 형식 활성화 여부
    """

    # 환경 변수로 오버라이드 가능
    log_level = os.getenv("LOG_LEVEL", log_level).upper()

    # Root Logger 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console Handler 추가
    console_handler = logging.StreamHandler(sys.stdout)

    if enable_json:
        # JSON Formatter 적용
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(service)s %(logger)s %(message)s'
        )
    else:
        # 일반 텍스트 Formatter (개발 환경)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # uvicorn 로그 레벨 설정
    logging.getLogger("uvicorn").setLevel(log_level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logging.info(
        f"✅ Structured logging enabled: service={service_name}, level={log_level}"
    )


def get_logger(name: str) -> logging.Logger:
    """Logger 인스턴스 반환"""
    return logging.getLogger(name)
```

### 3. 애플리케이션에 적용

`app/main.py`:
```python
from fastapi import FastAPI
from app.infrastructure.logging.logger import setup_logging
import os

SERVICE_NAME = os.getenv("SERVICE_NAME", "chat-service")

# Structured Logging 설정
setup_logging(
    service_name=SERVICE_NAME,
    log_level="INFO",
    enable_json=True  # Kubernetes 환경에서는 True
)

app = FastAPI(title=SERVICE_NAME)

# ...
```

### 4. API에서 로그 기록

`app/api/chat.py`:
```python
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@router.post("/rooms/{room_id}/messages")
async def send_message(
    room_id: int,
    message: MessageCreate,
    current_user: User = Depends(get_current_user)
):
    """메시지 전송"""

    # Structured Log 기록
    logger.info(
        "Message send request received",
        extra={
            "user_id": current_user.id,
            "username": current_user.username,
            "room_id": room_id,
            "message_type": message.message_type,
            "content_length": len(message.content)
        }
    )

    try:
        # 메시지 저장
        msg = await message_repository.save(message)

        logger.info(
            "Message saved successfully",
            extra={
                "message_id": str(msg.id),
                "room_id": room_id
            }
        )

        return {"message_id": str(msg.id)}

    except Exception as e:
        logger.error(
            "Failed to save message",
            exc_info=True,
            extra={
                "user_id": current_user.id,
                "room_id": room_id,
                "error_type": type(e).__name__
            }
        )
        raise
```

**출력 예시 (JSON)**:
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "service": "chat-service",
  "environment": "production",
  "logger": "app.api.chat",
  "message": "Message send request received",
  "trace_id": "abc123def456789012345678901234567890",
  "span_id": "1234567890abcdef",
  "user_id": 456,
  "username": "john_doe",
  "room_id": 123,
  "message_type": "text",
  "content_length": 42
}
```

---

## Filebeat 설정

### 1. Filebeat ConfigMap

`infrastructure/k8s/manifests/filebeat-config.yaml`:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: filebeat-config
  namespace: bigtech-chat
data:
  filebeat.yml: |
    filebeat.inputs:
      - type: container
        paths:
          - /var/log/containers/*.log
        processors:
          # Kubernetes 메타데이터 추가
          - add_kubernetes_metadata:
              host: ${NODE_NAME}
              matchers:
                - logs_path:
                    logs_path: "/var/log/containers/"

          # JSON 파싱
          - decode_json_fields:
              fields: ["message"]
              target: ""
              overwrite_keys: true

          # 필드 정리
          - drop_fields:
              fields: ["agent", "ecs", "host.name"]

    # Elasticsearch 출력
    output.elasticsearch:
      hosts: ["http://elasticsearch:9200"]
      index: "bigtech-chat-%{[service]}-%{+yyyy.MM.dd}"

    # Index Template 설정
    setup.template.name: "bigtech-chat"
    setup.template.pattern: "bigtech-chat-*"
    setup.template.enabled: true
    setup.ilm.enabled: false

    # Kibana 연동
    setup.kibana:
      host: "http://kibana:5601"

    # 로그 레벨
    logging.level: info
    logging.to_stderr: true
```

### 2. Filebeat DaemonSet

`infrastructure/k8s/manifests/filebeat-daemonset.yaml`:
```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: filebeat
  namespace: bigtech-chat
spec:
  selector:
    matchLabels:
      app: filebeat
  template:
    metadata:
      labels:
        app: filebeat
    spec:
      serviceAccountName: filebeat
      terminationGracePeriodSeconds: 30
      hostNetwork: true
      dnsPolicy: ClusterFirstWithHostNet
      containers:
        - name: filebeat
          image: docker.elastic.co/beats/filebeat:8.11.0
          args: [
            "-c", "/etc/filebeat.yml",
            "-e"
          ]
          env:
            - name: NODE_NAME
              valueFrom:
                fieldRef:
                  fieldPath: spec.nodeName
          securityContext:
            runAsUser: 0
          resources:
            limits:
              memory: 200Mi
            requests:
              cpu: 100m
              memory: 100Mi
          volumeMounts:
            - name: config
              mountPath: /etc/filebeat.yml
              readOnly: true
              subPath: filebeat.yml
            - name: data
              mountPath: /usr/share/filebeat/data
            - name: varlibdockercontainers
              mountPath: /var/lib/docker/containers
              readOnly: true
            - name: varlog
              mountPath: /var/log
              readOnly: true
      volumes:
        - name: config
          configMap:
            name: filebeat-config
        - name: varlibdockercontainers
          hostPath:
            path: /var/lib/docker/containers
        - name: varlog
          hostPath:
            path: /var/log
        - name: data
          hostPath:
            path: /var/lib/filebeat-data
            type: DirectoryOrCreate
```

### 3. RBAC 설정

`infrastructure/k8s/manifests/filebeat-rbac.yaml`:
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: filebeat
  namespace: bigtech-chat
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: filebeat
rules:
  - apiGroups: [""]
    resources:
      - namespaces
      - pods
      - nodes
    verbs:
      - get
      - watch
      - list
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: filebeat
subjects:
  - kind: ServiceAccount
    name: filebeat
    namespace: bigtech-chat
roleRef:
  kind: ClusterRole
  name: filebeat
  apiGroup: rbac.authorization.k8s.io
```

---

## Elasticsearch & Kibana 배포

### 1. Elasticsearch StatefulSet

`infrastructure/k8s/manifests/elasticsearch.yaml`:
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: elasticsearch
  namespace: bigtech-chat
spec:
  serviceName: elasticsearch
  replicas: 3
  selector:
    matchLabels:
      app: elasticsearch
  template:
    metadata:
      labels:
        app: elasticsearch
    spec:
      initContainers:
        # vm.max_map_count 설정
        - name: increase-vm-max-map-count
          image: busybox
          command: ["sysctl", "-w", "vm.max_map_count=262144"]
          securityContext:
            privileged: true
      containers:
        - name: elasticsearch
          image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
          env:
            - name: cluster.name
              value: "bigtech-chat-logs"
            - name: node.name
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
            - name: discovery.seed_hosts
              value: "elasticsearch-0.elasticsearch,elasticsearch-1.elasticsearch,elasticsearch-2.elasticsearch"
            - name: cluster.initial_master_nodes
              value: "elasticsearch-0,elasticsearch-1,elasticsearch-2"
            - name: ES_JAVA_OPTS
              value: "-Xms1g -Xmx1g"
            - name: xpack.security.enabled
              value: "false"
          ports:
            - containerPort: 9200
              name: http
            - containerPort: 9300
              name: transport
          volumeMounts:
            - name: data
              mountPath: /usr/share/elasticsearch/data
          resources:
            requests:
              memory: "2Gi"
              cpu: "1000m"
            limits:
              memory: "2Gi"
              cpu: "1000m"
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 50Gi
---
apiVersion: v1
kind: Service
metadata:
  name: elasticsearch
  namespace: bigtech-chat
spec:
  clusterIP: None
  ports:
    - port: 9200
      name: http
    - port: 9300
      name: transport
  selector:
    app: elasticsearch
```

### 2. Kibana Deployment

`infrastructure/k8s/manifests/kibana.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kibana
  namespace: bigtech-chat
spec:
  replicas: 1
  selector:
    matchLabels:
      app: kibana
  template:
    metadata:
      labels:
        app: kibana
    spec:
      containers:
        - name: kibana
          image: docker.elastic.co/kibana/kibana:8.11.0
          env:
            - name: ELASTICSEARCH_HOSTS
              value: "http://elasticsearch:9200"
            - name: SERVER_NAME
              value: "kibana"
            - name: SERVER_HOST
              value: "0.0.0.0"
          ports:
            - containerPort: 5601
              name: http
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
          livenessProbe:
            httpGet:
              path: /api/status
              port: 5601
            initialDelaySeconds: 60
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /api/status
              port: 5601
            initialDelaySeconds: 30
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: kibana
  namespace: bigtech-chat
spec:
  type: ClusterIP
  ports:
    - port: 5601
      targetPort: 5601
      name: http
  selector:
    app: kibana
```

---

## Log 분석 및 대시보드

### 1. Kibana Index Pattern 생성

Kibana UI 접속 후:
1. **Management → Stack Management → Index Patterns**
2. **Create Index Pattern**
   - Index pattern name: `bigtech-chat-*`
   - Time field: `@timestamp`
3. **Create**

### 2. 로그 검색 쿼리 (KQL)

```kql
# 특정 서비스의 에러 로그
service: "chat-service" AND level: "ERROR"

# 특정 사용자의 로그
user_id: 456

# Trace ID로 검색 (Jaeger 연동)
trace_id: "abc123def456789012345678901234567890"

# 느린 요청 (duration > 1초)
duration > 1000

# 최근 5분 내 에러 로그
level: "ERROR" AND @timestamp > now-5m

# 특정 메시지 타입의 로그
message_type: "image" OR message_type: "file"
```

### 3. Log Dashboard 설계

#### Dashboard 1: Service Overview
```
┌─────────────────────────────────────────────────────┐
│  BigTech Chat - Log Overview                       │
├─────────────────────────────────────────────────────┤
│  [Total Logs] [Error Count] [Warning Count]        │
├─────────────────────────────────────────────────────┤
│  Log Level Distribution (Pie Chart)                 │
│  ┌───────────────────────────────────────┐         │
│  │  INFO:  70%                            │         │
│  │  WARNING: 20%                          │         │
│  │  ERROR:   8%                           │         │
│  │  CRITICAL: 2%                          │         │
│  └───────────────────────────────────────┘         │
├─────────────────────────────────────────────────────┤
│  Logs per Service (Bar Chart)                       │
│  ┌───────────────────────────────────────┐         │
│  │  user-service:    ████████ 8000       │         │
│  │  chat-service:    ████████████ 12000  │         │
│  │  friend-service:  ████ 4000           │         │
│  │  notif-service:   ██████ 6000         │         │
│  └───────────────────────────────────────┘         │
├─────────────────────────────────────────────────────┤
│  Error Timeline (Line Chart)                        │
│  ┌───────────────────────────────────────┐         │
│  │        /\                              │         │
│  │       /  \        /\                   │         │
│  │      /    \      /  \                  │         │
│  │  ___/      \____/    \____             │         │
│  └───────────────────────────────────────┘         │
└─────────────────────────────────────────────────────┘
```

#### Dashboard 2: Error Analysis
```
┌─────────────────────────────────────────────────────┐
│  Error Analysis                                     │
├─────────────────────────────────────────────────────┤
│  Top Errors (Table)                                 │
│  ┌───────────────────────────────────────────┐     │
│  │ Error Type          │ Count │ Service     │     │
│  ├─────────────────────┼───────┼─────────────┤     │
│  │ DatabaseError       │  150  │ chat-svc    │     │
│  │ KafkaTimeoutError   │   45  │ notif-svc   │     │
│  │ PermissionDenied    │   30  │ user-svc    │     │
│  └───────────────────────────────────────────┘     │
├─────────────────────────────────────────────────────┤
│  Error Stack Traces (Recent 10)                     │
│  ┌───────────────────────────────────────────┐     │
│  │  [ERROR] chat-service                     │     │
│  │  MongoDB timeout: operation exceeded 30s  │     │
│  │  Traceback:                               │     │
│  │    File "app/api/chat.py", line 42        │     │
│  │    ...                                    │     │
│  └───────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────┘
```

### 4. Trace + Log 통합 (Correlation ID)

**Jaeger Trace → Kibana Log 연동**:

1. Jaeger UI에서 Trace 확인:
   - Trace ID: `abc123def456789012345678901234567890`

2. Kibana에서 해당 Trace의 모든 로그 검색:
   ```kql
   trace_id: "abc123def456789012345678901234567890"
   ```

3. 전체 요청 흐름 확인:
   ```
   10:30:45.123 [user-service]   INFO  User authenticated: user_id=456
   10:30:45.138 [chat-service]   INFO  Message send request received
   10:30:45.163 [chat-service]   INFO  Message saved to MongoDB
   10:30:45.175 [chat-service]   INFO  Kafka event published: message.events
   10:30:45.220 [notif-service]  INFO  Kafka event consumed
   10:30:45.255 [notif-service]  INFO  SSE notification sent
   ```

### 5. Alert 설정 (Kibana Alerting)

**Alert 1: High Error Rate**
```json
{
  "name": "High Error Rate in Chat Service",
  "schedule": {
    "interval": "5m"
  },
  "conditions": [
    {
      "type": "threshold",
      "query": "service:\"chat-service\" AND level:\"ERROR\"",
      "timeWindow": "5m",
      "threshold": {
        "comparator": "gt",
        "value": 10
      }
    }
  ],
  "actions": [
    {
      "type": "slack",
      "channel": "#bigtech-chat-alerts",
      "message": "🚨 High error rate detected in chat-service: {{count}} errors in last 5 minutes"
    }
  ]
}
```

**Alert 2: Critical Error**
```json
{
  "name": "Critical Error Detected",
  "schedule": {
    "interval": "1m"
  },
  "conditions": [
    {
      "type": "match",
      "query": "level:\"CRITICAL\"",
      "timeWindow": "1m"
    }
  ],
  "actions": [
    {
      "type": "slack",
      "channel": "#bigtech-chat-critical",
      "message": "🔥 CRITICAL ERROR: {{service}} - {{message}}"
    },
    {
      "type": "email",
      "to": "oncall@bigtech-chat.com",
      "subject": "CRITICAL: {{service}}",
      "body": "{{exception}}"
    }
  ]
}
```

---

## 배포 순서

### 1. Elasticsearch 배포
```bash
kubectl apply -f infrastructure/k8s/manifests/elasticsearch.yaml

# 상태 확인
kubectl get pods -n bigtech-chat -l app=elasticsearch
kubectl logs -n bigtech-chat elasticsearch-0
```

### 2. Kibana 배포
```bash
kubectl apply -f infrastructure/k8s/manifests/kibana.yaml

# 상태 확인
kubectl get pods -n bigtech-chat -l app=kibana

# UI 접속
kubectl port-forward -n bigtech-chat svc/kibana 5601:5601
# http://localhost:5601
```

### 3. Filebeat 배포
```bash
# RBAC 설정
kubectl apply -f infrastructure/k8s/manifests/filebeat-rbac.yaml

# ConfigMap 생성
kubectl apply -f infrastructure/k8s/manifests/filebeat-config.yaml

# DaemonSet 배포
kubectl apply -f infrastructure/k8s/manifests/filebeat-daemonset.yaml

# 상태 확인
kubectl get daemonset -n bigtech-chat filebeat
kubectl logs -n bigtech-chat -l app=filebeat
```

### 4. 로그 확인
```bash
# Kibana UI에서 Index Pattern 생성 후 Discover 탭에서 로그 확인
```

---

## Observability 통합 요약

### Three Pillars of Observability

```
┌─────────────────────────────────────────────────────┐
│  1. Metrics (Prometheus + Grafana)                 │
│  - 성능 메트릭 수집 및 시각화                         │
│  - Alert 발송                                       │
├─────────────────────────────────────────────────────┤
│  2. Traces (Jaeger + OpenTelemetry)                │
│  - 분산 추적                                        │
│  - 서비스 의존성 파악                                │
├─────────────────────────────────────────────────────┤
│  3. Logs (ELK Stack)                                │
│  - 중앙화된 로그 수집                                │
│  - Trace ID로 로그 연동                             │
└─────────────────────────────────────────────────────┘
```

### Correlation ID를 통한 통합

```
User Request (POST /rooms/123/messages)
│
├─ Trace ID: abc123def...
│
├─ [Jaeger] Distributed Trace
│  └─ user-service → chat-service → notif-service
│
├─ [Prometheus] Metrics
│  └─ message_sent_total +1
│  └─ message_processing_duration_seconds 0.12
│
└─ [Elasticsearch] Logs
   └─ trace_id: abc123def...
   └─ 10:30:45 [chat-service] INFO Message saved
   └─ 10:30:45 [notif-service] INFO SSE sent
```

**통합 워크플로우**:
1. Grafana에서 높은 응답 시간 감지
2. Jaeger에서 해당 Trace 검색
3. Trace ID로 Kibana에서 상세 로그 확인
4. 원인 파악 및 해결

---

## 참고 자료
- [Elastic Stack 공식 문서](https://www.elastic.co/guide/index.html)
- [Filebeat Kubernetes 가이드](https://www.elastic.co/guide/en/beats/filebeat/current/running-on-kubernetes.html)
- [Python JSON Logger](https://github.com/madzak/python-json-logger)

# BigTech Chat Backend - 신입 개발자 온보딩 가이드

> **대상**: Python/FastAPI를 알고 있는 신입 개발자
> **목표**: MSA 아키텍처를 단계별로 학습하고, Spring Boot 마이그레이션 준비
> **학습 기간**: 약 7주 (49일)
> **최종 업데이트**: 2026-01-28

---

## 목차

- [Part 1: 시작하기](#part-1-시작하기-day-1-3)
- [Part 2: FastAPI 코드 이해하기](#part-2-fastapi-코드-이해하기-day-4-7)
- [Part 3: MSA 아키텍처](#part-3-msa-아키텍처-day-8-14)
- [Part 4: Kafka Event Streaming](#part-4-kafka-event-streaming-day-15-21)
- [Part 5: Docker & Kubernetes](#part-5-docker--kubernetes-day-22-28)
- [Part 6: Observability (모니터링)](#part-6-observability-모니터링-day-29-35)
- [Part 7: 테스트 및 CI/CD](#part-7-테스트-및-cicd-day-36-42)
- [Part 8: Spring Boot 마이그레이션 준비](#part-8-spring-boot-마이그레이션-준비-day-43-49)
- [Part 9: 실습 과제 및 부록](#part-9-실습-과제-및-부록)

---

# Part 1: 시작하기 (Day 1-3)

## 1.1 프로젝트 소개

### 이 프로젝트는 무엇인가요?

**BigTech Chat**은 카카오톡, 라인 같은 **실시간 채팅 서비스**의 백엔드입니다.

```
사용자가 할 수 있는 것:
├── 회원가입 / 로그인
├── 친구 추가 / 친구 목록 보기
├── 1:1 채팅방 만들기
├── 메시지 보내기 / 받기 (실시간)
└── 온라인 상태 확인
```

### 왜 이 프로젝트를 공부해야 하나요?

이 프로젝트는 **대기업 면접에서 자주 묻는 기술들**을 실제로 구현해놓았습니다:

| 면접 질문 | 이 프로젝트에서 배울 수 있는 것 |
|-----------|-------------------------------|
| "MSA 경험 있으세요?" | 3개 마이크로서비스 분리 경험 |
| "Kafka 써보셨나요?" | 이벤트 기반 서비스 간 통신 |
| "DDD 알고 계세요?" | Bounded Context, Aggregate 설계 |
| "K8s 배포 해보셨나요?" | Deployment, HPA, Ingress 설정 |
| "모니터링은 어떻게?" | Prometheus + Grafana 대시보드 |

### 기술 스택: 익숙한 것 vs 새로 배울 것

**이미 알고 있을 것** (Python/FastAPI 개발자 기준):
- ✅ Python 3.11
- ✅ FastAPI (async/await)
- ✅ Pydantic (데이터 검증)
- ✅ SQLAlchemy (MySQL ORM)

**새로 배울 것**:
- 🆕 MongoDB + Beanie (문서형 DB)
- 🆕 Redis (캐시, 온라인 상태)
- 🆕 Kafka (이벤트 스트리밍)
- 🆕 Docker + Kubernetes
- 🆕 Prometheus + Grafana (모니터링)

### 프로젝트 로드맵

```
현재 위치                                    다음 단계
    ↓                                           ↓
┌─────────────────────────────────────────────────────────────┐
│  Monolithic  →  DDD  →  MSA (FastAPI)  →  Spring Boot      │
│     완료        완료       ★ 현재            다음 목표       │
└─────────────────────────────────────────────────────────────┘
```

---

## 1.2 서비스 구조 한눈에 보기

### 3개의 마이크로서비스

```
                    ┌─────────────────────┐
                    │   API Gateway       │
                    │   (Kong - Port 80)  │
                    └──────────┬──────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ User Service  │    │ Chat Service  │    │Friend Service │
│  (Port 8005)  │    │  (Port 8002)  │    │  (Port 8003)  │
│               │    │               │    │               │
│ • 회원가입     │    │ • 채팅방 생성  │    │ • 친구 요청    │
│ • 로그인      │    │ • 메시지 전송  │    │ • 친구 수락    │
│ • 프로필 관리  │    │ • 실시간 SSE  │    │ • 친구 목록    │
└───────┬───────┘    └───────┬───────┘    └───────┬───────┘
        │                    │                    │
        └──────────────────────┼──────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Kafka (3 brokers) │
                    │   이벤트 버스        │
                    └─────────────────────┘
```

### 데이터베이스 구성

```
┌─────────────────────────────────────────────────────────────┐
│                        데이터 저장소                          │
├─────────────────┬─────────────────┬─────────────────────────┤
│     MySQL       │    MongoDB      │        Redis            │
│   (관계형 DB)    │   (문서형 DB)    │       (캐시)            │
├─────────────────┼─────────────────┼─────────────────────────┤
│ • 사용자 정보    │ • 채팅 메시지    │ • 온라인 상태           │
│ • 친구 관계     │ • 읽음 상태      │ • 세션 정보             │
│ • 채팅방 정보    │ • 메시지 반응    │ • API 캐시              │
└─────────────────┴─────────────────┴─────────────────────────┘

💡 왜 DB를 3개나 쓸까요?
   - MySQL: 사용자/친구처럼 "관계"가 중요한 데이터
   - MongoDB: 메시지처럼 "대량으로 빠르게 쌓이는" 데이터
   - Redis: 온라인 상태처럼 "자주 바뀌고 빨리 읽어야 하는" 데이터
```

---

## 1.3 로컬 개발 환경 설정

### 필수 설치 도구

```bash
# 1. Docker Desktop (필수)
# https://www.docker.com/products/docker-desktop 에서 다운로드

# 설치 확인
docker --version    # Docker version 24.0.0 이상
docker-compose --version  # Docker Compose version v2.0.0 이상

# 2. Python 3.11+ (이미 있을 것)
python --version    # Python 3.11.x

# 3. kubectl (Kubernetes 배포 시 필요, 나중에 설치해도 됨)
# https://kubernetes.io/docs/tasks/tools/
```

### 프로젝트 클론 및 환경 설정

```bash
# 저장소 클론
git clone <repository-url>
cd bigtech_chat-be

# 가상환경 활성화 (이미 있다면)
source .venv/bin/activate

# 또는 새로 생성
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 전체 스택 실행 (가장 쉬운 방법)

```bash
# 1. 전체 MSA 스택 실행 (서비스 + DB + Kafka + 모니터링)
docker-compose -f docker-compose.msa.yml up -d

# 2. Kong Gateway 라우팅 설정
./infrastructure/docker/kong/kong-config.sh

# 3. 실행 확인 (약 30초 대기 후)
docker-compose -f docker-compose.msa.yml ps
```

### 서비스 접속 확인

| 서비스 | URL | 설명 |
|--------|-----|------|
| **API Gateway** | http://localhost | 모든 API의 진입점 |
| **User Service** | http://localhost:8005/docs | Swagger UI |
| **Friend Service** | http://localhost:8003/docs | Swagger UI |
| **Chat Service** | http://localhost:8002/docs | Swagger UI |
| **Grafana** | http://localhost:3000 | 모니터링 대시보드 (admin/admin) |
| **Prometheus** | http://localhost:9090 | 메트릭 조회 |
| **Kafka UI** | http://localhost:8080 | Kafka 토픽/메시지 확인 |

### 첫 번째 API 테스트

```bash
# 1. Health Check
curl http://localhost:8005/health
# 응답: {"status":"healthy","service":"User Service"}

# 2. 회원가입
curl -X POST http://localhost:8005/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "Test1234!@",
    "display_name": "테스트 유저"
  }'

# 3. 로그인
curl -X POST http://localhost:8005/auth/login/json \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test1234!@"
  }'
# 응답: {"access_token": "eyJ0eXAi...", "token_type": "bearer"}
```

### 트러블슈팅

**문제: 포트 충돌 (Port already in use)**
```bash
# 사용 중인 포트 확인
lsof -i :3306    # MySQL
lsof -i :8005    # User Service

# 해결: 기존 프로세스 종료 또는 Docker 컨테이너 정리
docker-compose -f docker-compose.msa.yml down
```

**문제: 서비스가 시작되지 않음**
```bash
# 로그 확인
docker logs bigtech-user-service
docker logs bigtech-chat-service

# 전체 재시작
docker-compose -f docker-compose.msa.yml down
docker-compose -f docker-compose.msa.yml up -d
```

> 📚 **더 자세한 내용**: [빠른 시작 가이드](./QUICK_START.md)

---

## 1.4 디렉토리 구조 이해하기

```
bigtech_chat-be/
│
├── services/                    # 🔥 마이크로서비스 (가장 중요!)
│   ├── user-service/           # 사용자 인증/프로필
│   ├── friend-service/         # 친구 관계 관리
│   └── chat-service/           # 채팅/메시지
│
├── infrastructure/              # 인프라 설정
│   └── docker/
│       ├── kong/               # API Gateway 설정
│       ├── prometheus/         # 메트릭 수집 설정
│       ├── grafana/            # 대시보드 설정
│       └── ...
│
├── k8s/                        # Kubernetes 배포 파일
│   └── manifests/
│       ├── services/           # 서비스 Deployment
│       ├── statefulsets/       # DB StatefulSet
│       └── ...
│
├── tests/                      # 테스트
│   └── e2e/                    # End-to-End 테스트
│
├── docs/                       # 📚 문서 (지금 읽고 있는 것!)
│   ├── architecture/           # DDD 아키텍처 문서
│   ├── kafka/                  # Kafka 설계 문서
│   ├── observability/          # 모니터링 문서
│   └── ...
│
├── docker-compose.msa.yml      # 전체 스택 실행용
├── docker-compose.test.yml     # 테스트 환경용
└── README.md                   # 프로젝트 소개
```

### 각 서비스 내부 구조 (공통 패턴)

```
services/user-service/
│
├── main.py                     # 앱 진입점 (FastAPI 앱 생성)
├── requirements.txt            # Python 의존성
├── Dockerfile                  # Docker 이미지 빌드
│
└── app/
    ├── api/                    # 🌐 API 엔드포인트
    │   ├── auth.py            # /auth/register, /auth/login
    │   ├── profile.py         # /profile/me
    │   └── user.py            # /users/search
    │
    ├── services/               # 💼 비즈니스 로직
    │   ├── auth_service.py    # 인증 로직
    │   └── ...
    │
    ├── models/                 # 🗄️ 데이터베이스 모델
    │   └── user.py            # User 테이블
    │
    ├── schemas/                # 📋 Pydantic 스키마
    │   └── user.py            # UserCreate, UserResponse
    │
    ├── database/               # 🔌 DB 연결
    │   ├── mysql.py           # MySQL 연결
    │   └── redis.py           # Redis 연결
    │
    ├── kafka/                  # 📨 Kafka 이벤트
    │   ├── producer.py        # 이벤트 발행
    │   └── events.py          # 이벤트 정의
    │
    ├── core/                   # ⚙️ 설정
    │   ├── config.py          # 환경 변수
    │   └── errors.py          # 예외 정의
    │
    └── utils/                  # 🔧 유틸리티
        └── auth.py            # JWT, 비밀번호 해싱
```

---

## 1.5 Part 1 학습 체크리스트

- [ ] Docker Desktop 설치 및 실행 확인
- [ ] `docker-compose.msa.yml`로 전체 스택 실행
- [ ] 3개 서비스 Swagger UI 접속 확인
- [ ] 회원가입 → 로그인 API 테스트 완료
- [ ] Grafana 대시보드 접속 확인 (http://localhost:3000)
- [ ] 디렉토리 구조 파악 완료

> **Spring Boot에서는?**
> - FastAPI의 `main.py`는 Spring Boot의 `@SpringBootApplication` 클래스에 해당
> - `app/api/`는 Spring의 `@RestController` 클래스들에 해당
> - `app/services/`는 Spring의 `@Service` 클래스들에 해당
> - 이 구조는 Spring Boot에서도 거의 동일하게 적용됩니다!

---

# Part 2: FastAPI 코드 이해하기 (Day 4-7)

## 2.1 FastAPI 핵심 패턴 복습

### async/await 비동기 처리

```python
# ❌ 동기 방식 (느림 - 요청 하나씩 순차 처리)
def get_user(user_id: int):
    user = db.query(User).filter(User.id == user_id).first()
    return user

# ✅ 비동기 방식 (빠름 - I/O 대기 중 다른 요청 처리)
async def get_user(user_id: int):
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

**왜 비동기가 중요한가요?**
```
동기 방식:
  요청1 ████████░░░░░░░░ (DB 대기)
  요청2          ████████░░░░░░░░ (앞 요청 끝날 때까지 대기)
  요청3                   ████████░░░░░░░░

비동기 방식:
  요청1 ████░░░░████ (DB 대기 중 다른 요청 처리)
  요청2   ████░░░░████
  요청3     ████░░░░████
  → 같은 시간에 더 많은 요청 처리 가능!
```

### CPU-bound 작업의 비동기 처리 (bcrypt)

> ⚠️ **주의**: bcrypt 같은 CPU-intensive 작업은 async/await만으로는 부족합니다!

```python
# ❌ 잘못된 방식: bcrypt가 이벤트 루프를 블로킹
async def register(user_data: UserCreate):
    hashed = get_password_hash(user_data.password)  # 블로킹! (200ms+)
    # 이 동안 다른 요청 처리 불가

# ✅ 올바른 방식: ThreadPoolExecutor로 별도 스레드에서 실행
from concurrent.futures import ThreadPoolExecutor
import asyncio

_executor = ThreadPoolExecutor(max_workers=4)

async def get_password_hash_async(password: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, pwd_context.hash, password)

async def register(user_data: UserCreate):
    hashed = await get_password_hash_async(user_data.password)  # 논블로킹!
    # 해싱 중에도 다른 요청 처리 가능
```

**성능 개선 효과** (실제 테스트 결과):
- 에러율: 39% → **0%**
- 평균 응답시간: 18.7초 → **2.7초** (85% 개선)

### Pydantic을 활용한 데이터 검증

```python
# services/user-service/app/schemas/user.py

from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    """회원가입 요청 데이터"""
    email: EmailStr                           # 이메일 형식 자동 검증
    username: str = Field(min_length=3, max_length=20)  # 길이 제한
    password: str = Field(min_length=8)       # 최소 8자
    display_name: str | None = None           # 선택 필드

class UserResponse(BaseModel):
    """응답 데이터 (비밀번호 제외)"""
    id: int
    email: str
    username: str
    display_name: str | None

    class Config:
        from_attributes = True  # SQLAlchemy 모델 → Pydantic 변환 허용
```

**Pydantic이 자동으로 해주는 것:**
- 타입 검사 (str에 int 들어오면 에러)
- 형식 검사 (EmailStr은 이메일 형식만 허용)
- 길이 검사 (min_length, max_length)
- 자동 문서화 (Swagger UI에 표시)

### Depends()를 이용한 의존성 주입

```python
# services/user-service/app/api/auth.py

from fastapi import Depends, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.mysql import get_async_session
from app.utils.auth import get_current_user

router = APIRouter()

@router.get("/profile/me")
async def get_my_profile(
    current_user: User = Depends(get_current_user),  # JWT 검증 + 유저 조회
    db: AsyncSession = Depends(get_async_session)    # DB 세션 주입
):
    return current_user
```

**Depends()의 장점:**
```python
# 1. 코드 재사용: get_current_user를 여러 API에서 사용
@router.get("/profile/me")
async def get_profile(current_user = Depends(get_current_user)): ...

@router.put("/profile/me")
async def update_profile(current_user = Depends(get_current_user)): ...

@router.get("/friends")
async def get_friends(current_user = Depends(get_current_user)): ...

# 2. 테스트 용이: 가짜 객체로 쉽게 교체 가능
def test_get_profile():
    app.dependency_overrides[get_current_user] = lambda: fake_user
```

---

## 2.2 데이터베이스 연동 코드 분석

### MySQL + SQLAlchemy (관계형 데이터)

```python
# services/user-service/app/database/mysql.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 1. 엔진 생성 (DB 연결 풀)
engine = create_async_engine(
    settings.mysql_url,  # mysql+aiomysql://user:pass@host:3306/db
    pool_size=10,        # 동시 연결 수
    max_overflow=20      # 추가 허용 연결 수
)

# 2. 세션 팩토리 생성
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 3. 의존성 주입용 함수
async def get_async_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session  # 요청 처리 후 자동으로 세션 닫힘
```

**User 모델 예시:**
```python
# services/user-service/app/models/user.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100))
    is_online = Column(Boolean, default=False)
    last_seen_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
```

### MongoDB + Beanie (문서형 데이터)

```python
# services/chat-service/app/models/messages.py

from beanie import Document
from pydantic import Field
from datetime import datetime

class Message(Document):
    """채팅 메시지 (MongoDB에 저장)"""
    user_id: int                              # 보낸 사람
    room_id: int                              # 채팅방
    content: str                              # 메시지 내용
    message_type: str = "text"                # text, image, file
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_deleted: bool = False                  # 소프트 삭제

    class Settings:
        name = "messages"  # 컬렉션 이름
        indexes = [
            [("room_id", 1), ("created_at", -1)]  # 복합 인덱스
        ]
```

**왜 메시지는 MongoDB에 저장할까요?**
```
MySQL (관계형):
  - 장점: JOIN, 트랜잭션, 일관성
  - 단점: 스키마 변경 어려움, 대용량 쓰기 부담

MongoDB (문서형):
  - 장점: 유연한 스키마, 빠른 쓰기, 수평 확장 쉬움
  - 단점: JOIN 없음, 트랜잭션 제한적

→ 메시지는 "대량으로 빠르게 쌓이고" "스키마가 자주 바뀔 수 있어서" MongoDB가 적합!
  (예: 나중에 이모지 반응, 답장, 파일 첨부 등 추가)
```

### Redis (캐시 및 실시간 상태)

```python
# services/user-service/app/database/redis.py

import redis.asyncio as redis

# Redis 클라이언트 생성
redis_client = redis.from_url(settings.redis_url)

# 온라인 상태 저장 (TTL: 60초)
async def set_online(user_id: int):
    await redis_client.setex(
        f"user:online:{user_id}",  # 키
        60,                         # TTL (초)
        "online"                    # 값
    )

# 온라인 상태 확인
async def is_online(user_id: int) -> bool:
    result = await redis_client.get(f"user:online:{user_id}")
    return result is not None
```

**Redis 사용 패턴:**
```
┌─────────────────────────────────────────────────────┐
│ Redis 키 패턴                                        │
├─────────────────────────────────────────────────────┤
│ user:online:{user_id}     → 온라인 상태 (TTL 60초)   │
│ user:session:{user_id}    → 세션 정보               │
│ cache:user:{user_id}      → 유저 정보 캐시          │
│ rate_limit:{ip}           → API 호출 제한           │
└─────────────────────────────────────────────────────┘
```

---

## 2.3 서비스별 핵심 코드 분석

### User Service: 인증 로직

```python
# services/user-service/app/api/auth.py

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_async_session)
):
    # 1. 이메일 중복 확인
    existing = await auth_service.find_user_by_email(db, user_data.email)
    if existing:
        raise HTTPException(status_code=400, detail="이미 사용 중인 이메일입니다")

    # 2. 비밀번호 해싱
    hashed_password = get_password_hash(user_data.password)

    # 3. 사용자 생성
    user = await auth_service.create_user(db, user_data, hashed_password)

    # 4. Kafka 이벤트 발행 (다른 서비스에 알림)
    await producer.publish(
        topic="user.events",
        event=UserRegistered(user_id=user.id, email=user.email)
    )

    return user
```

### Friend Service: 친구 요청 로직

```python
# services/friend-service/app/api/friend.py

@router.post("/request")
async def send_friend_request(
    request: FriendRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    # 1. 자기 자신에게 요청 방지
    if request.target_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="자신에게 친구 요청할 수 없습니다")

    # 2. 이미 친구인지 확인
    existing = await friendship_service.get_friendship(
        db, current_user.id, request.target_user_id
    )
    if existing:
        raise HTTPException(status_code=400, detail="이미 친구 요청을 보냈습니다")

    # 3. 친구 요청 생성 (status: pending)
    friendship = await friendship_service.create_request(
        db, current_user.id, request.target_user_id
    )

    # 4. Kafka 이벤트 발행
    await producer.publish(
        topic="friend.events",
        event=FriendRequestSent(
            from_user_id=current_user.id,
            to_user_id=request.target_user_id
        )
    )

    return friendship
```

### Chat Service: 메시지 전송 로직

```python
# services/chat-service/app/api/message.py

@router.post("/{room_id}")
async def send_message(
    room_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user)
):
    # 1. 채팅방 참여자인지 확인
    is_member = await chat_room_service.is_room_member(room_id, current_user.id)
    if not is_member:
        raise HTTPException(status_code=403, detail="채팅방에 참여하지 않았습니다")

    # 2. 메시지 저장 (MongoDB)
    message = Message(
        user_id=current_user.id,
        room_id=room_id,
        content=message_data.content,
        message_type=message_data.message_type
    )
    await message.insert()

    # 3. Kafka 이벤트 발행 (실시간 알림용)
    await producer.publish(
        topic="message.events",
        event=MessageSent(
            message_id=str(message.id),
            room_id=room_id,
            user_id=current_user.id,
            content=message_data.content
        ),
        key=str(room_id)  # 같은 채팅방 메시지는 순서 보장
    )

    return message
```

---

## 2.4 Part 2 학습 체크리스트

- [ ] async/await가 왜 필요한지 설명할 수 있다
- [ ] Pydantic 스키마 작성법을 이해했다
- [ ] Depends()로 의존성 주입하는 방법을 알았다
- [ ] MySQL, MongoDB, Redis의 용도 차이를 이해했다
- [ ] User Service의 회원가입 코드를 따라갈 수 있다
- [ ] 각 서비스가 Kafka로 이벤트를 발행하는 것을 확인했다

> **Spring Boot에서는?**
> - `async/await` → Spring WebFlux의 `Mono`/`Flux` 또는 코루틴
> - `Pydantic` → Java의 Bean Validation (`@Valid`, `@NotNull`)
> - `Depends()` → Spring의 `@Autowired` 또는 생성자 주입
> - `SQLAlchemy` → Spring Data JPA
> - `Beanie` → Spring Data MongoDB

---

# Part 3: MSA 아키텍처 (Day 8-14)

## 3.1 MSA란 무엇인가?

### Monolithic vs MSA 비교

**Monolithic (단일 앱):**
```
┌─────────────────────────────────────────┐
│           하나의 FastAPI 앱              │
│  ┌─────────┬─────────┬─────────┐       │
│  │  User   │  Chat   │ Friend  │       │
│  │  API    │  API    │  API    │       │
│  └────┬────┴────┬────┴────┬────┘       │
│       └─────────┼─────────┘            │
│            하나의 DB                    │
└─────────────────────────────────────────┘

문제점:
- User 기능 수정해도 전체 앱 재배포
- Chat 트래픽 폭증 시 전체 앱 Scale-up 필요
- 한 부분 버그로 전체 서비스 장애 가능
```

**MSA (마이크로서비스):**
```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ User Service │  │ Chat Service │  │Friend Service│
│   (별도 앱)   │  │   (별도 앱)   │  │   (별도 앱)   │
│   별도 DB    │  │   별도 DB    │  │   별도 DB    │
└──────────────┘  └──────────────┘  └──────────────┘

장점:
- User만 수정하면 User만 재배포
- Chat 트래픽 폭증 시 Chat만 Scale-out
- Chat 장애 시 User/Friend는 정상 동작
```

### 이 프로젝트의 MSA 분리 기준

```
┌─────────────────────────────────────────────────────────────┐
│                    비즈니스 도메인 기준 분리                   │
├─────────────────┬─────────────────┬─────────────────────────┤
│  User Domain    │  Friend Domain  │     Chat Domain         │
├─────────────────┼─────────────────┼─────────────────────────┤
│ • 회원가입      │ • 친구 요청     │ • 채팅방 관리           │
│ • 로그인/로그아웃│ • 친구 수락/거절 │ • 메시지 전송/조회      │
│ • 프로필 관리   │ • 친구 목록     │ • 읽음 상태 관리        │
│ • 사용자 검색   │ • 차단 관리     │ • 실시간 스트리밍       │
├─────────────────┼─────────────────┼─────────────────────────┤
│ MySQL + Redis   │ MySQL           │ MySQL + MongoDB + Redis │
└─────────────────┴─────────────────┴─────────────────────────┘
```

---

## 3.2 DDD(Domain-Driven Design) 기초

### Bounded Context (경계가 있는 맥락)

**비유: 회사의 부서**
```
"사용자"라는 단어의 의미가 부서마다 다름:

┌─────────────────────────────────────────────────────────────┐
│ HR 부서에서 "사용자" = 직원 (급여, 휴가, 인사정보)            │
│ IT 부서에서 "사용자" = 시스템 계정 (권한, 접근 기록)          │
│ 마케팅에서 "사용자" = 고객 (구매 이력, 선호도)               │
└─────────────────────────────────────────────────────────────┘

→ 각 부서(Context)마다 "사용자"의 의미와 속성이 다름
→ 이것이 Bounded Context!
```

**이 프로젝트의 Bounded Context:**
```
┌─────────────────────────────────────────────────────────────┐
│ User Context에서 "User"                                     │
│ = 인증 대상 (email, password_hash, is_active)               │
├─────────────────────────────────────────────────────────────┤
│ Friend Context에서 "User"                                   │
│ = 친구 관계의 대상 (user_id만 참조)                          │
├─────────────────────────────────────────────────────────────┤
│ Chat Context에서 "User"                                     │
│ = 메시지 발신자 (user_id, username 캐싱)                     │
└─────────────────────────────────────────────────────────────┘
```

### Aggregate (집합체)

**비유: 주문서**
```
주문서 = Aggregate Root (진입점)
├── 주문 상품 목록 = Entity
├── 배송 주소 = Value Object
└── 결제 정보 = Value Object

규칙: 외부에서는 "주문서"를 통해서만 접근
      직접 "주문 상품"을 수정하면 안 됨
```

**이 프로젝트의 Aggregate:**
```python
# User Aggregate
User (Root)
├── email, username, password_hash  # User가 직접 관리
└── Profile (Value Object)          # display_name, profile_image

# ChatRoom Aggregate
ChatRoom (Root)
├── room_type, created_at           # ChatRoom이 직접 관리
├── RoomMember[] (Entity)           # 참여자 목록
└── Message[] (Entity)              # 메시지 목록
```

> 📚 **더 자세한 DDD 설명**: [Bounded Context 문서](./architecture/01-bounded-context.md), [Aggregate 설계 문서](./architecture/02-aggregate-design.md)

---

## 3.3 서비스 간 통신

### 동기 통신 (REST API)

```
사용자가 친구 목록 조회 시:

Client → Friend Service: GET /friends
                ↓
         Friend Service → User Service: GET /users?ids=1,2,3
                              (친구들의 상세 정보 조회)
                ↓
         Friend Service ← User Service: [{id:1, name:"철수"}, ...]
                ↓
Client ← Friend Service: 친구 목록 + 상세 정보
```

**코드 예시:**
```python
# Friend Service에서 User Service 호출
import httpx

async def get_user_details(user_ids: list[int]):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://user-service:8005/users",
            params={"user_ids": ",".join(map(str, user_ids))}
        )
        return response.json()
```

### 비동기 통신 (Kafka 이벤트)

```
사용자가 회원가입 시:

User Service: 회원 생성 완료
      ↓
      └──→ Kafka (user.events): UserRegistered 이벤트 발행
                    ↓
           ┌───────┴───────┐
           ↓               ↓
    Notification      Analytics
      Service          Service
    (환영 이메일)     (통계 수집)
```

**언제 어떤 방식을 사용할까?**

| 상황 | 통신 방식 | 이유 |
|------|-----------|------|
| 친구 목록 + 상세 정보 | REST (동기) | 응답이 바로 필요 |
| 회원가입 알림 | Kafka (비동기) | 응답 기다릴 필요 없음 |
| 메시지 전송 | Kafka (비동기) | 빠른 응답 + 다수에게 전달 |
| 프로필 조회 | REST (동기) | 즉시 데이터 필요 |

---

## 3.4 API Gateway (Kong)

### API Gateway의 역할

```
                    인터넷
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Kong API Gateway                          │
│                                                             │
│  1. 라우팅: /api/users/* → User Service (8005)             │
│            /api/friends/* → Friend Service (8003)          │
│            /api/messages/* → Chat Service (8002)           │
│                                                             │
│  2. 인증: JWT 토큰 검증 (선택적)                            │
│                                                             │
│  3. Rate Limiting: IP당 분당 100회 제한                     │
│                                                             │
│  4. CORS: 허용된 도메인만 접근 가능                          │
│                                                             │
│  5. 로깅: 모든 요청/응답 기록                                │
└─────────────────────────────────────────────────────────────┘
```

**라우팅 규칙 예시:**
```bash
# infrastructure/docker/kong/kong-config.sh

# User Service 라우팅
curl -X POST http://kong:8001/services \
  --data name=user-service \
  --data url=http://user-service:8005

curl -X POST http://kong:8001/services/user-service/routes \
  --data paths[]=/api/auth \
  --data paths[]=/api/users \
  --data paths[]=/api/profile
```

---

## 3.5 Part 3 학습 체크리스트

- [ ] Monolithic vs MSA의 차이를 설명할 수 있다
- [ ] Bounded Context가 무엇인지 이해했다
- [ ] Aggregate의 역할을 설명할 수 있다
- [ ] REST vs Kafka 통신의 차이를 이해했다
- [ ] API Gateway가 왜 필요한지 알았다

> **Spring Boot에서는?**
> - DDD 개념은 언어와 무관하게 동일하게 적용
> - API Gateway: Spring Cloud Gateway 또는 Kong 동일 사용
> - 서비스 간 통신: Spring WebClient (REST), Spring Kafka

---

# Part 4: Kafka Event Streaming (Day 15-21)

## 4.1 Kafka 기초 개념

### Kafka를 우체국에 비유하면

```
┌─────────────────────────────────────────────────────────────┐
│                    Kafka = 24시간 우체국                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Producer (발신자)        Topic (우편함)      Consumer (수신자)
│  ┌─────────────┐         ┌─────────────┐    ┌─────────────┐
│  │ User Service│ ──────▶ │ user.events │ ──▶│ Notification│
│  │ (회원가입)   │  편지    │ ┌─────────┐ │     │  Service   │
│  └─────────────┘  전송    │ │Partition│ │     └─────────────┘
│                          │ │   0     │ │
│  ┌─────────────┐         │ ├─────────┤ │    ┌─────────────┐
│  │ Chat Service│ ──────▶ │ │Partition│ │ ──▶│  Analytics  │
│  │ (메시지전송) │         │ │   1     │ │     │  Service   │
│  └─────────────┘         │ └─────────┘ │     └─────────────┘
│                          └─────────────┘
│                                                             │
│  💡 Partition = 우편함을 여러 칸으로 나눔                    │
│     → 여러 Consumer가 동시에 처리 가능 (병렬 처리)           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 핵심 용어 정리

| 용어 | 설명 | 비유 |
|------|------|------|
| **Producer** | 메시지를 보내는 쪽 | 편지 보내는 사람 |
| **Consumer** | 메시지를 받는 쪽 | 편지 받는 사람 |
| **Topic** | 메시지 분류 단위 | 우편함 종류 (일반/등기/택배) |
| **Partition** | Topic 내 병렬 처리 단위 | 우편함의 칸 |
| **Offset** | 메시지 순번 | 편지의 일련번호 |
| **Consumer Group** | 같은 목적의 Consumer 그룹 | 같은 부서 직원들 |

### Consumer Group 이해하기

```
┌─────────────────────────────────────────────────────────────┐
│  message.events Topic (3 Partitions)                        │
│                                                             │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │Partition 0│  │Partition 1│  │Partition 2│              │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘              │
│        │              │              │                     │
│        ▼              ▼              ▼                     │
│  ┌─────────────────────────────────────────────┐           │
│  │     Consumer Group: notification-group       │           │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │           │
│  │  │Consumer 1│  │Consumer 2│  │Consumer 3│  │           │
│  │  │(P0 담당) │  │(P1 담당) │  │(P2 담당) │  │           │
│  │  └──────────┘  └──────────┘  └──────────┘  │           │
│  └─────────────────────────────────────────────┘           │
│                                                             │
│  💡 같은 그룹 내 Consumer들은 Partition을 나눠서 처리        │
│     → 병렬 처리로 처리량 증가!                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 4.2 이 프로젝트의 Kafka 설계

### Topic 목록

| Topic | Partitions | 보관기간 | 발행자 | 용도 |
|-------|------------|----------|--------|------|
| `user.events` | 3 | 7일 | User Service | 회원가입, 프로필 수정 |
| `user.online_status` | 6 | 1시간 | User Service | 온라인 상태 변경 |
| `friend.events` | 3 | 7일 | Friend Service | 친구 요청/수락/거절 |
| `message.events` | 10 | 7일 | Chat Service | 메시지 전송 |
| `chat.events` | 3 | 7일 | Chat Service | 채팅방 생성 |

### 이벤트 흐름 예시: 메시지 전송

```
1. 사용자 A가 메시지 전송
   │
   ▼
2. Chat Service: 메시지 MongoDB 저장
   │
   ▼
3. Chat Service → Kafka: MessageSent 이벤트 발행
   {
     "event_type": "MessageSent",
     "message_id": "msg_123",
     "room_id": 1,
     "user_id": 100,
     "content": "안녕하세요!",
     "timestamp": "2026-01-27T10:00:00Z"
   }
   │
   ▼
4. Kafka (message.events Topic, Partition = room_id % 10)
   │
   ├──▶ Notification Service: 사용자 B에게 푸시 알림
   │
   └──▶ Analytics Service: 메시지 통계 수집
```

### Producer 코드 예시

```python
# services/chat-service/app/kafka/producer.py

from aiokafka import AIOKafkaProducer
import json

class KafkaEventProducer:
    def __init__(self):
        self.producer = None

    async def start(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks='all',  # 모든 복제본에 저장 확인
        )
        await self.producer.start()

    async def publish(self, topic: str, event: dict, key: str = None):
        """이벤트 발행"""
        await self.producer.send_and_wait(
            topic=topic,
            value=event,
            key=key.encode('utf-8') if key else None
        )

# 싱글톤 인스턴스
_producer = KafkaEventProducer()

def get_event_producer():
    return _producer
```

---

## 4.3 실습: Kafka UI로 이벤트 확인

### Kafka UI 접속

```bash
# Kafka UI 접속
open http://localhost:8080
```

### 실습 순서

1. **Topic 목록 확인**
   - 좌측 메뉴 "Topics" 클릭
   - `user.events`, `message.events` 등 확인

2. **메시지 확인**
   - Topic 클릭 → "Messages" 탭
   - 실시간으로 들어오는 이벤트 확인

3. **이벤트 발생시키기**
   ```bash
   # 1. 회원가입 (UserRegistered 이벤트 발생)
   curl -X POST http://localhost:8005/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email": "kafka-test@example.com", "username": "kafkatest", "password": "Test1234!@"}'

   # 2. Kafka UI에서 user.events Topic 확인
   # → UserRegistered 이벤트가 보여야 함
   ```

4. **Consumer Lag 확인**
   - "Consumer Groups" 메뉴
   - Lag = 아직 처리 안 된 메시지 수
   - Lag이 계속 증가하면 Consumer가 느린 것!

> 📚 **더 자세한 Kafka 설명**: [Kafka Topic 설계 문서](./kafka/topic-design.md)

---

## 4.4 Part 4 학습 체크리스트

- [ ] Producer, Consumer, Topic, Partition을 설명할 수 있다
- [ ] Consumer Group의 역할을 이해했다
- [ ] 이 프로젝트의 Kafka Topic 목록을 알았다
- [ ] Kafka UI에서 이벤트를 확인해봤다
- [ ] MessageSent 이벤트의 흐름을 따라갈 수 있다

> **Spring Boot에서는?**
> - Spring Kafka 라이브러리 사용
> - `@KafkaListener`로 Consumer 구현
> - `KafkaTemplate`으로 Producer 구현
> - Kafka 개념 자체는 동일!

---

# Part 5: Docker & Kubernetes (Day 22-28)

## 5.1 Docker 기초

### Dockerfile 구조 이해

```dockerfile
# services/user-service/Dockerfile

# ============================================
# Stage 1: Builder (빌드 환경)
# ============================================
FROM python:3.11-slim AS builder

WORKDIR /build

# 빌드에만 필요한 도구 설치
RUN apt-get update && apt-get install -y \
    gcc \           # C 컴파일러 (일부 패키지 빌드용)
    libffi-dev      # FFI 라이브러리

# 가상환경 생성 및 패키지 설치
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ============================================
# Stage 2: Runtime (실행 환경)
# ============================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# 실행에 필요한 것만 설치 (curl = 헬스체크용)
RUN apt-get update && apt-get install -y curl \
    && useradd --create-home appuser  # 보안: 비-root 사용자

# Builder에서 만든 가상환경만 복사 (gcc 등은 복사 안 함!)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 애플리케이션 코드 복사
COPY --chown=appuser:appuser . .

# 비-root 사용자로 실행
USER appuser

EXPOSE 8005

# 워커 수 환경변수 (기본값 4)
ENV WORKERS=4

# Gunicorn + Uvicorn 워커로 멀티프로세스 처리
# → 단일 uvicorn 대비 4배 동시 처리 가능
CMD ["sh", "-c", "gunicorn main:app -w ${WORKERS} -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8005 --timeout 120"]
```

> 💡 **왜 Gunicorn을 사용할까요?**
> - 단일 Uvicorn: 1개 프로세스로 요청 처리 (CPU-bound 작업 시 병목)
> - Gunicorn + Uvicorn 워커: 여러 프로세스가 병렬 처리 (bcrypt 같은 CPU 작업에 유리)
> - 성능 개선: 에러율 39%→0%, 응답시간 18초→2.7초 (85% 개선)

### Multi-stage Build의 효과

```
┌─────────────────────────────────────────────────────────────┐
│                  이미지 크기 비교                             │
├─────────────────┬─────────────┬─────────────┬───────────────┤
│ 서비스           │ Before      │ After       │ 절감률        │
├─────────────────┼─────────────┼─────────────┼───────────────┤
│ User Service    │ 425MB       │ 251MB       │ -41%          │
│ Friend Service  │ 425MB       │ 251MB       │ -41%          │
│ Chat Service    │ 471MB       │ 297MB       │ -37%          │
└─────────────────┴─────────────┴─────────────┴───────────────┘

💡 왜 작은 이미지가 좋을까?
   - 빌드 시간 단축
   - 배포 시간 단축 (다운로드 빠름)
   - 저장 공간 절약
   - 보안 (불필요한 도구 없음)
```

### Docker 명령어

```bash
# 이미지 빌드
docker build -t bigtech-user-service:latest \
  -f services/user-service/Dockerfile \
  services/user-service/

# 이미지 크기 확인
docker images | grep bigtech

# 컨테이너 실행
docker run -d -p 8005:8005 bigtech-user-service:latest

# 로그 확인
docker logs -f <container_id>
```

> 📚 **더 자세한 Docker 설명**: [Dockerfile 최적화 문서](./optimization/01-dockerfile-optimization.md)

---

## 5.2 Kubernetes 기초

### 핵심 개념 (신입 관점)

**Pod = 컨테이너 실행 단위**
```yaml
# Pod 안에 컨테이너가 실행됨
┌─────────────────────┐
│        Pod          │
│  ┌───────────────┐  │
│  │  Container    │  │
│  │  (user-svc)   │  │
│  └───────────────┘  │
└─────────────────────┘
```

**Deployment = Pod를 관리하는 것**
```yaml
# "user-service Pod를 항상 2개 유지해줘"
┌─────────────────────────────────────────┐
│           Deployment                     │
│  replicas: 2                            │
│  ┌─────────────┐  ┌─────────────┐       │
│  │    Pod 1    │  │    Pod 2    │       │
│  └─────────────┘  └─────────────┘       │
│                                         │
│  Pod 1이 죽으면? → 자동으로 새 Pod 생성  │
└─────────────────────────────────────────┘
```

**Service = Pod들에게 접근하는 방법**
```yaml
# "user-service라는 이름으로 접근하면 Pod들에게 연결해줘"
┌─────────────────────────────────────────────────────┐
│  Service: user-service                              │
│  ┌─────────────────────────────────────────────┐   │
│  │  user-service:8005                          │   │
│  │         │                                    │   │
│  │    ┌────┴────┐                              │   │
│  │    ▼         ▼                              │   │
│  │  Pod 1    Pod 2   (로드밸런싱)               │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

**HPA = 자동 확장**
```yaml
# "CPU 70% 넘으면 Pod 늘려줘"
┌─────────────────────────────────────────────────────┐
│  HPA (Horizontal Pod Autoscaler)                    │
│                                                     │
│  CPU < 70%: Pod 2개 유지                            │
│  CPU > 70%: Pod 3개, 4개, ... 최대 10개까지         │
│  CPU < 40%: Pod 다시 줄임                           │
└─────────────────────────────────────────────────────┘
```

---

## 5.3 이 프로젝트의 K8s 매니페스트

### 디렉토리 구조

```
k8s/manifests/
├── namespace.yaml          # 네임스페이스 정의
├── configmap.yaml          # 환경 설정 (DB URL 등)
├── secrets.yaml            # 민감 정보 (비밀번호)
│
├── services/               # 마이크로서비스
│   ├── user-service.yaml   # Deployment + Service
│   ├── friend-service.yaml
│   └── chat-service.yaml
│
├── statefulsets/           # 데이터베이스 (상태 유지 필요)
│   ├── mysql.yaml
│   ├── mongodb.yaml
│   ├── redis.yaml
│   └── kafka.yaml
│
├── hpa/
│   └── hpa.yaml           # Auto Scaling 설정
│
└── ingress/
    └── ingress.yaml       # 외부 트래픽 라우팅
```

### 배포 명령어

```bash
# 1. 네임스페이스 생성
kubectl apply -f k8s/manifests/namespace.yaml

# 2. 설정 적용
kubectl apply -f k8s/manifests/configmap.yaml
kubectl apply -f k8s/manifests/secrets.yaml

# 3. 데이터베이스 배포 (먼저!)
kubectl apply -f k8s/manifests/statefulsets/

# 4. 서비스 배포
kubectl apply -f k8s/manifests/services/

# 5. Auto Scaling 설정
kubectl apply -f k8s/manifests/hpa/

# 6. Ingress 설정
kubectl apply -f k8s/manifests/ingress/

# 상태 확인
kubectl get all -n bigtech-chat
```

> 📚 **더 자세한 K8s 설명**: [Kubernetes 배포 가이드](../k8s/README.md)

---

## 5.4 Part 5 학습 체크리스트

- [ ] Multi-stage build가 왜 필요한지 설명할 수 있다
- [ ] Pod, Deployment, Service의 차이를 알았다
- [ ] HPA가 무엇인지 이해했다
- [ ] StatefulSet은 언제 사용하는지 알았다
- [ ] kubectl 기본 명령어를 실행해봤다

> **Spring Boot에서는?**
> - Dockerfile 구조는 거의 동일 (base 이미지만 JDK로 변경)
> - Kubernetes 개념과 매니페스트는 완전히 동일!
> - K8s 지식은 언어와 무관하게 100% 재사용 가능

---

# Part 6: Observability (모니터링) (Day 29-35)

## 6.1 왜 모니터링이 중요한가?

### 프로덕션 환경의 현실

```
개발 환경:                    프로덕션 환경:
┌─────────────┐              ┌─────────────────────────┐
│ 내 컴퓨터    │              │ 수백 대의 서버           │
│ 요청 1개    │              │ 초당 수천 개의 요청      │
│ 에러나면     │              │ 에러나면?               │
│ 콘솔에서 확인│              │ 어디서 났는지 모름!      │
└─────────────┘              └─────────────────────────┘

→ 모니터링 없이는 문제를 찾을 수 없음!
```

### Observability의 3가지 축

```
┌─────────────────────────────────────────────────────────────┐
│                    Observability                            │
├───────────────────┬───────────────────┬─────────────────────┤
│      Metrics      │      Logs         │      Traces         │
│    (숫자 지표)     │    (텍스트 기록)   │    (요청 추적)       │
├───────────────────┼───────────────────┼─────────────────────┤
│ • CPU 사용률      │ • 에러 메시지     │ • A → B → C 흐름    │
│ • 메모리 사용량    │ • 요청/응답 기록  │ • 어디서 느려졌나   │
│ • 요청 수/초      │ • 디버그 정보     │ • 병목 지점 파악    │
├───────────────────┼───────────────────┼─────────────────────┤
│   Prometheus      │   Loki            │   Jaeger            │
│   + Grafana       │   + Grafana       │   (추후 적용)       │
└───────────────────┴───────────────────┴─────────────────────┘
```

---

## 6.2 Prometheus + Grafana

### Prometheus: 메트릭 수집

```
┌─────────────────────────────────────────────────────────────┐
│                     Prometheus                               │
│                                                             │
│  15초마다 각 서비스의 /metrics 엔드포인트를 "긁어옴" (scrape) │
│                                                             │
│  User Service:8005/metrics ──┐                              │
│  Chat Service:8002/metrics ──┼──▶ Prometheus DB 저장        │
│  Friend Service:8003/metrics ┘                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**메트릭 예시:**
```
# HTTP 요청 수 (Counter - 계속 증가)
http_requests_total{service="user-service", method="POST", path="/auth/login"} 12345

# 현재 온라인 사용자 수 (Gauge - 오르락내리락)
online_users_count{service="user-service"} 523

# 응답 시간 분포 (Histogram)
http_request_duration_seconds_bucket{le="0.1"} 9800   # 0.1초 이하: 9800건
http_request_duration_seconds_bucket{le="0.5"} 9950   # 0.5초 이하: 9950건
http_request_duration_seconds_bucket{le="1.0"} 9999   # 1초 이하: 9999건
```

### Grafana: 시각화

```bash
# Grafana 접속
open http://localhost:3000
# ID: admin, PW: admin
```

**이 프로젝트의 대시보드:**

| 대시보드 | 주요 패널 |
|---------|----------|
| **User Service** | 회원가입 수, 로그인 수, 응답 시간, 에러율 |
| **Friend Service** | 친구 요청 수, 수락률, API 트래픽 |
| **Chat Service** | 메시지 전송량, 채팅방 생성, SSE 연결 수 |
| **Infrastructure** | MySQL/MongoDB/Redis/Kafka 상태 |

### PromQL 기초 쿼리

```promql
# 분당 요청 수
rate(http_requests_total[1m])

# 평균 응답 시간
rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m])

# 에러율 (%)
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100

# User Service의 POST 요청만
http_requests_total{service="user-service", method="POST"}
```

---

## 6.3 로깅 (Loki + Promtail)

```
┌─────────────────────────────────────────────────────────────┐
│                    로그 수집 흐름                            │
│                                                             │
│  User Service ──┐                                           │
│  Chat Service ──┼──▶ Promtail ──▶ Loki ──▶ Grafana         │
│  Friend Service ┘    (수집)      (저장)    (검색/조회)       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Grafana에서 로그 검색:**
```
# 모든 에러 로그
{service="user-service"} |= "error"

# 특정 사용자의 로그
{service="chat-service"} |= "user_id=123"

# 최근 5분간 로그
{service="friend-service"} | json | __timestamp__ > 5m ago
```

---

## 6.4 알림 (Alertmanager)

```yaml
# infrastructure/docker/prometheus/alert-rules.yml

groups:
  - name: service-alerts
    rules:
      # 서비스 다운 알림
      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.instance }} 서비스가 다운되었습니다"

      # 높은 에러율 알림
      - alert: HighErrorRate
        expr: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "에러율이 5%를 초과했습니다"
```

> 📚 **더 자세한 모니터링 설명**: [Prometheus 설정](./observability/prometheus-setup.md), [Grafana 대시보드](./observability/grafana-dashboards.md)

---

## 6.5 Part 6 학습 체크리스트

- [ ] Metrics, Logs, Traces의 차이를 설명할 수 있다
- [ ] Prometheus가 메트릭을 어떻게 수집하는지 알았다
- [ ] Grafana 대시보드에 접속해봤다
- [ ] Counter vs Gauge의 차이를 이해했다
- [ ] 기본 PromQL 쿼리를 작성할 수 있다

> **Spring Boot에서는?**
> - Spring Boot Actuator + Micrometer로 메트릭 노출
> - Prometheus, Grafana, Loki는 동일하게 사용
> - 모니터링 지식은 언어와 무관하게 100% 재사용 가능

---

# Part 7: 테스트 및 CI/CD (Day 36-42)

## 7.1 테스트 전략

### 테스트 피라미드

```
                    ▲
                   /│\        E2E 테스트 (느림, 비용 높음)
                  / │ \       전체 시스템 통합 테스트
                 /  │  \
                /───┼───\     Integration 테스트 (중간)
               /    │    \    서비스 + DB 연동 테스트
              /     │     \
             /──────┼──────\  Unit 테스트 (빠름, 비용 낮음)
            /       │       \ 함수/클래스 단위 테스트
           ─────────┴─────────
```

### 이 프로젝트의 테스트 구조

```
tests/
├── unit/                    # 단위 테스트 (DB 없이)
│   ├── test_auth.py        # JWT 생성/검증 테스트
│   └── test_validators.py  # 입력 검증 테스트
│
├── integration/            # 통합 테스트 (DB 포함)
│   └── test_full_flow.py   # 회원가입→로그인→채팅 흐름
│
└── e2e/                    # E2E 테스트 (전체 서비스)
    ├── conftest.py         # 공통 설정
    ├── test_user_service.py
    ├── test_friend_service.py
    └── test_chat_service.py
```

---

## 7.2 E2E 테스트 실습

### 테스트 환경 실행

```bash
# 테스트 전용 환경 실행 (별도 포트 사용)
docker-compose -f docker-compose.test.yml up -d

# 테스트 실행
cd tests/e2e
pip install -r requirements.txt
pytest -v --html=report.html
```

### 테스트 코드 예시

```python
# tests/e2e/test_user_service.py

import pytest
import httpx

class TestUserService:
    """User Service E2E 테스트"""

    def test_health_check(self, http_client):
        """헬스 체크 테스트"""
        response = http_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_register_success(self, http_client):
        """회원가입 성공 테스트"""
        response = http_client.post("/auth/register", json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "Test1234!@",
            "display_name": "테스트"
        })
        assert response.status_code == 201
        assert "id" in response.json()

    def test_login_success(self, http_client, registered_user):
        """로그인 성공 테스트"""
        response = http_client.post("/auth/login/json", json={
            "email": registered_user["email"],
            "password": "Test1234!@"
        })
        assert response.status_code == 200
        assert "access_token" in response.json()
```

---

## 7.3 GitHub Actions CI/CD

### CI 파이프라인 (.github/workflows/ci.yml)

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  # 1. 코드 품질 검사
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Ruff (Linter)
        run: ruff check .

  # 2. 서비스별 테스트
  test-user-service:
    runs-on: ubuntu-latest
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: testpass
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: pytest services/user-service/tests/

  # 3. Docker 이미지 빌드
  build:
    needs: [lint, test-user-service]
    runs-on: ubuntu-latest
    steps:
      - name: Build Docker image
        run: docker build -t bigtech-user-service .

  # 4. E2E 테스트 (main 브랜치만)
  e2e-tests:
    needs: [build]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Run E2E tests
        run: pytest tests/e2e/
```

### CI/CD 흐름

```
개발자가 코드 Push
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions                           │
│                                                             │
│  1. Lint (코드 스타일 검사)                                  │
│        │                                                    │
│        ▼                                                    │
│  2. Unit Test (서비스별)                                    │
│        │                                                    │
│        ▼                                                    │
│  3. Docker Build (이미지 생성)                              │
│        │                                                    │
│        ▼                                                    │
│  4. E2E Test (main 브랜치만)                                │
│        │                                                    │
│        ▼                                                    │
│  5. Push to Registry (이미지 저장소)                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
   배포 가능!
```

---

## 7.4 Part 7 학습 체크리스트

- [ ] Unit / Integration / E2E 테스트의 차이를 알았다
- [ ] pytest로 테스트를 실행해봤다
- [ ] E2E 테스트 코드를 읽고 이해할 수 있다
- [ ] GitHub Actions CI 파이프라인을 이해했다
- [ ] PR을 올리면 어떤 검사가 실행되는지 알았다

> **Spring Boot에서는?**
> - JUnit 5 + MockMvc로 테스트
> - Testcontainers로 DB 통합 테스트
> - GitHub Actions 구조는 동일!

---

# Part 8: Spring Boot 마이그레이션 준비 (Day 43-49)

## 8.1 FastAPI vs Spring Boot 비교

### 코드 구조 비교

**FastAPI (Python):**
```python
# main.py
from fastapi import FastAPI, Depends
app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int, db = Depends(get_db)):
    return await db.get(User, user_id)
```

**Spring Boot (Kotlin):**
```kotlin
// UserController.kt
@RestController
@RequestMapping("/users")
class UserController(private val userService: UserService) {

    @GetMapping("/{userId}")
    fun getUser(@PathVariable userId: Long): User {
        return userService.findById(userId)
    }
}
```

### 핵심 개념 매핑

| FastAPI | Spring Boot | 설명 |
|---------|-------------|------|
| `@app.get()` | `@GetMapping` | HTTP GET 엔드포인트 |
| `@app.post()` | `@PostMapping` | HTTP POST 엔드포인트 |
| `Depends()` | `@Autowired` / 생성자 주입 | 의존성 주입 |
| `Pydantic BaseModel` | DTO + `@Valid` | 데이터 검증 |
| `async/await` | `suspend` (코루틴) | 비동기 처리 |
| `SQLAlchemy` | Spring Data JPA | ORM |
| `Beanie` | Spring Data MongoDB | MongoDB ODM |

### 실제 성능 비교 결과 (2026-01-28 테스트)

```
┌────────────────────────────────────────────────────────────────┐
│          FastAPI vs Spring Boot 성능 비교 (100 VUs, 2분)        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  처리량:     FastAPI 727 vs Spring Boot 1,743 (2.4배 차이)     │
│  응답속도:   FastAPI 2.7초 vs Spring Boot 0.7초 (4배 차이)      │
│  에러율:     둘 다 0%                                          │
│                                                                │
│  💡 결론:                                                      │
│  - CPU 작업(bcrypt): Spring Boot가 4배 빠름                    │
│  - I/O 작업(DB조회): FastAPI가 12배 빠름                       │
│  - 전체 처리량: Spring Boot가 2.4배 높음                       │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

> 📊 **상세 보고서**: [성능 비교 보고서](./testing/PERFORMANCE_COMPARISON_REPORT.md)

### 언어와 무관한 것들 (100% 재사용 가능)

```
┌─────────────────────────────────────────────────────────────┐
│              이 프로젝트에서 배운 것 중                       │
│              Spring Boot에서도 그대로 쓸 수 있는 것           │
├─────────────────────────────────────────────────────────────┤
│ ✅ DDD (Bounded Context, Aggregate)                         │
│ ✅ MSA 아키텍처 패턴                                         │
│ ✅ Kafka (Topic 설계, Producer/Consumer)                    │
│ ✅ Kubernetes (Deployment, HPA, Ingress)                    │
│ ✅ Docker (Dockerfile, 이미지 최적화)                        │
│ ✅ Prometheus + Grafana (메트릭, 대시보드)                   │
│ ✅ CI/CD (GitHub Actions)                                   │
│ ✅ API 설계 (REST, 에러 처리)                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 8.2 Spring Boot 학습 로드맵

### 1단계: Java/Kotlin 기초 (1-2주)
- Kotlin 문법 (Java보다 간결)
- 널 안전성, 데이터 클래스
- 코루틴 기초

### 2단계: Spring Framework 핵심 (2-3주)
- IoC Container, DI
- `@Component`, `@Service`, `@Repository`
- `@RestController`, `@RequestMapping`

### 3단계: Spring Boot 실무 (2-3주)
- Spring Boot Starter
- application.yml 설정
- Spring Data JPA
- Spring Kafka

### 추천 학습 자료
- 📚 [Spring Boot 공식 가이드](https://spring.io/guides)
- 📺 [인프런 - 스프링 입문](https://www.inflearn.com/course/스프링-입문-스프링부트)
- 📖 「스프링 부트와 AWS로 혼자 구현하는 웹 서비스」

---

## 8.3 마이그레이션 전략

### 점진적 마이그레이션 (Strangler Fig Pattern)

```
Phase 1: User Service만 Spring Boot로
┌─────────────────────────────────────────────────────────────┐
│                    Kong API Gateway                         │
│                           │                                 │
│     ┌─────────────────────┼─────────────────────┐          │
│     │                     │                     │          │
│     ▼                     ▼                     ▼          │
│ ┌─────────┐        ┌─────────┐          ┌─────────┐       │
│ │  User   │        │  Chat   │          │ Friend  │       │
│ │ Service │        │ Service │          │ Service │       │
│ │(Spring) │        │(FastAPI)│          │(FastAPI)│       │
│ └─────────┘        └─────────┘          └─────────┘       │
│   🆕 새로                기존                기존           │
└─────────────────────────────────────────────────────────────┘

→ User Service를 Spring Boot로 새로 만들고
→ Kong에서 라우팅만 변경
→ 나머지 서비스는 그대로 동작
→ 문제 없으면 다음 서비스 전환
```

### 왜 User Service부터?
1. 가장 단순함 (MySQL만 사용)
2. 다른 서비스에 의존 적음
3. 실패해도 영향 범위 제한적

---

## 8.4 Part 8 학습 체크리스트

- [ ] FastAPI와 Spring Boot의 코드 구조 차이를 이해했다
- [ ] 이 프로젝트의 어떤 지식이 Spring Boot에서도 쓸 수 있는지 알았다
- [ ] Strangler Fig Pattern을 이해했다
- [ ] Spring Boot 학습 로드맵을 세웠다

> 📚 **더 자세한 비교**: [FastAPI vs Spring Boot 문서](./spring-boot/fastapi-vs-springboot.md)

---

# Part 9: 실습 과제 및 부록

## 9.1 주차별 실습 과제

### Week 1: 환경 구성 및 API 탐색
- [ ] 전체 스택 실행 (`docker-compose.msa.yml`)
- [ ] 3개 서비스 Swagger UI에서 모든 API 테스트
- [ ] Grafana 대시보드 살펴보기
- [ ] Kafka UI에서 이벤트 확인

### Week 2: 코드 수정 실습
- [ ] User Service에 새 API 추가 (예: 비밀번호 변경)
- [ ] Pydantic 스키마 작성
- [ ] PR 생성하고 CI 통과 확인

### Week 3: Kafka 이벤트 추가
- [ ] 새로운 Domain Event 정의
- [ ] Producer로 이벤트 발행
- [ ] Kafka UI에서 이벤트 확인

### Week 4: 모니터링 커스터마이징
- [ ] 새로운 메트릭 추가
- [ ] Grafana 패널 추가
- [ ] Alert Rule 작성

---

## 9.2 용어집 (Glossary)

| 용어 | 설명 |
|------|------|
| **Aggregate** | DDD에서 일관성을 유지하는 객체 묶음의 단위 |
| **Bounded Context** | DDD에서 도메인의 경계를 정의하는 개념 |
| **Consumer Group** | Kafka에서 같은 목적으로 메시지를 처리하는 Consumer들의 그룹 |
| **Consumer Lag** | Kafka에서 아직 처리되지 않은 메시지의 수 |
| **Deployment** | K8s에서 Pod의 배포와 관리를 담당하는 리소스 |
| **Domain Event** | 비즈니스에서 의미 있는 사건을 나타내는 객체 |
| **HPA** | Horizontal Pod Autoscaler, CPU/메모리 기반 자동 스케일링 |
| **Ingress** | K8s에서 외부 트래픽을 내부 서비스로 라우팅하는 리소스 |
| **MSA** | Microservices Architecture, 마이크로서비스 아키텍처 |
| **Partition** | Kafka Topic의 병렬 처리 단위 |
| **Pod** | K8s에서 컨테이너 실행의 최소 단위 |
| **Producer** | Kafka에서 메시지를 발행하는 주체 |
| **PromQL** | Prometheus Query Language, 메트릭 조회 언어 |
| **Scrape** | Prometheus가 메트릭을 수집하는 행위 |
| **StatefulSet** | K8s에서 상태를 유지하는 애플리케이션용 리소스 (DB 등) |
| **Topic** | Kafka에서 메시지를 분류하는 단위 |

---

## 9.3 명령어 치트시트

### Docker
```bash
# 전체 스택 실행
docker-compose -f docker-compose.msa.yml up -d

# 로그 확인
docker logs -f bigtech-user-service

# 컨테이너 접속
docker exec -it bigtech-user-service bash

# 정리
docker-compose -f docker-compose.msa.yml down -v
```

### Kubernetes
```bash
# 리소스 확인
kubectl get all -n bigtech-chat
kubectl get pods -n bigtech-chat

# 로그 확인
kubectl logs -f deployment/user-service -n bigtech-chat

# Pod 접속
kubectl exec -it <pod-name> -n bigtech-chat -- bash

# 배포
kubectl apply -f k8s/manifests/
```

### 테스트
```bash
# E2E 테스트
pytest tests/e2e/ -v

# 커버리지
pytest --cov=app tests/

# HTML 리포트
pytest --html=report.html
```

---

## 9.4 자주 묻는 질문 (FAQ)

**Q: 왜 DB를 3개나 사용하나요?**
> MySQL은 관계형 데이터(사용자, 친구), MongoDB는 대용량 문서(메시지), Redis는 캐시와 실시간 상태에 최적화되어 있습니다. 각 DB의 장점을 살린 것입니다.

**Q: Kafka 없이 REST API로만 통신하면 안 되나요?**
> 가능하지만, 서비스 간 결합도가 높아지고 장애 전파 위험이 있습니다. Kafka를 사용하면 서비스가 독립적으로 동작하고, 재시도/복구가 용이합니다.

**Q: 모든 서비스를 Spring Boot로 바꿔야 하나요?**
> 아닙니다. 필요에 따라 일부만 전환해도 됩니다. 성능이 중요한 서비스만 전환하거나, 팀 역량에 맞게 점진적으로 진행할 수 있습니다.

**Q: 이 프로젝트를 포트폴리오에 어떻게 설명하면 좋을까요?**
> "FastAPI 기반 실시간 채팅 백엔드를 MSA로 전환하고, Kafka 이벤트 스트리밍, K8s 배포, Prometheus 모니터링을 구축한 경험이 있습니다."

---

## 9.5 추가 학습 자료

### 공식 문서
- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [Kafka 공식 문서](https://kafka.apache.org/documentation/)
- [Kubernetes 공식 문서](https://kubernetes.io/docs/)
- [Prometheus 공식 문서](https://prometheus.io/docs/)

### 추천 도서
- 「도메인 주도 설계 핵심」 - 반 버논
- 「마이크로서비스 패턴」 - 크리스 리처드슨
- 「쿠버네티스 인 액션」 - 마르코 룩샤

---

**문서 버전**: v1.1
**최종 업데이트**: 2026-01-28
**작성자**: Claude Code

---

> 이 문서에 대한 피드백이나 질문이 있으시면 GitHub Issues에 등록해주세요.

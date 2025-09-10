# BigTech Chat Backend

실시간 채팅 애플리케이션의 백엔드 서비스입니다. FastAPI를 기반으로 하며, MySQL과 MongoDB를 활용한 하이브리드 데이터베이스 아키텍처를 사용합니다.

## 📋 목차

- [프로젝트 개요](#프로젝트-개요)
- [기술 스택](#기술-스택)
- [아키텍처](#아키텍처)
- [ERD 다이어그램](#erd-다이어그램)
- [설치 및 실행](#설치-및-실행)
- [API 문서](#api-문서)
- [프로젝트 구조](#프로젝트-구조)
- [개발 로드맵](#개발-로드맵)

## 🎯 프로젝트 개요

BigTech Chat은 현대적인 실시간 채팅 애플리케이션으로, 1:1 채팅과 그룹 채팅을 지원하며 확장 가능한 아키텍처를 제공합니다.

### 주요 기능

- 🔐 **사용자 인증**: JWT 기반 인증 시스템
- 💬 **1:1 채팅**: 개인 간 실시간 메시징
- 👥 **그룹 채팅**: 다중 사용자 그룹 채팅방
- 🤝 **친구 관리**: 친구 요청, 승인, 관리 시스템
- 🚫 **사용자 차단**: 스팸 및 부적절한 사용자 차단 기능
- 📱 **실시간 알림**: WebSocket 기반 실시간 메시징
- 🔍 **메시지 검색**: 향후 Elasticsearch 통합 예정

## 🛠 기술 스택

### Backend Framework
- **FastAPI**: 고성능 웹 프레임워크
- **Python 3.9+**: 프로그래밍 언어
- **Pydantic**: 데이터 검증 및 시리얼라이제이션

### 데이터베이스
- **MySQL 8.0**: 관계형 데이터 (사용자, 채팅방, 관계)
- **MongoDB 6.0**: 문서형 데이터 (메시지, 검색 인덱스)
- **Redis**: 캐시 및 세션 관리 (향후 구현)

### ORM/ODM
- **SQLAlchemy**: MySQL ORM
- **Beanie**: MongoDB ODM (Motor 기반)

### 인증 및 보안
- **JWT**: 토큰 기반 인증
- **bcrypt**: 비밀번호 해싱
- **python-jose**: JWT 토큰 처리

### 개발 도구
- **Docker**: 컨테이너화
- **Docker Compose**: 로컬 개발 환경
- **Uvicorn**: ASGI 서버

## 🏗 아키텍처

### 전체 아키텍처
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Database      │
│   (React)       │◄──►│   (FastAPI)     │◄──►│   MySQL +       │
│                 │    │                 │    │   MongoDB       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 데이터베이스 설계 철학
- **MySQL**: 구조적/관계적 데이터 저장
  - 사용자 정보, 친구 관계, 채팅방 메타데이터
- **MongoDB**: 대용량/유연한 데이터 저장
  - 메시지 데이터, 검색 인덱스

### 발전 로드맵
- **현재**: MVP (Monolithic FastAPI)
- **1단계**: DDD (Domain-Driven Design) 적용
- **2단계**: MSA (Microservices Architecture) 전환
- **최종**: Spring Boot로 이전 (선택사항)

## 📊 ERD 다이어그램

### Draw.io로 ERD 작성하기

1. **Draw.io 접속**: https://app.diagrams.net/
2. **새 다이어그램 생성**: "Create New Diagram" → "Entity Relation"
3. **아래 테이블들을 참고하여 ERD 작성**

### MySQL 테이블 구조

#### Users (사용자)
```sql
users
├── id (PK, INT, AUTO_INCREMENT)
├── email (UNIQUE, VARCHAR(255))
├── password_hash (VARCHAR(255))
├── username (UNIQUE, VARCHAR(50))
├── display_name (VARCHAR(100), NULL)
├── is_active (BOOLEAN, DEFAULT TRUE)
├── created_at (DATETIME)
└── updated_at (DATETIME)
```

#### Chat Rooms (1:1 채팅방)
```sql
chat_rooms
├── id (PK, INT, AUTO_INCREMENT)
├── user_id_1 (FK → users.id, INDEX)
├── user_id_2 (FK → users.id, INDEX)
├── is_active (BOOLEAN, DEFAULT TRUE)
├── created_at (DATETIME)
└── updated_at (DATETIME)
```

#### Group Chat Rooms (그룹 채팅방)
```sql
group_chat_rooms
├── id (PK, INT, AUTO_INCREMENT)
├── name (VARCHAR(255))
├── description (TEXT, NULL)
├── is_private (BOOLEAN, DEFAULT FALSE)
├── created_by (FK → users.id)
├── max_members (INT, DEFAULT 100)
├── is_active (BOOLEAN, DEFAULT TRUE)
├── created_at (DATETIME)
└── updated_at (DATETIME)
```

#### Group Room Members (그룹 멤버)
```sql
group_room_members
├── id (PK, INT, AUTO_INCREMENT)
├── user_id (FK → users.id, INDEX)
├── group_room_id (FK → group_chat_rooms.id, INDEX)
├── role (VARCHAR(20), DEFAULT 'member') -- owner, admin, member
├── is_active (BOOLEAN, DEFAULT TRUE)
├── joined_at (DATETIME)
├── left_at (DATETIME, NULL)
├── created_at (DATETIME)
└── updated_at (DATETIME)
```

#### Friendships (친구 관계)
```sql
friendships
├── id (PK, INT, AUTO_INCREMENT)
├── user_id_1 (FK → users.id, INDEX)
├── user_id_2 (FK → users.id, INDEX)
├── status (VARCHAR(20), DEFAULT 'pending') -- pending, accepted, rejected
├── created_at (DATETIME)
└── updated_at (DATETIME)
```

#### Block Users (차단 사용자)
```sql
block_users
├── id (PK, INT, AUTO_INCREMENT)
├── user_id (FK → users.id, INDEX) -- 차단한 사용자
├── blocked_user_id (FK → users.id, INDEX) -- 차단된 사용자
└── created_at (DATETIME)
```

### MongoDB 컬렉션 구조

#### Messages (메시지)
```javascript
messages: {
  _id: ObjectId,
  user_id: Number,           // 발송자 ID
  room_id: Number,           // 채팅방 ID  
  room_type: String,         // "private" | "group"
  content: String,           // 메시지 내용
  message_type: String,      // "text" | "image" | "file" | "system"
  reply_to: String,          // 답글 대상 메시지 ID (optional)
  is_edited: Boolean,        // 수정 여부
  edited_at: Date,           // 수정 시간 (optional)
  created_at: Date,          // 생성 시간
  updated_at: Date           // 수정 시간
}

// 인덱스
- { room_id: 1, room_type: 1, created_at: -1 }
- { user_id: 1, created_at: -1 }
- { room_type: 1, created_at: -1 }
```

## 🚀 설치 및 실행

### 사전 요구사항
- Docker & Docker Compose
- Python 3.9+ (로컬 개발 시)

### Docker로 실행 (권장)

```bash
# 저장소 클론
git clone <repository-url>
cd bigtech_chat-be

# 환경 변수 설정
cp .env.example .env
# .env 파일 수정

# 컨테이너 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f app
```

### 로컬 개발 환경

```bash
# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 데이터베이스 실행 (Docker)
docker-compose up -d mysql mongodb redis

# 애플리케이션 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 환경 변수

`.env` 파일에 다음 변수들을 설정하세요:

```bash
# Database URLs
MONGO_URL=mongodb://mongodb:27017
MYSQL_URL=mysql+aiomysql://chatuser:chatpass@mysql:3306/chatdb

# JWT Settings
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_HOURS=24

# Debug
DEBUG=true
```

## 📚 API 문서

애플리케이션 실행 후 다음 URL에서 API 문서를 확인할 수 있습니다:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### 주요 API 엔드포인트

```
Authentication:
POST   /auth/register     # 사용자 회원가입
POST   /auth/login        # 로그인
POST   /auth/logout       # 로그아웃

Users:
GET    /users/me          # 내 정보 조회
PUT    /users/me          # 내 정보 수정

Chat Rooms:
GET    /chat-rooms        # 채팅방 목록
POST   /chat-rooms        # 1:1 채팅방 생성
GET    /chat-rooms/{id}   # 채팅방 상세

Group Rooms:
GET    /group-rooms       # 그룹 채팅방 목록  
POST   /group-rooms       # 그룹 채팅방 생성
POST   /group-rooms/{id}/join  # 그룹 참여

Messages:
GET    /messages/{room_id}     # 메시지 조회
POST   /messages               # 메시지 전송
PUT    /messages/{id}          # 메시지 수정
DELETE /messages/{id}          # 메시지 삭제

Friends:
GET    /friends               # 친구 목록
POST   /friends/request       # 친구 요청
PUT    /friends/{id}/accept   # 친구 승인

Health:
GET    /health               # 서버 상태 확인
```

## 📁 프로젝트 구조

```
bigtech_chat-be/
├── app/
│   ├── api/                    # API 라우터
│   │   ├── health.py          # 헬스체크
│   │   ├── auth.py            # 인증 관련
│   │   ├── users.py           # 사용자 관리
│   │   ├── chat.py            # 채팅 관련
│   │   └── __init__.py
│   ├── core/                   # 핵심 설정
│   │   ├── config.py          # 환경 설정
│   │   └── __init__.py
│   ├── database/               # 데이터베이스 연결
│   │   ├── mysql.py           # MySQL 연결
│   │   ├── mongodb.py         # MongoDB 연결
│   │   └── __init__.py
│   ├── models/                 # 데이터 모델
│   │   ├── users.py           # 사용자 모델
│   │   ├── chat_rooms.py      # 1:1 채팅방 모델
│   │   ├── group_chat_rooms.py # 그룹 채팅방 모델
│   │   ├── group_room_members.py # 그룹 멤버 모델
│   │   ├── messages.py        # 메시지 모델
│   │   ├── friendships.py     # 친구 관계 모델
│   │   ├── block_users.py     # 차단 사용자 모델
│   │   └── __init__.py
│   ├── schemas/                # Pydantic 스키마
│   │   ├── user.py            # 사용자 스키마
│   │   ├── chat_room.py       # 채팅방 스키마
│   │   ├── group_chat_room.py # 그룹 채팅방 스키마
│   │   ├── group_room_member.py # 그룹 멤버 스키마
│   │   ├── message.py         # 메시지 스키마
│   │   ├── friendship.py      # 친구 관계 스키마
│   │   ├── block_user.py      # 차단 사용자 스키마
│   │   └── __init__.py
│   ├── utils/                  # 유틸리티
│   │   ├── auth.py            # 인증 유틸리티
│   │   └── __init__.py
│   ├── main.py                # FastAPI 앱 엔트리포인트
│   └── __init__.py
├── docker-compose.yml         # Docker Compose 설정
├── Dockerfile                 # Docker 이미지 설정
├── requirements.txt           # Python 의존성
├── .env.example              # 환경 변수 예시
├── .gitignore                # Git 무시 파일
├── README.md                 # 프로젝트 문서
└── CLAUDE.md                 # Claude 개발 가이드
```

## 🛣 개발 로드맵

### Phase 1: MVP (현재)
- ✅ 기본 사용자 인증 시스템
- ✅ 1:1 채팅 기능
- ✅ 그룹 채팅 기능  
- ✅ 친구 관리 시스템
- ✅ 사용자 차단 기능
- ✅ RESTful API 설계

### Phase 2: 실시간 기능 (계획)
- 🔄 WebSocket 실시간 메시징
- 🔄 실시간 알림 시스템
- 🔄 온라인 상태 표시
- 🔄 타이핑 인디케이터

### Phase 3: 고급 기능 (계획)
- 📋 파일 업로드/다운로드
- 🔍 메시지 검색 (Elasticsearch)
- 📱 푸시 알림
- 🎵 음성/영상 메시지

### Phase 4: 확장성 (장기)
- 🏗 마이크로서비스 아키텍처
- 📊 Redis 캐싱 시스템  
- 📈 Kafka 메시징 큐
- ☁️ 클라우드 배포 (K8s)

## 🤝 기여하기

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 있습니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

---

## 📞 연락처

프로젝트 관련 문의사항이 있으시면 언제든 연락해 주세요.

**Happy Coding! 🚀**
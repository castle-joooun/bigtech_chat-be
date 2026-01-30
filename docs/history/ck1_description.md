# CK1 (Checkpoint 1) - FastAPI 인증 시스템 구축 완료

## 📝 체크포인트 개요

**CK1**은 BigTech Chat Backend 프로젝트의 첫 번째 주요 체크포인트로, 완전한 인증 시스템과 기본 FastAPI 애플리케이션 구조를 구축한 상태입니다.

**완료 일시**: 2025-09-10  
**주요 목표**: 사용자 인증/인가 시스템 구현 및 기본 API 인프라 완성

---

## 🏗 프로젝트 아키텍처

### 전체 구조
```
FastAPI Backend (Python 3.9+)
├── 하이브리드 데이터베이스
│   ├── MySQL 8.0 (관계형 데이터)
│   └── MongoDB 6.0 (문서형 데이터)
├── JWT 토큰 기반 인증
├── Pydantic 스키마 검증
└── SQLAlchemy + Beanie ORM/ODM
```

### 기술 스택
- **백엔드**: FastAPI, Python 3.9+, Uvicorn
- **데이터베이스**: MySQL + MongoDB (하이브리드)
- **ORM/ODM**: SQLAlchemy (async) + Beanie (Motor 기반)
- **인증**: JWT (python-jose), bcrypt
- **검증**: Pydantic v2, email-validator
- **개발도구**: Docker, python-dotenv

---

## 📁 파일 구조

### 생성된 주요 파일들

```
bigtech_chat-be/
├── app/
│   ├── api/
│   │   ├── auth.py          ⭐ 인증 API 엔드포인트
│   │   └── health.py        ⭐ 헬스체크 API
│   ├── core/
│   │   └── config.py        ⭐ 설정 관리 (JWT, DB 등)
│   ├── database/
│   │   ├── __init__.py      ⭐ 데이터베이스 초기화
│   │   ├── mongodb.py       ⭐ MongoDB 연결 설정
│   │   └── mysql.py         ⭐ MySQL 연결 설정 + get_async_session
│   ├── models/              ⭐ SQLAlchemy + Beanie 모델들
│   │   ├── users.py         - User 모델 (외래키 관계 포함)
│   │   ├── chat_rooms.py    - 1:1 채팅방 모델
│   │   ├── group_chat_rooms.py - 그룹 채팅방 모델
│   │   ├── group_room_members.py - 그룹 멤버 모델
│   │   ├── friendships.py   - 친구 관계 모델
│   │   ├── block_users.py   - 차단 사용자 모델
│   │   ├── messages.py      - 메시지 모델 (MongoDB)
│   │   └── message_search.py - 검색 모델 (주석처리)
│   ├── schemas/             ⭐ Pydantic 스키마들
│   │   ├── user.py          - 사용자 관련 스키마
│   │   ├── chat_room.py     - 채팅방 스키마
│   │   ├── friendship.py    - 친구 관계 스키마
│   │   ├── group_chat_room.py - 그룹 채팅방 스키마
│   │   ├── group_room_member.py - 그룹 멤버 스키마
│   │   ├── message.py       - 메시지 스키마
│   │   └── block_user.py    - 차단 사용자 스키마
│   ├── utils/
│   │   └── auth.py          ⭐ 인증 유틸리티 (JWT, 비밀번호)
│   └── main.py              ⭐ FastAPI 앱 엔트리포인트
├── .env.example             ⭐ 환경변수 예시
├── requirements.txt         ⭐ Python 의존성
├── schema.sql              ⭐ ERDCloud용 SQL DDL
├── ERD_GUIDE.md            ⭐ ERD 작성 가이드
├── README.md               ⭐ 프로젝트 문서
└── CLAUDE.md               ⭐ 개발 가이드
```

---

## 🔐 인증 시스템 상세

### JWT 토큰 기반 인증
- **토큰 형식**: Bearer JWT
- **만료 시간**: 24시간 (설정 가능)
- **알고리즘**: HS256
- **페이로드**: `{"sub": user_id, "email": user_email, "exp": expiration}`

### 비밀번호 정책
- **길이**: 8-16자
- **필수 포함**: 영문자 + 숫자 + 특수문자
- **해싱**: bcrypt (cost factor 12)
- **검증 함수**: `validate_password()` in `utils/auth.py`

### 인증 API 엔드포인트

| Method | Endpoint | Description | Request Body |
|--------|----------|-------------|--------------|
| `POST` | `/auth/register` | 회원가입 | `UserCreate` |
| `POST` | `/auth/login` | 로그인 (OAuth2) | `OAuth2PasswordRequestForm` |
| `POST` | `/auth/login/json` | 로그인 (JSON) | `UserLogin` |
| `GET`  | `/auth/me` | 현재 사용자 정보 | - |
| `POST` | `/auth/logout` | 로그아웃 | - |
| `POST` | `/auth/refresh` | 토큰 갱신 | - |

---

## 🗃 데이터베이스 설계

### MySQL 테이블 (관계형 데이터)

#### Users 테이블
```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

#### 주요 관계 테이블들
- **chat_rooms**: 1:1 채팅방 (`user_id_1`, `user_id_2`)
- **group_chat_rooms**: 그룹 채팅방 (`created_by → users.id`)
- **group_room_members**: 그룹 멤버십 (`user_id`, `group_room_id`)
- **friendships**: 친구 관계 (`user_id_1`, `user_id_2`, `status`)
- **block_users**: 차단 관계 (`user_id`, `blocked_user_id`)

### MongoDB 컬렉션 (문서형 데이터)

#### Messages 컬렉션
```javascript
{
    _id: ObjectId,
    user_id: Number,           // 발송자 ID
    room_id: Number,           // 채팅방 ID
    room_type: String,         // "private" | "group"
    content: String,           // 메시지 내용
    message_type: String,      // "text" | "image" | "file" | "system"
    reply_to: String,          // 답글 대상 메시지 ID
    is_edited: Boolean,
    edited_at: Date,
    created_at: Date,
    updated_at: Date
}
```

### 외래키 관계
- **완전한 관계형 무결성**: 모든 MySQL 테이블에 `ForeignKey` 제약조건 설정
- **양방향 관계**: SQLAlchemy `relationship()` 설정으로 ORM 레벨 관계 지원
- **Cascade 삭제**: 사용자 삭제 시 관련 데이터 자동 삭제

---

## 📋 Pydantic 스키마 시스템

### 스키마 패턴
각 모델마다 다음 스키마들을 구현:

1. **Base**: 공통 필드
2. **Create**: 생성용 (비밀번호 포함)
3. **Update**: 수정용 (선택적 필드)
4. **Response**: 응답용 (민감정보 제외)
5. **WithDetails**: 관계 데이터 포함

### 주요 검증 기능
- **이메일 검증**: `EmailStr` 타입
- **길이 제한**: `min_length`, `max_length`
- **필드 설명**: `Field(..., description="...")` 
- **타입 안전성**: `TYPE_CHECKING`으로 순환 import 방지

---

## ⚙️ 설정 관리

### 환경변수 (.env)
```bash
# Database URLs
MONGO_URL=mongodb://localhost:27017/bigtech_chat
MYSQL_URL=mysql+aiomysql://chatuser:chatpass@localhost:3306/chatdb

# JWT Settings
SECRET_KEY=your-super-secret-key-change-in-production-please
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_HOURS=24

# App Settings
DEBUG=true
APP_NAME="BigTech Chat Backend"
VERSION=1.0.0
```

### Pydantic Settings
- **자동 타입 변환**: 환경변수를 Python 타입으로 변환
- **기본값 지원**: 필수/선택 설정 구분
- **검증**: 잘못된 설정값 조기 감지

---

## 🔧 핵심 유틸리티 함수

### 인증 관련 (`app/utils/auth.py`)
```python
# 비밀번호 관리
def verify_password(plain_password, hashed_password) -> bool
def get_password_hash(password) -> str
def validate_password(password: str) -> bool

# JWT 토큰 관리
def create_access_token(data: Dict, expires_delta: Optional[timedelta]) -> str
def decode_access_token(token: str) -> Optional[Dict[str, Any]]
```

### 데이터베이스 관리
```python
# MySQL
async def get_async_session() -> AsyncGenerator[AsyncSession, None]
async def init_mysql_db()
async def check_mysql_connection()

# MongoDB  
async def connect_to_mongo()
async def init_mongodb()
async def close_mongo()
```

---

## 🚀 실행 방법

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정
```bash
cp .env.example .env
# .env 파일 수정
```

### 3. 데이터베이스 실행 (Docker)
```bash
# MySQL + MongoDB 컨테이너 실행 필요
```

### 4. 애플리케이션 실행
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. API 문서 확인
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## ✅ 완료된 주요 기능들

### 🔐 인증/인가
- [x] 사용자 회원가입 (이메일/사용자명 중복 체크)
- [x] JWT 토큰 기반 로그인
- [x] 비밀번호 정책 검증 및 해싱
- [x] 토큰 갱신 시스템
- [x] 현재 사용자 정보 조회

### 🗄 데이터베이스
- [x] MySQL 비동기 연결 및 ORM 설정
- [x] MongoDB 비동기 연결 및 ODM 설정  
- [x] 완전한 외래키 관계 설정
- [x] 데이터베이스 초기화 시스템

### 📝 스키마 및 검증
- [x] 8개 주요 엔티티의 Pydantic 스키마
- [x] Request/Response 모델 분리
- [x] 타입 안전성 및 검증 규칙

### 📚 문서화
- [x] 완전한 API 문서 (Swagger/ReDoc)
- [x] ERD 작성 가이드
- [x] 프로젝트 README 
- [x] ERDCloud SQL DDL

---

## 🔄 다음 체크포인트 예상

### CK2 목표 (예상)
- 채팅 관련 API 구현 (1:1, 그룹)
- 메시지 CRUD 시스템
- 실시간 WebSocket 연결

### CK3 목표 (예상)  
- 친구 관리 시스템
- 사용자 차단 기능
- 알림 시스템

### CK4 목표 (예상)
- 파일 업로드/다운로드
- 이미지 처리
- 캐싱 시스템 (Redis)

---

## 🐛 알려진 이슈

### 해결된 이슈들
- ✅ `get_async_session` import 오류 → mysql.py에 alias 추가
- ✅ Pydantic `TYPE_CHECKING` 오류 → 스키마 구조 수정
- ✅ SQLAlchemy 외래키 관계 미설정 → 모든 모델에 관계 추가
- ✅ Git merge conflicts → 수동 해결 및 통합

### 현재 제한사항
- ⚠️ 데이터베이스 서버 실행 필요 (MySQL, MongoDB)
- ⚠️ 실제 테스트를 위해서는 Docker 환경 구성 필요
- ⚠️ 일부 dependency 충돌 경고 (기능에는 영향 없음)

---

## 📈 성과 지표

### 코드 품질
- **총 라인 수**: ~2,500+ lines
- **모델 수**: 7개 (MySQL 6개 + MongoDB 1개)  
- **API 엔드포인트**: 6개 (인증 관련)
- **스키마 수**: 50+ 개 (8개 파일)
- **테스트 커버리지**: 0% (향후 구현 예정)

### 아키텍처 품질
- ✅ **관심사 분리**: API, 모델, 스키마, 유틸리티 분리
- ✅ **타입 안전성**: Pydantic과 SQLAlchemy 타입 힌트
- ✅ **보안**: JWT + bcrypt 조합
- ✅ **확장성**: 하이브리드 DB 아키텍처
- ✅ **유지보수성**: 체계적인 폴더 구조

---

## 💡 기술적 의사결정

### 하이브리드 데이터베이스 선택
- **MySQL**: 사용자, 관계 데이터 (ACID 보장 필요)
- **MongoDB**: 메시지 데이터 (유연성, 확장성 필요)

### JWT vs 세션 기반 인증
- **JWT 선택**: 무상태, 확장성, MSA 호환성

### Pydantic v2 사용
- **성능**: v1 대비 5-50배 빠른 검증
- **타입 안전성**: 런타임 타입 검사

### 비동기 I/O 전면 채택
- **SQLAlchemy**: async/await 패턴
- **Motor**: MongoDB 비동기 드라이버
- **FastAPI**: 네이티브 비동기 지원

---

## 📖 학습 및 참고 자료

### 공식 문서
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Async Tutorial](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Beanie ODM](https://roman-right.github.io/beanie/)
- [Pydantic V2](https://docs.pydantic.dev/latest/)

### ERD 및 데이터베이스 설계
- [ERDCloud](https://www.erdcloud.com/) - ERD 자동 생성
- MySQL 8.0 Reference Manual
- MongoDB Manual

---

**CK1 완료일**: 2025-09-10  
**다음 체크포인트**: CK2 (채팅 API 구현)  
**프로젝트 진행률**: 25% (MVP 기준)
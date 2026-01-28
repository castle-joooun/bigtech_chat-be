# User Service Dockerfile (Multi-stage Build)
# ============================================

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /build

# 빌드에 필요한 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 가상환경 생성
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# Stage 2: Runtime
FROM python:3.11-slim AS runtime

WORKDIR /app

# curl만 설치 (헬스체크용)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# 빌드된 가상환경 복사
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 애플리케이션 코드 복사
COPY --chown=appuser:appuser . .

# 비-root 사용자로 전환
USER appuser

# 포트 노출
EXPOSE 8005

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8005/health || exit 1

# 워커 수 환경변수 (기본값 4)
ENV WORKERS=4

# 애플리케이션 실행 (Gunicorn + Uvicorn 워커로 멀티프로세스 처리)
CMD ["sh", "-c", "gunicorn main:app -w ${WORKERS} -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8005 --timeout 120"]

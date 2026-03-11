# API Gateway Dockerfile (Multi-stage Build)
# ============================================

# Stage 1: Builder - Maven 빌드
FROM maven:3.9-eclipse-temurin-21 AS builder

WORKDIR /build

# 1) 부모 pom.xml과 모든 모듈 pom.xml 복사 (의존성 캐싱용)
COPY pom.xml ./
COPY common-lib/pom.xml ./common-lib/
COPY user-service/pom.xml ./user-service/
COPY friend-service/pom.xml ./friend-service/
COPY chat-service/pom.xml ./chat-service/
COPY api-gateway/pom.xml ./api-gateway/

# 2) 의존성 다운로드 (캐시 레이어)
RUN mvn dependency:go-offline -pl common-lib,api-gateway -am -B

# 3) 소스 코드 복사
COPY common-lib/src ./common-lib/src
COPY api-gateway/src ./api-gateway/src

# 4) 빌드 (clean 없이 증분 빌드)
RUN mvn package -pl common-lib,api-gateway -am -DskipTests -B


# Stage 2: Runtime - 경량 JRE 이미지
FROM eclipse-temurin:21-jre

WORKDIR /app

# curl 설치 (헬스체크용) 및 비-root 사용자 생성
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r spring && useradd -r -g spring spring

# 빌드된 JAR 복사
COPY --from=builder /build/api-gateway/target/*.jar app.jar

# logs 디렉토리 생성 및 소유권 설정
RUN mkdir -p /app/logs && chown -R spring:spring /app

# 비-root 사용자로 전환
USER spring:spring

# JVM 컨테이너 최적화 설정
ENV JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0 -XX:+UseG1GC -Djava.security.egd=file:/dev/./urandom"

# 포트 노출
EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/actuator/health || exit 1

# 애플리케이션 실행
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]

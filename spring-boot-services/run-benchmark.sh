#!/bin/bash
# =============================================================================
# Spring Boot MSA Benchmark Script
#
# 사용법:
#   ./run-benchmark.sh          # 기본 실행 (50 VU, 60초)
#   ./run-benchmark.sh 100 120  # 100 VU, 120초
# =============================================================================

set -e

MAX_VUS=${1:-50}
DURATION=${2:-60}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
K6_SCRIPT="/Users/castle_mac/Desktop/project/bigtech_chat-be/microservices/tests/load/fastapi-vs-spring-benchmark.js"
RESULT_DIR="$SCRIPT_DIR/benchmark-results"

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN} Spring Boot MSA Benchmark${NC}"
echo -e "${GREEN} VUs: $MAX_VUS | Duration: ${DURATION}s${NC}"
echo -e "${GREEN}============================================================${NC}"

# 결과 디렉토리 생성
mkdir -p "$RESULT_DIR"

# Step 1: 서비스 상태 확인
echo -e "\n${YELLOW}[1/5] 서비스 상태 확인...${NC}"
if ! curl -s http://localhost:8081/actuator/health | grep -q "UP"; then
    echo -e "${RED}user-service가 실행 중이 아닙니다. docker-compose up -d 실행하세요.${NC}"
    exit 1
fi
if ! curl -s http://localhost:8003/actuator/health | grep -q "UP"; then
    echo -e "${RED}friend-service가 실행 중이 아닙니다.${NC}"
    exit 1
fi
if ! curl -s http://localhost:8002/actuator/health | grep -q "UP"; then
    echo -e "${RED}chat-service가 실행 중이 아닙니다.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ 모든 서비스 정상${NC}"

# Step 2: 데이터베이스 초기화
echo -e "\n${YELLOW}[2/5] 데이터베이스 초기화...${NC}"
docker exec bigtech-mysql mysql -uchatuser -pchatpassword bigtech_chat -e "
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE friendships;
TRUNCATE TABLE chat_rooms;
TRUNCATE TABLE users;
SET FOREIGN_KEY_CHECKS = 1;
ALTER TABLE users AUTO_INCREMENT = 1;
ALTER TABLE friendships AUTO_INCREMENT = 1;
ALTER TABLE chat_rooms AUTO_INCREMENT = 1;
" 2>/dev/null

docker exec bigtech-mongodb mongosh -u admin -p adminpassword --authenticationDatabase admin bigtech_chat --eval "
db.messages.deleteMany({});
db.message_read_status.deleteMany({});
" > /dev/null 2>&1

echo -e "${GREEN}✓ MySQL & MongoDB 초기화 완료${NC}"

# Step 3: JVM 웜업
echo -e "\n${YELLOW}[3/5] JVM 웜업 중... (10회 회원가입/로그인)${NC}"
for i in {1..10}; do
    curl -s -X POST http://localhost:8081/api/auth/register \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"warmup$i@test.com\",\"username\":\"warmup$i\",\"password\":\"Test1234!\",\"displayName\":\"Warmup $i\"}" > /dev/null
    curl -s -X POST http://localhost:8081/api/auth/login/json \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"warmup$i@test.com\",\"password\":\"Test1234!\"}" > /dev/null
    echo -n "."
done
echo ""
echo -e "${GREEN}✓ JVM 웜업 완료${NC}"

# Step 4: 웜업 데이터 삭제
echo -e "\n${YELLOW}[4/5] 웜업 데이터 정리...${NC}"
docker exec bigtech-mysql mysql -uchatuser -pchatpassword bigtech_chat -e "
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE friendships;
TRUNCATE TABLE chat_rooms;
TRUNCATE TABLE users;
SET FOREIGN_KEY_CHECKS = 1;
ALTER TABLE users AUTO_INCREMENT = 1;
ALTER TABLE friendships AUTO_INCREMENT = 1;
ALTER TABLE chat_rooms AUTO_INCREMENT = 1;
" 2>/dev/null
echo -e "${GREEN}✓ 정리 완료${NC}"

# Step 5: 벤치마크 실행
echo -e "\n${YELLOW}[5/5] 벤치마크 실행...${NC}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULT_FILE="$RESULT_DIR/spring-benchmark-$TIMESTAMP.json"

cd /Users/castle_mac/Desktop/project/bigtech_chat-be/microservices/tests/load

k6 run \
    --out json="$RESULT_FILE" \
    -e TARGET=spring \
    -e MAX_VUS=$MAX_VUS \
    -e DURATION="${DURATION}s" \
    "$K6_SCRIPT"

EXIT_CODE=$?

# 결과 요약
echo -e "\n${GREEN}============================================================${NC}"
echo -e "${GREEN} 벤치마크 완료${NC}"
echo -e "${GREEN}============================================================${NC}"
echo -e "결과 파일: $RESULT_FILE"

# JSON 결과에서 요약 추출
if [ -f "$RESULT_FILE" ]; then
    echo -e "\n${YELLOW}결과 요약:${NC}"
    # 마지막 줄에서 summary 추출
    tail -1 "$RESULT_FILE" 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"  총 요청: {data.get('total_requests', 'N/A')}\")
    print(f\"  에러: {data.get('errors', 'N/A')}\")
    print(f\"  성공률: {100 - float(data.get('errors', 0)) / max(float(data.get('total_requests', 1)), 1) * 100:.2f}%\")
except:
    pass
" 2>/dev/null || true
fi

exit $EXIT_CODE

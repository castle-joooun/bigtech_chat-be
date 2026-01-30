#!/bin/bash

# =============================================================================
# Kong API Gateway Configuration Script
# 서비스 등록 및 라우팅 설정
# =============================================================================

KONG_ADMIN_URL="http://localhost:8001"

echo "🚀 Configuring Kong API Gateway..."
echo ""

# =============================================================================
# 1. User Service 등록
# =============================================================================
echo "📦 Registering User Service..."

# Service 등록
curl -s -X POST "${KONG_ADMIN_URL}/services" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "user-service",
    "url": "http://user-service:8005"
  }' | jq .

# Routes 등록 - /api/auth/*
curl -s -X POST "${KONG_ADMIN_URL}/services/user-service/routes" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "user-auth-route",
    "paths": ["/api/auth"],
    "strip_path": true,
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  }' | jq .

# Routes 등록 - /api/profile/*
curl -s -X POST "${KONG_ADMIN_URL}/services/user-service/routes" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "user-profile-route",
    "paths": ["/api/profile"],
    "strip_path": true,
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  }' | jq .

# Routes 등록 - /api/users/*
curl -s -X POST "${KONG_ADMIN_URL}/services/user-service/routes" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "user-users-route",
    "paths": ["/api/users"],
    "strip_path": true,
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  }' | jq .

echo "✅ User Service registered"
echo ""

# =============================================================================
# 2. Friend Service 등록
# =============================================================================
echo "📦 Registering Friend Service..."

# Service 등록
curl -s -X POST "${KONG_ADMIN_URL}/services" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "friend-service",
    "url": "http://friend-service:8003"
  }' | jq .

# Routes 등록 - /api/friends/*
curl -s -X POST "${KONG_ADMIN_URL}/services/friend-service/routes" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "friend-route",
    "paths": ["/api/friends"],
    "strip_path": true,
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  }' | jq .

echo "✅ Friend Service registered"
echo ""

# =============================================================================
# 3. Chat Service 등록
# =============================================================================
echo "📦 Registering Chat Service..."

# Service 등록
curl -s -X POST "${KONG_ADMIN_URL}/services" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "chat-service",
    "url": "http://chat-service:8002"
  }' | jq .

# Routes 등록 - /api/chat-rooms/*
curl -s -X POST "${KONG_ADMIN_URL}/services/chat-service/routes" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "chat-rooms-route",
    "paths": ["/api/chat-rooms"],
    "strip_path": true,
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  }' | jq .

# Routes 등록 - /api/messages/*
curl -s -X POST "${KONG_ADMIN_URL}/services/chat-service/routes" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "messages-route",
    "paths": ["/api/messages"],
    "strip_path": true,
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  }' | jq .

echo "✅ Chat Service registered"
echo ""

# =============================================================================
# 4. Global Plugins 설정
# =============================================================================
echo "🔧 Configuring global plugins..."

# CORS Plugin
curl -s -X POST "${KONG_ADMIN_URL}/plugins" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "cors",
    "config": {
      "origins": ["http://localhost:3000", "http://localhost:5173"],
      "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
      "headers": ["Accept", "Authorization", "Content-Type", "X-Requested-With"],
      "exposed_headers": ["X-Auth-Token"],
      "credentials": true,
      "max_age": 3600
    }
  }' | jq .

# Rate Limiting Plugin (전역)
curl -s -X POST "${KONG_ADMIN_URL}/plugins" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "rate-limiting",
    "config": {
      "minute": 100,
      "hour": 1000,
      "policy": "local"
    }
  }' | jq .

# Request/Response Logging
curl -s -X POST "${KONG_ADMIN_URL}/plugins" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "file-log",
    "config": {
      "path": "/tmp/kong-access.log",
      "reopen": true
    }
  }' | jq .

echo "✅ Global plugins configured"
echo ""

# =============================================================================
# 5. 설정 확인
# =============================================================================
echo "📋 Verifying configuration..."
echo ""

echo "Services:"
curl -s "${KONG_ADMIN_URL}/services" | jq '.data[] | {name, host, port}'
echo ""

echo "Routes:"
curl -s "${KONG_ADMIN_URL}/routes" | jq '.data[] | {name, paths, service: .service.name}'
echo ""

echo "Plugins:"
curl -s "${KONG_ADMIN_URL}/plugins" | jq '.data[] | {name, enabled}'
echo ""

# =============================================================================
# 완료
# =============================================================================
echo "🎉 Kong API Gateway configuration completed!"
echo ""
echo "API Gateway URLs:"
echo "  - Proxy:     http://localhost:80"
echo "  - Admin API: http://localhost:8001"
echo "  - Konga UI:  http://localhost:1337"
echo ""
echo "Service Routes:"
echo "  - User:   http://localhost/api/auth/*, /api/profile/*, /api/users/*"
echo "  - Friend: http://localhost/api/friends/*"
echo "  - Chat:   http://localhost/api/chat-rooms/*, /api/messages/*"

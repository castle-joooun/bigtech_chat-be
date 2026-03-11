/**
 * k6 Soak Test: Long Duration Stability
 *
 * 테스트 시나리오:
 * - 장시간 동안 일정 부하 유지
 * - 메모리 누수, 리소스 고갈 확인
 * - 시스템 안정성 검증
 *
 * 실행 방법:
 *   k6 run tests/load/05-soak-test.js
 *   k6 run --duration 1h tests/load/05-soak-test.js  # 1시간 테스트
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';
import { randomString } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// =============================================================================
// Configuration
// =============================================================================

const USER_SERVICE_URL = __ENV.USER_SERVICE_URL || 'http://localhost:8005';
const CHAT_SERVICE_URL = __ENV.CHAT_SERVICE_URL || 'http://localhost:8002';

// Soak test duration can be overridden with --duration flag
const SOAK_DURATION = __ENV.SOAK_DURATION || '30m';  // 기본 30분

export const options = {
    scenarios: {
        soak_test: {
            executor: 'constant-vus',
            vus: 100,  // 안정적인 부하 수준
            duration: SOAK_DURATION,
        },
    },
    thresholds: {
        http_req_duration: ['p(95)<2000', 'p(99)<5000'],
        http_req_failed: ['rate<0.02'],  // 2% 미만 에러율
        'soak_error_rate': ['rate<0.02'],
    },
};

// =============================================================================
// Custom Metrics
// =============================================================================

const requestDuration = new Trend('soak_request_duration');
const errorRate = new Rate('soak_error_rate');
const totalRequests = new Counter('soak_total_requests');
const totalErrors = new Counter('soak_total_errors');

// Time-based metrics (to detect degradation over time)
const durationByMinute = {};

// =============================================================================
// Helper Functions
// =============================================================================

function generateUser() {
    const id = randomString(10);
    return {
        email: `soak_${id}@test.com`,
        username: `soakuser_${id}`,
        password: 'Test123!@#',
        display_name: `Soak Test ${id}`,
    };
}

function getCurrentMinute() {
    return Math.floor(Date.now() / 60000);
}

function recordMetric(duration, success) {
    const minute = getCurrentMinute();
    if (!durationByMinute[minute]) {
        durationByMinute[minute] = { total: 0, count: 0, errors: 0 };
    }
    durationByMinute[minute].total += duration;
    durationByMinute[minute].count += 1;
    if (!success) {
        durationByMinute[minute].errors += 1;
    }

    requestDuration.add(duration);
    totalRequests.add(1);
    if (!success) {
        totalErrors.add(1);
        errorRate.add(0);
    } else {
        errorRate.add(1);
    }
}

// =============================================================================
// API Functions
// =============================================================================

function performUserFlow() {
    const user = generateUser();
    let success = true;
    let totalDuration = 0;

    // Step 1: Register
    const regStart = Date.now();
    const regResponse = http.post(
        `${USER_SERVICE_URL}/auth/register`,
        JSON.stringify(user),
        {
            headers: { 'Content-Type': 'application/json' },
            tags: { name: 'soak_register' },
            timeout: '30s',
        }
    );
    totalDuration += Date.now() - regStart;

    if (regResponse.status !== 200 && regResponse.status !== 201) {
        recordMetric(totalDuration, false);
        return false;
    }

    sleep(0.2);

    // Step 2: Login
    const loginStart = Date.now();
    const loginResponse = http.post(
        `${USER_SERVICE_URL}/auth/login/json`,
        JSON.stringify({ email: user.email, password: user.password }),
        {
            headers: { 'Content-Type': 'application/json' },
            tags: { name: 'soak_login' },
            timeout: '30s',
        }
    );
    totalDuration += Date.now() - loginStart;

    let token = null;
    try {
        const body = JSON.parse(loginResponse.body);
        token = body.access_token;
    } catch (e) {
        recordMetric(totalDuration, false);
        return false;
    }

    if (!token) {
        recordMetric(totalDuration, false);
        return false;
    }

    sleep(0.2);

    // Step 3: Profile operations
    const profileStart = Date.now();
    const profileResponse = http.get(
        `${USER_SERVICE_URL}/profile/me`,
        {
            headers: { 'Authorization': `Bearer ${token}` },
            tags: { name: 'soak_profile' },
            timeout: '30s',
        }
    );
    totalDuration += Date.now() - profileStart;

    if (profileResponse.status !== 200) {
        success = false;
    }

    sleep(0.2);

    // Step 4: Search users
    const searchStart = Date.now();
    const searchResponse = http.get(
        `${USER_SERVICE_URL}/users/search?query=test&limit=10`,
        {
            headers: { 'Authorization': `Bearer ${token}` },
            tags: { name: 'soak_search' },
            timeout: '30s',
        }
    );
    totalDuration += Date.now() - searchStart;

    if (searchResponse.status !== 200) {
        success = false;
    }

    sleep(0.2);

    // Step 5: Get chat rooms (may be empty, but tests the endpoint)
    const chatStart = Date.now();
    const chatResponse = http.get(
        `${CHAT_SERVICE_URL}/chat-rooms?limit=10`,
        {
            headers: { 'Authorization': `Bearer ${token}` },
            tags: { name: 'soak_chatrooms' },
            timeout: '30s',
        }
    );
    totalDuration += Date.now() - chatStart;

    if (chatResponse.status !== 200) {
        success = false;
    }

    recordMetric(totalDuration, success);
    return success;
}

// =============================================================================
// Main Test Function
// =============================================================================

export default function () {
    group('Soak Test - User Flow', () => {
        performUserFlow();
    });

    // Consistent think time for soak test
    sleep(1 + Math.random());  // 1-2 seconds
}

// =============================================================================
// Setup & Teardown
// =============================================================================

export function setup() {
    console.log('='.repeat(70));
    console.log('SOAK TEST - Long Duration Stability Check');
    console.log('='.repeat(70));
    console.log('');
    console.log('Configuration:');
    console.log(`  Duration: ${SOAK_DURATION}`);
    console.log(`  VUs: 100 (constant)`);
    console.log(`  User Service: ${USER_SERVICE_URL}`);
    console.log(`  Chat Service: ${CHAT_SERVICE_URL}`);
    console.log('');
    console.log('Monitoring for:');
    console.log('  - Memory leaks');
    console.log('  - Response time degradation');
    console.log('  - Error rate increase over time');
    console.log('  - Resource exhaustion');
    console.log('='.repeat(70));

    // Health check
    const healthResponse = http.get(`${USER_SERVICE_URL}/health`);
    check(healthResponse, {
        'service is healthy': (r) => r.status === 200,
    });

    return {
        startTime: Date.now(),
        startMinute: getCurrentMinute(),
    };
}

export function teardown(data) {
    const durationMinutes = (Date.now() - data.startTime) / 60000;

    console.log('='.repeat(70));
    console.log(`Soak test completed: ${durationMinutes.toFixed(2)} minutes`);
    console.log('');
    console.log('Time-based Analysis:');
    console.log('(Check Grafana/Prometheus for detailed metrics)');
    console.log('');
    console.log('Key Questions:');
    console.log('  1. Did response times increase over time?');
    console.log('  2. Did error rates change?');
    console.log('  3. Was memory usage stable?');
    console.log('  4. Were there any connection pool exhaustion issues?');
    console.log('='.repeat(70));
}

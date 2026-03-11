/**
 * k6 Stress Test: Find Breaking Point
 *
 * 테스트 시나리오:
 * - 시스템의 한계점 파악
 * - 점진적으로 부하 증가
 * - 에러 발생 지점 확인
 *
 * 실행 방법:
 *   k6 run tests/load/04-stress-test.js
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
const FRIEND_SERVICE_URL = __ENV.FRIEND_SERVICE_URL || 'http://localhost:8003';

export const options = {
    scenarios: {
        stress_test: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                // 점진적 부하 증가
                { duration: '2m', target: 100 },   // Stage 1: 100 VUs
                { duration: '3m', target: 100 },   // Hold
                { duration: '2m', target: 300 },   // Stage 2: 300 VUs
                { duration: '3m', target: 300 },   // Hold
                { duration: '2m', target: 500 },   // Stage 3: 500 VUs
                { duration: '3m', target: 500 },   // Hold
                { duration: '2m', target: 700 },   // Stage 4: 700 VUs (stress)
                { duration: '3m', target: 700 },   // Hold
                { duration: '2m', target: 1000 },  // Stage 5: 1000 VUs (breaking point?)
                { duration: '3m', target: 1000 },  // Hold
                { duration: '5m', target: 0 },     // Recovery
            ],
            gracefulRampDown: '30s',
        },
    },
    thresholds: {
        // Stress test - 임계값은 참고용
        http_req_duration: ['p(90)<10000'],  // P90 < 10s
        http_req_failed: ['rate<0.30'],      // 30% 에러율까지 기록 (breaking point 확인용)
    },
};

// =============================================================================
// Custom Metrics
// =============================================================================

const requestDuration = new Trend('stress_request_duration');
const errorCount = new Counter('stress_errors');
const successRate = new Rate('stress_success_rate');
const stageMetrics = {
    stage1: new Counter('stage1_requests'),
    stage2: new Counter('stage2_requests'),
    stage3: new Counter('stage3_requests'),
    stage4: new Counter('stage4_requests'),
    stage5: new Counter('stage5_requests'),
};

// =============================================================================
// Helper Functions
// =============================================================================

function generateUser() {
    const id = randomString(10);
    return {
        email: `stress_${id}@test.com`,
        username: `stressuser_${id}`,
        password: 'Test123!@#',
        display_name: `Stress Test ${id}`,
    };
}

function getStage(vu) {
    if (vu <= 100) return 1;
    if (vu <= 300) return 2;
    if (vu <= 500) return 3;
    if (vu <= 700) return 4;
    return 5;
}

// =============================================================================
// API Functions
// =============================================================================

function registerAndLogin(user) {
    // Register
    const regUrl = `${USER_SERVICE_URL}/auth/register`;
    const regPayload = JSON.stringify(user);
    const regParams = {
        headers: { 'Content-Type': 'application/json' },
        tags: { name: 'stress_register' },
        timeout: '60s',
    };

    const startTime = Date.now();
    const regResponse = http.post(regUrl, regPayload, regParams);

    if (regResponse.status !== 200 && regResponse.status !== 201) {
        errorCount.add(1);
        successRate.add(0);
        requestDuration.add(Date.now() - startTime);
        return null;
    }

    // Login
    const loginUrl = `${USER_SERVICE_URL}/auth/login/json`;
    const loginPayload = JSON.stringify({
        email: user.email,
        password: user.password,
    });
    const loginParams = {
        headers: { 'Content-Type': 'application/json' },
        tags: { name: 'stress_login' },
        timeout: '60s',
    };

    const loginResponse = http.post(loginUrl, loginPayload, loginParams);
    const duration = Date.now() - startTime;
    requestDuration.add(duration);

    let token = null;
    const success = check(loginResponse, {
        'login successful': (r) => {
            if (r.status === 200) {
                try {
                    const body = JSON.parse(r.body);
                    token = body.access_token;
                    return true;
                } catch (e) {
                    return false;
                }
            }
            return false;
        },
    });

    if (!success) {
        errorCount.add(1);
    }
    successRate.add(success ? 1 : 0);

    return token;
}

function performMixedOperations(token, userId) {
    const operations = [
        () => {
            // Get profile
            const url = `${USER_SERVICE_URL}/profile/me`;
            return http.get(url, {
                headers: { 'Authorization': `Bearer ${token}` },
                tags: { name: 'stress_profile' },
                timeout: '30s',
            });
        },
        () => {
            // Search users
            const url = `${USER_SERVICE_URL}/users/search?query=test&limit=10`;
            return http.get(url, {
                headers: { 'Authorization': `Bearer ${token}` },
                tags: { name: 'stress_search' },
                timeout: '30s',
            });
        },
        () => {
            // Get chat rooms (may be empty)
            const url = `${CHAT_SERVICE_URL}/chat-rooms?limit=10`;
            return http.get(url, {
                headers: { 'Authorization': `Bearer ${token}` },
                tags: { name: 'stress_chatrooms' },
                timeout: '30s',
            });
        },
    ];

    // Randomly select and execute operations
    const numOps = Math.floor(Math.random() * 3) + 1;
    for (let i = 0; i < numOps; i++) {
        const op = operations[Math.floor(Math.random() * operations.length)];
        const startTime = Date.now();
        const response = op();
        const duration = Date.now() - startTime;

        requestDuration.add(duration);

        const success = response.status === 200;
        if (!success) {
            errorCount.add(1);
        }
        successRate.add(success ? 1 : 0);

        sleep(0.1);
    }
}

// =============================================================================
// Main Test Function
// =============================================================================

export default function () {
    const user = generateUser();
    const currentVUs = __VU;
    const stage = getStage(currentVUs);

    // Track stage metrics
    switch (stage) {
        case 1: stageMetrics.stage1.add(1); break;
        case 2: stageMetrics.stage2.add(1); break;
        case 3: stageMetrics.stage3.add(1); break;
        case 4: stageMetrics.stage4.add(1); break;
        case 5: stageMetrics.stage5.add(1); break;
    }

    group(`Stress Stage ${stage}`, () => {
        const token = registerAndLogin(user);

        if (token) {
            sleep(0.2);
            performMixedOperations(token, null);
        }
    });

    // Variable sleep based on stage (simulate different user patterns)
    const sleepTime = Math.max(0.5, 2 - (stage * 0.3));
    sleep(sleepTime);
}

// =============================================================================
// Setup & Teardown
// =============================================================================

export function setup() {
    console.log('='.repeat(70));
    console.log('STRESS TEST - Finding System Breaking Point');
    console.log('='.repeat(70));
    console.log('');
    console.log('Test Configuration:');
    console.log(`  User Service:   ${USER_SERVICE_URL}`);
    console.log(`  Chat Service:   ${CHAT_SERVICE_URL}`);
    console.log(`  Friend Service: ${FRIEND_SERVICE_URL}`);
    console.log('');
    console.log('Load Stages:');
    console.log('  Stage 1: 100 VUs  (5 min)  - Baseline');
    console.log('  Stage 2: 300 VUs  (5 min)  - Moderate');
    console.log('  Stage 3: 500 VUs  (5 min)  - High');
    console.log('  Stage 4: 700 VUs  (5 min)  - Stress');
    console.log('  Stage 5: 1000 VUs (5 min)  - Breaking Point?');
    console.log('  Recovery: 5 min');
    console.log('');
    console.log('Total Duration: ~30 minutes');
    console.log('='.repeat(70));

    // Verify services are up
    const services = [
        { name: 'User Service', url: `${USER_SERVICE_URL}/health` },
        { name: 'Chat Service', url: `${CHAT_SERVICE_URL}/health` },
        { name: 'Friend Service', url: `${FRIEND_SERVICE_URL}/health` },
    ];

    for (const service of services) {
        const response = http.get(service.url);
        if (response.status !== 200) {
            console.error(`${service.name} not healthy: ${response.status}`);
        } else {
            console.log(`${service.name}: OK`);
        }
    }

    return { startTime: Date.now() };
}

export function teardown(data) {
    const duration = (Date.now() - data.startTime) / 1000 / 60;
    console.log('='.repeat(70));
    console.log(`Stress test completed in ${duration.toFixed(2)} minutes`);
    console.log('');
    console.log('Review the metrics to identify:');
    console.log('  - At which VU count did errors start increasing?');
    console.log('  - What was the response time at each stage?');
    console.log('  - Did the system recover after high load?');
    console.log('='.repeat(70));
}

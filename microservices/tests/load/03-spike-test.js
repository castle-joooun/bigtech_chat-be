/**
 * k6 Spike Test: Sudden Traffic Surge
 *
 * 테스트 시나리오:
 * - 갑작스러운 트래픽 급증 시뮬레이션
 * - 시스템 복구 능력 테스트
 *
 * 실행 방법:
 *   k6 run tests/load/03-spike-test.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';
import { randomString } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// =============================================================================
// Configuration
// =============================================================================

const USER_SERVICE_URL = __ENV.USER_SERVICE_URL || 'http://localhost:8005';
const FRIEND_SERVICE_URL = __ENV.FRIEND_SERVICE_URL || 'http://localhost:8003';

export const options = {
    scenarios: {
        spike_test: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '10s', target: 10 },    // Warm up
                { duration: '20s', target: 10 },    // Normal load
                { duration: '10s', target: 500 },   // SPIKE! 급격한 증가
                { duration: '1m', target: 500 },    // Sustained spike
                { duration: '10s', target: 10 },    // Recovery
                { duration: '30s', target: 10 },    // Normal load (recovery check)
                { duration: '10s', target: 0 },     // Ramp down
            ],
            gracefulRampDown: '10s',
        },
    },
    thresholds: {
        // Spike 상황에서는 임계값 완화
        http_req_duration: ['p(95)<5000', 'p(99)<10000'],
        http_req_failed: ['rate<0.10'],  // 10% 에러율까지 허용 (spike 상황)
        'spike_registration_errors': ['count<100'],
        'spike_friend_request_errors': ['count<100'],
    },
};

// =============================================================================
// Custom Metrics
// =============================================================================

const registrationDuration = new Trend('spike_registration_duration');
const friendRequestDuration = new Trend('spike_friend_request_duration');
const registrationErrors = new Counter('spike_registration_errors');
const friendRequestErrors = new Counter('spike_friend_request_errors');
const successRate = new Rate('spike_success_rate');

// =============================================================================
// Test Data
// =============================================================================

function generateUser() {
    const id = randomString(8);
    return {
        email: `spike_${id}@test.com`,
        username: `spikeuser_${id}`,
        password: 'Test123!@#',
        display_name: `Spike Test User ${id}`,
    };
}

// =============================================================================
// API Functions
// =============================================================================

function registerUser(user) {
    const url = `${USER_SERVICE_URL}/auth/register`;
    const payload = JSON.stringify(user);
    const params = {
        headers: { 'Content-Type': 'application/json' },
        tags: { name: 'spike_register' },
        timeout: '30s',  // Longer timeout for spike
    };

    const startTime = Date.now();
    const response = http.post(url, payload, params);
    const duration = Date.now() - startTime;

    registrationDuration.add(duration);

    let userId = null;
    const success = check(response, {
        'registration successful': (r) => {
            if (r.status === 200 || r.status === 201) {
                try {
                    const body = JSON.parse(r.body);
                    userId = body.id || body.user_id;
                    return true;
                } catch (e) {
                    return false;
                }
            }
            return false;
        },
    });

    if (!success) {
        registrationErrors.add(1);
    }
    successRate.add(success ? 1 : 0);

    return { userId, token: null, success };
}

function loginUser(email, password) {
    const url = `${USER_SERVICE_URL}/auth/login/json`;
    const payload = JSON.stringify({ email, password });
    const params = {
        headers: { 'Content-Type': 'application/json' },
        tags: { name: 'spike_login' },
        timeout: '30s',
    };

    const response = http.post(url, payload, params);
    let token = null;

    check(response, {
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

    return token;
}

function sendFriendRequest(token, targetUserId) {
    const url = `${FRIEND_SERVICE_URL}/friends/request`;
    const payload = JSON.stringify({
        target_user_id: targetUserId,
    });
    const params = {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
        },
        tags: { name: 'spike_friend_request' },
        timeout: '30s',
    };

    const startTime = Date.now();
    const response = http.post(url, payload, params);
    const duration = Date.now() - startTime;

    friendRequestDuration.add(duration);

    const success = check(response, {
        'friend request sent': (r) => r.status === 200 || r.status === 201,
    });

    if (!success) {
        friendRequestErrors.add(1);
    }
    successRate.add(success ? 1 : 0);

    return success;
}

function searchUsers(token, query) {
    const url = `${FRIEND_SERVICE_URL}/friends/search?query=${query}&limit=10`;
    const params = {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
        },
        tags: { name: 'spike_search' },
        timeout: '30s',
    };

    const response = http.get(url, params);

    check(response, {
        'search successful': (r) => r.status === 200,
    });

    return response;
}

// =============================================================================
// Main Test Function
// =============================================================================

export default function () {
    const user = generateUser();

    group('Spike - User Registration', () => {
        const { userId, success } = registerUser(user);

        if (!success) {
            sleep(0.5);
            return;
        }
    });

    sleep(0.2);

    group('Spike - User Login', () => {
        const token = loginUser(user.email, user.password);

        if (!token) {
            sleep(0.5);
            return;
        }

        sleep(0.1);

        // Random search to simulate user behavior
        group('Spike - User Search', () => {
            searchUsers(token, 'test');
        });
    });

    sleep(0.3);
}

// =============================================================================
// Setup & Teardown
// =============================================================================

export function setup() {
    console.log('='.repeat(60));
    console.log('SPIKE TEST - Sudden Traffic Surge Simulation');
    console.log('='.repeat(60));
    console.log(`User Service: ${USER_SERVICE_URL}`);
    console.log(`Friend Service: ${FRIEND_SERVICE_URL}`);
    console.log('');
    console.log('Test Stages:');
    console.log('  1. Warm up (10s): 0 → 10 VUs');
    console.log('  2. Normal (20s): 10 VUs');
    console.log('  3. SPIKE (10s): 10 → 500 VUs ⚡');
    console.log('  4. Sustained (1m): 500 VUs');
    console.log('  5. Recovery (10s): 500 → 10 VUs');
    console.log('  6. Post-recovery (30s): 10 VUs');
    console.log('='.repeat(60));

    // Health checks
    const userHealth = http.get(`${USER_SERVICE_URL}/health`);
    if (userHealth.status !== 200) {
        console.error(`User Service not healthy: ${userHealth.status}`);
    }

    return { startTime: Date.now() };
}

export function teardown(data) {
    const duration = (Date.now() - data.startTime) / 1000;
    console.log('='.repeat(60));
    console.log(`Spike test completed in ${duration.toFixed(2)} seconds`);
    console.log('='.repeat(60));
}

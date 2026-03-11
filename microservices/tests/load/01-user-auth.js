/**
 * k6 Load Test: User Authentication
 *
 * 테스트 시나리오:
 * 1. 회원가입
 * 2. 로그인
 * 3. 프로필 조회
 *
 * 실행 방법:
 *   k6 run tests/load/01-user-auth.js
 *   k6 run --vus 100 --duration 2m tests/load/01-user-auth.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';
import { randomString } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// =============================================================================
// Configuration
// =============================================================================

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8005';

export const options = {
    scenarios: {
        // Scenario 1: Ramp-up 부하 테스트
        ramp_up: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '30s', target: 50 },   // 30초간 50 VU까지 증가
                { duration: '1m', target: 100 },   // 1분간 100 VU 유지
                { duration: '30s', target: 200 },  // 30초간 200 VU까지 증가
                { duration: '1m', target: 200 },   // 1분간 200 VU 유지
                { duration: '30s', target: 0 },    // 30초간 0으로 감소
            ],
            gracefulRampDown: '10s',
        },
    },
    thresholds: {
        http_req_duration: ['p(95)<2000', 'p(99)<5000'],  // P95 < 2s, P99 < 5s
        http_req_failed: ['rate<0.05'],                   // 에러율 5% 미만
        'registration_duration': ['p(95)<3000'],
        'login_duration': ['p(95)<1000'],
        'profile_duration': ['p(95)<500'],
    },
};

// =============================================================================
// Custom Metrics
// =============================================================================

const registrationDuration = new Trend('registration_duration');
const loginDuration = new Trend('login_duration');
const profileDuration = new Trend('profile_duration');
const registrationErrors = new Counter('registration_errors');
const loginErrors = new Counter('login_errors');
const successfulLogins = new Rate('successful_logins');

// =============================================================================
// Test Data
// =============================================================================

function generateUser() {
    const id = randomString(8);
    return {
        email: `loadtest_${id}@test.com`,
        username: `loaduser_${id}`,
        password: 'Test123!@#',
        display_name: `Load Test User ${id}`,
    };
}

// =============================================================================
// API Functions
// =============================================================================

function register(user) {
    const url = `${BASE_URL}/auth/register`;
    const payload = JSON.stringify(user);
    const params = {
        headers: { 'Content-Type': 'application/json' },
        tags: { name: 'register' },
    };

    const startTime = Date.now();
    const response = http.post(url, payload, params);
    const duration = Date.now() - startTime;

    registrationDuration.add(duration);

    const success = check(response, {
        'registration status is 200 or 201': (r) => r.status === 200 || r.status === 201,
        'registration has user data': (r) => {
            try {
                const body = JSON.parse(r.body);
                return body.id !== undefined || body.user_id !== undefined;
            } catch (e) {
                return false;
            }
        },
    });

    if (!success) {
        registrationErrors.add(1);
        console.log(`Registration failed: ${response.status} - ${response.body}`);
    }

    return { response, success };
}

function login(email, password) {
    const url = `${BASE_URL}/auth/login/json`;
    const payload = JSON.stringify({ email, password });
    const params = {
        headers: { 'Content-Type': 'application/json' },
        tags: { name: 'login' },
    };

    const startTime = Date.now();
    const response = http.post(url, payload, params);
    const duration = Date.now() - startTime;

    loginDuration.add(duration);

    let token = null;
    const success = check(response, {
        'login status is 200': (r) => r.status === 200,
        'login has access token': (r) => {
            try {
                const body = JSON.parse(r.body);
                token = body.access_token;
                return token !== undefined;
            } catch (e) {
                return false;
            }
        },
    });

    successfulLogins.add(success ? 1 : 0);
    if (!success) {
        loginErrors.add(1);
        console.log(`Login failed: ${response.status} - ${response.body}`);
    }

    return { response, token, success };
}

function getProfile(token) {
    const url = `${BASE_URL}/profile/me`;
    const params = {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
        },
        tags: { name: 'profile' },
    };

    const startTime = Date.now();
    const response = http.get(url, params);
    const duration = Date.now() - startTime;

    profileDuration.add(duration);

    const success = check(response, {
        'profile status is 200': (r) => r.status === 200,
        'profile has user data': (r) => {
            try {
                const body = JSON.parse(r.body);
                return body.email !== undefined;
            } catch (e) {
                return false;
            }
        },
    });

    return { response, success };
}

// =============================================================================
// Main Test Function
// =============================================================================

export default function () {
    const user = generateUser();

    group('User Registration', () => {
        const { success } = register(user);
        if (!success) {
            return; // Skip rest of test if registration fails
        }
    });

    sleep(0.5); // Small delay between requests

    group('User Login', () => {
        const { token, success } = login(user.email, user.password);
        if (!success || !token) {
            return;
        }

        sleep(0.3);

        group('Profile Operations', () => {
            // Get profile
            getProfile(token);

            sleep(0.2);

            // Get profile again (simulate user activity)
            getProfile(token);
        });
    });

    sleep(1); // Think time between iterations
}

// =============================================================================
// Setup & Teardown
// =============================================================================

export function setup() {
    console.log(`Starting load test against ${BASE_URL}`);

    // Health check
    const healthRes = http.get(`${BASE_URL}/health`);
    if (healthRes.status !== 200) {
        console.error(`Health check failed: ${healthRes.status}`);
    }

    return { startTime: Date.now() };
}

export function teardown(data) {
    const duration = (Date.now() - data.startTime) / 1000;
    console.log(`Load test completed in ${duration.toFixed(2)} seconds`);
}

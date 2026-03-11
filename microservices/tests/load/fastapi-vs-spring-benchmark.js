/**
 * k6 Benchmark: FastAPI vs Spring Boot MSA (Full Scenario)
 *
 * 동일 시나리오로 FastAPI / Spring Boot MSA 성능 비교
 *
 * 테스트 시나리오 (실제 사용자 플로우):
 *   1. 회원가입 (User A, User B)
 *   2. 로그인 (User A, User B)
 *   3. 프로필 조회
 *   4. 사용자 검색
 *   5. 친구 요청 (A → B)
 *   6. 친구 승인 (B → accept)
 *   7. 채팅방 개설 (A → B)
 *   8. 메시지 발송 (A → B, 5회)
 *   9. 메시지 조회
 *
 * 실행 방법:
 *   # FastAPI MSA
 *   k6 run -e TARGET=fastapi /path/to/fastapi-vs-spring-benchmark.js
 *
 *   # Spring Boot MSA
 *   k6 run -e TARGET=spring /path/to/fastapi-vs-spring-benchmark.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';
import { randomString } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// =============================================================================
// Configuration - FastAPI vs Spring Boot
// =============================================================================

const TARGET = __ENV.TARGET || 'fastapi';
const MAX_VUS = parseInt(__ENV.MAX_VUS) || 50;
const DURATION = __ENV.DURATION || '1m';

const CONFIG = {
    fastapi: {
        name: 'FastAPI MSA',
        userServiceUrl: __ENV.USER_URL || 'http://[::1]:8005',
        friendServiceUrl: __ENV.FRIEND_URL || 'http://[::1]:8003',
        chatServiceUrl: __ENV.CHAT_URL || 'http://[::1]:8002',
        endpoints: {
            register: '/api/auth/register',
            login: '/api/auth/login/json',
            profile: '/api/profile/me',
            search: '/api/users/search',
            health: '/health',
            friendRequest: '/api/friends/request',
            friendAccept: '/api/friends/status',    // + /{userId}
            chatRoomCheck: '/api/chat-rooms/check',  // + /{userId}
            sendMessage: '/api/messages',             // + /{roomId}
            getMessages: '/api/messages',             // + /{roomId}
        },
        registerPayload: (user) => ({
            email: user.email,
            username: user.username,
            password: user.password,
            display_name: user.displayName,
        }),
        friendRequestPayload: (targetUserId) => ({
            user_id_2: targetUserId,
        }),
        friendAcceptPayload: () => ({
            action: 'accept',
        }),
        messagePayload: (content) => ({
            content: content,
            message_type: 'text',
        }),
        parseRegister: (body) => body.id || body.user_id,
        getToken: (body) => body.access_token,
        parseProfile: (body) => body.email !== undefined,
        parseChatRoom: (body) => body.id,
    },
    spring: {
        name: 'Spring Boot MSA',
        userServiceUrl: __ENV.USER_URL || 'http://[::1]:8081',
        friendServiceUrl: __ENV.FRIEND_URL || 'http://[::1]:8003',
        chatServiceUrl: __ENV.CHAT_URL || 'http://[::1]:8002',
        endpoints: {
            register: '/api/auth/register',
            login: '/api/auth/login/json',
            profile: '/api/profile/me',
            search: '/api/users/search',
            health: '/health',
            friendRequest: '/api/friends/request',
            friendAccept: '/api/friends/status',
            chatRoomCheck: '/api/chat-rooms/check',
            sendMessage: '/api/messages',
            getMessages: '/api/messages',
        },
        registerPayload: (user) => ({
            email: user.email,
            username: user.username,
            password: user.password,
            displayName: user.displayName,
        }),
        friendRequestPayload: (targetUserId) => ({
            userId2: targetUserId,
        }),
        friendAcceptPayload: () => ({
            action: 'accept',
        }),
        messagePayload: (content) => ({
            content: content,
            messageType: 'text',
        }),
        parseRegister: (body) => body.id,
        getToken: (body) => body.accessToken || body.access_token,
        parseProfile: (body) => body.username !== undefined,
        parseChatRoom: (body) => body.id,
    },
};

const cfg = CONFIG[TARGET];
if (!cfg) {
    throw new Error(`Unknown TARGET: ${TARGET}. Use 'fastapi' or 'spring'`);
}

// =============================================================================
// Test Options
// =============================================================================

export const options = {
    scenarios: {
        benchmark: {
            executor: 'ramping-vus',
            startVUs: 1,
            stages: [
                { duration: '10s', target: MAX_VUS },
                { duration: DURATION, target: MAX_VUS },
                { duration: '10s', target: 0 },
            ],
            gracefulRampDown: '5s',
        },
    },
    thresholds: {
        http_req_duration: ['p(95)<5000', 'p(99)<10000'],
        http_req_failed: ['rate<0.15'],
        'register_duration': ['p(95)<5000'],
        'login_duration': ['p(95)<3000'],
        'profile_duration': ['p(95)<500'],
        'search_duration': ['p(95)<1000'],
        'friend_request_duration': ['p(95)<2000'],
        'friend_accept_duration': ['p(95)<2000'],
        'chatroom_duration': ['p(95)<2000'],
        'send_message_duration': ['p(95)<1000'],
        'get_messages_duration': ['p(95)<1000'],
    },
};

// =============================================================================
// Custom Metrics
// =============================================================================

const registerDuration = new Trend('register_duration');
const loginDuration = new Trend('login_duration');
const profileDuration = new Trend('profile_duration');
const searchDuration = new Trend('search_duration');
const friendRequestDuration = new Trend('friend_request_duration');
const friendAcceptDuration = new Trend('friend_accept_duration');
const chatroomDuration = new Trend('chatroom_duration');
const sendMessageDuration = new Trend('send_message_duration');
const getMessagesDuration = new Trend('get_messages_duration');

const totalRequests = new Counter('total_requests');
const errorCount = new Counter('error_count');
const successRate = new Rate('success_rate');

// =============================================================================
// Helper
// =============================================================================

function generateUser(prefix) {
    const id = randomString(8);
    return {
        email: `${prefix}_${id}@test.com`,
        username: `${prefix}_${id}`,
        password: 'Test1234#',
        displayName: `${prefix} User ${id}`,
    };
}

function authHeaders(token) {
    return {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
    };
}

function apiCall(method, url, payload, token, metricTrend, tagName) {
    const params = {
        headers: token ? authHeaders(token) : { 'Content-Type': 'application/json' },
        tags: { name: tagName, target: TARGET },
        redirects: 0,
    };

    let res;
    if (method === 'GET') {
        res = http.get(url, params);
    } else if (method === 'POST') {
        res = http.post(url, payload ? JSON.stringify(payload) : null, params);
    } else if (method === 'PUT') {
        res = http.put(url, payload ? JSON.stringify(payload) : null, params);
    }

    metricTrend.add(res.timings.duration);
    totalRequests.add(1);

    const success = res.status >= 200 && res.status < 300;
    if (!success) {
        errorCount.add(1);
        console.log(`[ERROR] ${tagName} failed: status=${res.status} url=${url} body=${res.body}`);
    }
    successRate.add(success ? 1 : 0);

    check(res, {
        [`${tagName}: status 2xx`]: (r) => r.status >= 200 && r.status < 300,
    });

    return res;
}

// =============================================================================
// API Functions
// =============================================================================

function registerUser(user) {
    const url = `${cfg.userServiceUrl}${cfg.endpoints.register}`;
    const payload = cfg.registerPayload(user);
    const params = {
        headers: { 'Content-Type': 'application/json' },
        tags: { name: 'register', target: TARGET },
        redirects: 0,
    };

    const res = http.post(url, JSON.stringify(payload), params);
    registerDuration.add(res.timings.duration);
    totalRequests.add(1);

    let userId = null;
    const ok = res.status >= 200 && res.status < 300;

    if (ok) {
        try {
            userId = cfg.parseRegister(JSON.parse(res.body));
        } catch (e) {}
    } else {
        if (__ITER < 3) {
            console.log(`[DEBUG] register url=${url} status=${res.status} body=${res.body}`);
        }
    }

    check(res, {
        'register: status 2xx': (r) => r.status >= 200 && r.status < 300,
    });

    if (!ok) errorCount.add(1);
    successRate.add(ok ? 1 : 0);

    return userId;
}

function loginUser(email, password) {
    const url = `${cfg.userServiceUrl}${cfg.endpoints.login}`;
    const res = apiCall('POST', url, { email, password }, null, loginDuration, 'login');

    let token = null;
    try {
        if (res.status === 200) {
            token = cfg.getToken(JSON.parse(res.body));
        }
    } catch (e) {}

    return token;
}

function getProfile(token) {
    const url = `${cfg.userServiceUrl}${cfg.endpoints.profile}`;
    apiCall('GET', url, null, token, profileDuration, 'profile');
}

function searchUsers(token, query) {
    const url = `${cfg.userServiceUrl}${cfg.endpoints.search}?query=${query}&limit=10`;
    apiCall('GET', url, null, token, searchDuration, 'search');
}

function sendFriendRequest(token, targetUserId) {
    const url = `${cfg.friendServiceUrl}${cfg.endpoints.friendRequest}`;
    const res = apiCall('POST', url, cfg.friendRequestPayload(targetUserId), token, friendRequestDuration, 'friend_request');
    return res.status >= 200 && res.status < 300;
}

function acceptFriendRequest(token, requesterUserId) {
    const url = `${cfg.friendServiceUrl}${cfg.endpoints.friendAccept}/${requesterUserId}`;
    const res = apiCall('PUT', url, cfg.friendAcceptPayload(), token, friendAcceptDuration, 'friend_accept');
    return res.status >= 200 && res.status < 300;
}

function getOrCreateChatRoom(token, targetUserId) {
    const url = `${cfg.chatServiceUrl}${cfg.endpoints.chatRoomCheck}/${targetUserId}`;
    const res = apiCall('GET', url, null, token, chatroomDuration, 'chatroom');

    let roomId = null;
    try {
        if (res.status === 200) {
            roomId = cfg.parseChatRoom(JSON.parse(res.body));
        }
    } catch (e) {}

    return roomId;
}

function sendMessage(token, roomId, content) {
    const url = `${cfg.chatServiceUrl}${cfg.endpoints.sendMessage}/${roomId}`;
    const res = apiCall('POST', url, cfg.messagePayload(content), token, sendMessageDuration, 'send_message');
    return res.status >= 200 && res.status < 300;
}

function getMessages(token, roomId) {
    const url = `${cfg.chatServiceUrl}${cfg.endpoints.getMessages}/${roomId}?limit=50&skip=0`;
    apiCall('GET', url, null, token, getMessagesDuration, 'get_messages');
}

// =============================================================================
// Main Test Function
// =============================================================================

export default function () {
    const userA = generateUser('userA');
    const userB = generateUser('userB');

    // ── 1. 회원가입 (A, B) ──
    let userAId, userBId;
    group('01_Register', () => {
        userAId = registerUser(userA);
        userBId = registerUser(userB);
    });

    if (!userAId || !userBId) {
        sleep(1);
        return;
    }

    sleep(0.3);

    // ── 2. 로그인 (A, B) ──
    let tokenA, tokenB;
    group('02_Login', () => {
        tokenA = loginUser(userA.email, userA.password);
        tokenB = loginUser(userB.email, userB.password);
    });

    if (!tokenA || !tokenB) {
        sleep(1);
        return;
    }

    sleep(0.3);

    // ── 3. 프로필 조회 ──
    group('03_Profile', () => {
        getProfile(tokenA);
    });

    sleep(0.2);

    // ── 4. 사용자 검색 ──
    group('04_Search', () => {
        searchUsers(tokenA, userB.username);
    });

    sleep(0.2);

    // ── 5. 친구 요청 (A → B) ──
    let friendOk = false;
    group('05_Friend_Request', () => {
        friendOk = sendFriendRequest(tokenA, userBId);
    });

    if (!friendOk) {
        sleep(1);
        return;
    }

    sleep(0.3);

    // ── 6. 친구 승인 (B accepts A) ──
    group('06_Friend_Accept', () => {
        acceptFriendRequest(tokenB, userAId);
    });

    sleep(0.3);

    // ── 7. 채팅방 개설 ──
    let roomId = null;
    group('07_ChatRoom_Create', () => {
        roomId = getOrCreateChatRoom(tokenA, userBId);
    });

    if (!roomId) {
        sleep(1);
        return;
    }

    sleep(0.2);

    // ── 8. 메시지 발송 (5회) ──
    group('08_Send_Messages', () => {
        for (let i = 1; i <= 5; i++) {
            sendMessage(tokenA, roomId, `Hello from A! Message #${i}`);
            sleep(0.1);
        }
    });

    sleep(0.2);

    // ── 9. 메시지 조회 ──
    group('09_Get_Messages', () => {
        getMessages(tokenB, roomId);
    });

    sleep(0.5);
}

// =============================================================================
// Setup & Teardown
// =============================================================================

export function setup() {
    console.log('='.repeat(60));
    console.log(`  Benchmark Target : ${cfg.name}`);
    console.log(`  User Service     : ${cfg.userServiceUrl}`);
    console.log(`  Friend Service   : ${cfg.friendServiceUrl}`);
    console.log(`  Chat Service     : ${cfg.chatServiceUrl}`);
    console.log(`  Max VUs          : ${MAX_VUS}`);
    console.log(`  Duration         : ${DURATION}`);
    console.log('='.repeat(60));

    // Health checks
    const services = [
        { name: 'User', url: cfg.userServiceUrl },
        { name: 'Friend', url: cfg.friendServiceUrl },
        { name: 'Chat', url: cfg.chatServiceUrl },
    ];

    for (const svc of services) {
        try {
            const res = http.get(`${svc.url}${cfg.endpoints.health}`);
            if (res.status === 200) {
                console.log(`  ✓ ${svc.name} Service healthy`);
            } else {
                console.warn(`  ⚠ ${svc.name} Service returned ${res.status}`);
            }
        } catch (e) {
            console.error(`  ✗ ${svc.name} Service unreachable`);
        }
    }

    return { startTime: Date.now(), target: TARGET };
}

export function teardown(data) {
    const elapsed = ((Date.now() - data.startTime) / 1000).toFixed(1);
    console.log('='.repeat(60));
    console.log(`  ${cfg.name} Benchmark completed in ${elapsed}s`);
    console.log('='.repeat(60));
}

// =============================================================================
// Custom Summary
// =============================================================================

import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.1/index.js';

export function handleSummary(data) {
    function getMetric(name) {
        const m = data.metrics[name];
        if (!m || !m.values || m.values.avg === undefined) return {};
        const v = m.values;
        return {
            avg: (v.avg || 0).toFixed(2),
            med: (v.med || 0).toFixed(2),
            p90: (v['p(90)'] || 0).toFixed(2),
            p95: (v['p(95)'] || 0).toFixed(2),
            p99: (v['p(99)'] || 0).toFixed(2),
            max: (v.max || 0).toFixed(2),
        };
    }

    const metrics = {
        target: TARGET,
        name: cfg.name,
        timestamp: new Date().toISOString(),
        vus_max: MAX_VUS,
        duration: DURATION,
        total_requests: data.metrics.total_requests ? data.metrics.total_requests.values.count : 0,
        errors: data.metrics.error_count ? data.metrics.error_count.values.count : 0,
        http_req_duration: getMetric('http_req_duration'),
        register: getMetric('register_duration'),
        login: getMetric('login_duration'),
        profile: getMetric('profile_duration'),
        search: getMetric('search_duration'),
        friend_request: getMetric('friend_request_duration'),
        friend_accept: getMetric('friend_accept_duration'),
        chatroom: getMetric('chatroom_duration'),
        send_message: getMetric('send_message_duration'),
        get_messages: getMetric('get_messages_duration'),
    };

    const filename = `benchmark-${TARGET}-${Date.now()}.json`;

    return {
        'stdout': textSummary(data, { indent: ' ', enableColors: true }),
        [filename]: JSON.stringify(metrics, null, 2),
    };
}

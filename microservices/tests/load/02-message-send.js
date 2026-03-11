/**
 * k6 Load Test: Message Sending (Core Business Logic)
 *
 * 테스트 시나리오:
 * 1. 두 사용자 생성 및 로그인
 * 2. 채팅방 생성/조회
 * 3. 메시지 연속 전송 (10개)
 * 4. 메시지 조회
 *
 * 실행 방법:
 *   k6 run tests/load/02-message-send.js
 *   k6 run --vus 50 --duration 5m tests/load/02-message-send.js
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

export const options = {
    scenarios: {
        // Constant load for message throughput testing
        constant_load: {
            executor: 'constant-vus',
            vus: 50,
            duration: '3m',
        },
    },
    thresholds: {
        http_req_duration: ['p(95)<3000', 'p(99)<5000'],
        http_req_failed: ['rate<0.05'],
        'message_send_duration': ['p(95)<1000', 'p(99)<2000'],
        'message_list_duration': ['p(95)<500'],
        'chat_room_duration': ['p(95)<500'],
    },
};

// =============================================================================
// Custom Metrics
// =============================================================================

const messageSendDuration = new Trend('message_send_duration');
const messageListDuration = new Trend('message_list_duration');
const chatRoomDuration = new Trend('chat_room_duration');
const messagesSent = new Counter('messages_sent');
const messageErrors = new Counter('message_errors');
const successfulMessages = new Rate('successful_messages');

// =============================================================================
// Test Data
// =============================================================================

function generateUser() {
    const id = randomString(8);
    return {
        email: `msgtest_${id}@test.com`,
        username: `msguser_${id}`,
        password: 'Test123!@#',
        display_name: `Message Test User ${id}`,
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
        tags: { name: 'register' },
    };

    const response = http.post(url, payload, params);
    let userId = null;

    check(response, {
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

    return userId;
}

function loginUser(email, password) {
    const url = `${USER_SERVICE_URL}/auth/login/json`;
    const payload = JSON.stringify({ email, password });
    const params = {
        headers: { 'Content-Type': 'application/json' },
        tags: { name: 'login' },
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

function getOrCreateChatRoom(token, participantId) {
    const url = `${CHAT_SERVICE_URL}/chat-rooms/check/${participantId}`;
    const params = {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
        },
        tags: { name: 'chat_room' },
    };

    const startTime = Date.now();
    const response = http.get(url, params);
    const duration = Date.now() - startTime;

    chatRoomDuration.add(duration);

    let roomId = null;
    check(response, {
        'chat room created/found': (r) => {
            if (r.status === 200 || r.status === 201) {
                try {
                    const body = JSON.parse(r.body);
                    roomId = body.id || body.room_id;
                    return true;
                } catch (e) {
                    return false;
                }
            }
            return false;
        },
    });

    return roomId;
}

function sendMessage(token, roomId, content) {
    const url = `${CHAT_SERVICE_URL}/messages/${roomId}`;
    const payload = JSON.stringify({
        content: content,
        message_type: 'text',
    });
    const params = {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
        },
        tags: { name: 'send_message' },
    };

    const startTime = Date.now();
    const response = http.post(url, payload, params);
    const duration = Date.now() - startTime;

    messageSendDuration.add(duration);

    const success = check(response, {
        'message sent successfully': (r) => r.status === 200 || r.status === 201,
    });

    if (success) {
        messagesSent.add(1);
        successfulMessages.add(1);
    } else {
        messageErrors.add(1);
        successfulMessages.add(0);
        console.log(`Message send failed: ${response.status} - ${response.body}`);
    }

    return success;
}

function getMessages(token, roomId, limit = 50) {
    const url = `${CHAT_SERVICE_URL}/messages/${roomId}?limit=${limit}`;
    const params = {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
        },
        tags: { name: 'get_messages' },
    };

    const startTime = Date.now();
    const response = http.get(url, params);
    const duration = Date.now() - startTime;

    messageListDuration.add(duration);

    check(response, {
        'messages retrieved': (r) => r.status === 200,
    });

    return response;
}

// =============================================================================
// Main Test Function
// =============================================================================

export default function () {
    // Create two users for chat
    const user1 = generateUser();
    const user2 = generateUser();

    let user1Id, user2Id, token1, token2, roomId;

    group('Setup Users', () => {
        // Register users
        user1Id = registerUser(user1);
        user2Id = registerUser(user2);

        if (!user1Id || !user2Id) {
            console.log('User registration failed, skipping test');
            return;
        }

        sleep(0.3);

        // Login users
        token1 = loginUser(user1.email, user1.password);
        token2 = loginUser(user2.email, user2.password);

        if (!token1 || !token2) {
            console.log('User login failed, skipping test');
            return;
        }
    });

    if (!token1 || !token2) return;

    sleep(0.3);

    group('Chat Room', () => {
        // Create/get chat room
        roomId = getOrCreateChatRoom(token1, user2Id);

        if (!roomId) {
            console.log('Chat room creation failed, skipping test');
            return;
        }
    });

    if (!roomId) return;

    sleep(0.3);

    group('Message Exchange', () => {
        // User 1 sends 5 messages
        for (let i = 1; i <= 5; i++) {
            const content = `[Load Test] Message ${i} from User1 - ${randomString(10)}`;
            sendMessage(token1, roomId, content);
            sleep(0.1); // Small delay between messages
        }

        // User 2 sends 5 messages
        for (let i = 1; i <= 5; i++) {
            const content = `[Load Test] Message ${i} from User2 - ${randomString(10)}`;
            sendMessage(token2, roomId, content);
            sleep(0.1);
        }
    });

    sleep(0.3);

    group('Message Retrieval', () => {
        // Both users retrieve messages
        getMessages(token1, roomId, 50);
        sleep(0.1);
        getMessages(token2, roomId, 50);
    });

    sleep(1); // Think time
}

// =============================================================================
// Setup & Teardown
// =============================================================================

export function setup() {
    console.log('Starting message load test');
    console.log(`User Service: ${USER_SERVICE_URL}`);
    console.log(`Chat Service: ${CHAT_SERVICE_URL}`);

    // Health checks
    const userHealth = http.get(`${USER_SERVICE_URL}/health`);
    const chatHealth = http.get(`${CHAT_SERVICE_URL}/health`);

    if (userHealth.status !== 200) {
        console.error(`User Service health check failed: ${userHealth.status}`);
    }
    if (chatHealth.status !== 200) {
        console.error(`Chat Service health check failed: ${chatHealth.status}`);
    }

    return { startTime: Date.now() };
}

export function teardown(data) {
    const duration = (Date.now() - data.startTime) / 1000;
    console.log(`Message load test completed in ${duration.toFixed(2)} seconds`);
}

#!/usr/bin/env python3
"""
Kafka 테스트 스크립트

이 스크립트는 Kafka Producer와 Consumer가 정상적으로 작동하는지 테스트합니다.
"""

import asyncio
import json
from datetime import datetime, timezone
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer


async def test_producer():
    """Kafka Producer 테스트"""
    print("=" * 60)
    print("🚀 Kafka Producer 테스트 시작")
    print("=" * 60)

    producer = AIOKafkaProducer(
        bootstrap_servers=['localhost:19092', 'localhost:19093', 'localhost:19094'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: str(k).encode('utf-8') if k else None
    )

    try:
        await producer.start()
        print("✅ Producer 시작 성공")

        # 테스트 메시지 전송
        test_message = {
            "__event_type__": "MessageSent",
            "message_id": "test-123",
            "room_id": 1,
            "user_id": 1,
            "username": "테스트유저",
            "content": "안녕하세요! Kafka 테스트 메시지입니다.",
            "message_type": "text",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        print(f"\n📤 메시지 전송 중...")
        metadata = await producer.send_and_wait(
            topic='message.events',
            value=test_message,
            key='1'
        )

        print(f"✅ 메시지 전송 완료!")
        print(f"   - Topic: message.events")
        print(f"   - Partition: {metadata.partition}")
        print(f"   - Offset: {metadata.offset}")
        print(f"   - 내용: {test_message['content']}")

    except Exception as e:
        print(f"❌ Producer 에러: {e}")
    finally:
        await producer.stop()
        print("\n🛑 Producer 종료")


async def test_consumer():
    """Kafka Consumer 테스트"""
    print("\n" + "=" * 60)
    print("🚀 Kafka Consumer 테스트 시작 (10초 동안 메시지 수신)")
    print("=" * 60)

    consumer = AIOKafkaConsumer(
        'message.events',
        bootstrap_servers=['localhost:19092', 'localhost:19093', 'localhost:19094'],
        group_id='test-consumer-group',
        auto_offset_reset='earliest',  # 처음부터 읽기
        enable_auto_commit=True,
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )

    try:
        await consumer.start()
        print("✅ Consumer 시작 성공")
        print("📥 메시지 수신 대기 중...\n")

        message_count = 0

        # 10초 동안 메시지 수신
        async def consume_messages():
            nonlocal message_count
            async for msg in consumer:
                message_count += 1
                print(f"✅ 메시지 #{message_count} 수신:")
                print(f"   - Partition: {msg.partition}")
                print(f"   - Offset: {msg.offset}")
                print(f"   - Key: {msg.key}")
                print(f"   - Value: {json.dumps(msg.value, ensure_ascii=False, indent=2)}")
                print()

        try:
            await asyncio.wait_for(consume_messages(), timeout=10.0)
        except asyncio.TimeoutError:
            print(f"⏱️  10초 타임아웃 - 총 {message_count}개 메시지 수신")

    except Exception as e:
        print(f"❌ Consumer 에러: {e}")
    finally:
        await consumer.stop()
        print("\n🛑 Consumer 종료")


async def test_online_status():
    """온라인 상태 이벤트 테스트"""
    print("\n" + "=" * 60)
    print("🚀 온라인 상태 이벤트 테스트")
    print("=" * 60)

    producer = AIOKafkaProducer(
        bootstrap_servers=['localhost:19092', 'localhost:19093', 'localhost:19094'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: str(k).encode('utf-8') if k else None
    )

    try:
        await producer.start()
        print("✅ Producer 시작 성공")

        # 온라인 상태 변경 이벤트
        online_event = {
            "__event_type__": "UserOnlineStatusChanged",
            "user_id": 1,
            "is_online": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        print(f"\n📤 온라인 상태 이벤트 전송 중...")
        metadata = await producer.send_and_wait(
            topic='user.online_status',
            value=online_event,
            key='1'
        )

        print(f"✅ 이벤트 전송 완료!")
        print(f"   - Topic: user.online_status")
        print(f"   - Partition: {metadata.partition}")
        print(f"   - Offset: {metadata.offset}")

    except Exception as e:
        print(f"❌ 에러: {e}")
    finally:
        await producer.stop()
        print("\n🛑 Producer 종료")


async def main():
    """메인 테스트 실행"""
    print("\n🎯 Kafka 통합 테스트 시작\n")

    # 1. Producer 테스트
    await test_producer()

    # 2. Consumer 테스트 (방금 전송한 메시지 수신)
    await test_consumer()

    # 3. 온라인 상태 이벤트 테스트
    await test_online_status()

    print("\n" + "=" * 60)
    print("✅ 모든 테스트 완료!")
    print("=" * 60)
    print("\n💡 Kafka UI에서 확인하기:")
    print("   http://localhost:8080")
    print("\n💡 Consumer Groups 확인:")
    print("   docker exec bigtech-kafka-1 kafka-consumer-groups \\")
    print("     --bootstrap-server kafka-1:9092 \\")
    print("     --list")
    print()


if __name__ == "__main__":
    asyncio.run(main())

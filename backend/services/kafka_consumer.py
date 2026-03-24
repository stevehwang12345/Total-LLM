#!/usr/bin/env python3
"""
Kafka Consumer for Security Alarms

보안 관제 시스템으로부터 실시간 알람을 수신하는 Kafka Consumer
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import json
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

logger = logging.getLogger(__name__)


class SecurityAlarmConsumer:
    """
    보안 알람 Kafka Consumer

    역할:
    1. Kafka 토픽 'security.alarms'에서 알람 수신
    2. 알람 메시지 검증 및 파싱
    3. Alarm Handler로 전달
    4. 오프셋 자동 커밋
    """

    def __init__(
        self,
        bootstrap_servers: list,
        topic: str,
        group_id: str,
        alarm_handler: Optional[Callable] = None
    ):
        """
        Args:
            bootstrap_servers: Kafka 브로커 주소 리스트
            topic: 구독할 토픽 이름
            group_id: Consumer 그룹 ID
            alarm_handler: 알람 처리 콜백 함수 (async)
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.alarm_handler = alarm_handler

        self.consumer: Optional[AIOKafkaConsumer] = None
        self.is_running = False

        logger.info(f"✅ SecurityAlarmConsumer initialized (topic={topic}, group={group_id})")

    async def start(self):
        """Kafka Consumer 시작"""
        try:
            # AIOKafkaConsumer 생성
            self.consumer = AIOKafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset='latest',  # 최신 메시지부터 읽기
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )

            # Kafka 연결
            await self.consumer.start()
            self.is_running = True

            logger.info(f"🚀 Kafka consumer started (topic={self.topic})")

            # 메시지 수신 루프
            await self._consume_loop()

        except KafkaError as e:
            logger.error(f"❌ Kafka connection error: {e}")
            # Don't raise - let the application continue without Kafka
            self.is_running = False
        except Exception as e:
            logger.error(f"❌ Consumer error: {e}", exc_info=True)
            # Don't raise - let the application continue without Kafka
            self.is_running = False
        finally:
            await self.stop()

    async def stop(self):
        """Kafka Consumer 중지"""
        self.is_running = False

        if self.consumer:
            await self.consumer.stop()
            logger.info("🛑 Kafka consumer stopped")

    async def _consume_loop(self):
        """메시지 수신 루프"""
        logger.info("📡 Listening for alarms...")

        try:
            async for message in self.consumer:
                try:
                    # 메시지 파싱
                    alarm_data = message.value
                    offset = message.offset
                    partition = message.partition
                    timestamp = message.timestamp

                    logger.info(f"📨 Received alarm: offset={offset}, partition={partition}")
                    logger.debug(f"   Data: {alarm_data}")

                    # 알람 검증
                    validated_alarm = self._validate_alarm(alarm_data, offset)

                    # Alarm Handler 호출
                    if self.alarm_handler:
                        await self.alarm_handler(validated_alarm)
                    else:
                        logger.warning("⚠️ No alarm handler configured")

                except json.JSONDecodeError as e:
                    logger.error(f"❌ Invalid JSON message: {e}")
                    continue
                except Exception as e:
                    logger.error(f"❌ Error processing alarm: {e}", exc_info=True)
                    continue

        except asyncio.CancelledError:
            logger.info("🛑 Consumer loop cancelled")
        except Exception as e:
            logger.error(f"❌ Consumer loop error: {e}", exc_info=True)
            raise

    def _validate_alarm(self, alarm_data: Dict[str, Any], offset: int) -> Dict[str, Any]:
        """
        알람 메시지 검증 및 정규화

        Expected format:
        {
            "alarm_id": "ALARM-20250109-001234",
            "alarm_type": "intrusion_detection",
            "severity": "CRITICAL",
            "location": "A동 3층 복도",
            "timestamp": "2025-01-09T15:30:45.123Z",
            "image_url": "http://monitoring-system/images/alarm-001234.jpg",
            "device_id": "CCTV-A301",
            "description": "침입 감지됨"
        }

        Returns:
            검증된 알람 데이터 (kafka_offset 추가)
        """
        required_fields = ["alarm_id", "alarm_type", "severity", "location", "timestamp"]

        # 필수 필드 검증
        for field in required_fields:
            if field not in alarm_data:
                raise ValueError(f"Missing required field: {field}")

        # Severity 검증
        valid_severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        if alarm_data["severity"] not in valid_severities:
            logger.warning(f"⚠️ Invalid severity: {alarm_data['severity']}, defaulting to MEDIUM")
            alarm_data["severity"] = "MEDIUM"

        # Timestamp 파싱
        try:
            timestamp_str = alarm_data["timestamp"]
            # ISO 8601 형식 파싱
            alarm_data["timestamp"] = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"⚠️ Invalid timestamp: {e}, using current time")
            alarm_data["timestamp"] = datetime.now()

        # Kafka offset 추가
        alarm_data["kafka_offset"] = offset

        # 선택 필드 기본값 설정
        alarm_data.setdefault("image_url", None)
        alarm_data.setdefault("device_id", None)
        alarm_data.setdefault("description", "")

        return alarm_data


# ============================================
# Standalone 실행용 (테스트)
# ============================================

async def test_alarm_handler(alarm: Dict[str, Any]):
    """테스트용 알람 핸들러"""
    print(f"🔔 Alarm received: {alarm['alarm_id']}")
    print(f"   Type: {alarm['alarm_type']}")
    print(f"   Severity: {alarm['severity']}")
    print(f"   Location: {alarm['location']}")
    print(f"   Timestamp: {alarm['timestamp']}")
    if alarm.get('image_url'):
        print(f"   Image: {alarm['image_url']}")


async def main():
    """테스트 실행"""
    import yaml
    from pathlib import Path

    # Config 로드
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    kafka_config = config['security']['kafka']

    # Consumer 생성
    consumer = SecurityAlarmConsumer(
        bootstrap_servers=kafka_config['bootstrap_servers'],
        topic=kafka_config['topic'],
        group_id=kafka_config['group_id'],
        alarm_handler=test_alarm_handler
    )

    # 실행
    try:
        await consumer.start()
    except KeyboardInterrupt:
        print("\n🛑 Stopping consumer...")
        await consumer.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    asyncio.run(main())

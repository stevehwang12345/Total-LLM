#!/usr/bin/env python3
"""
WebSocket Broadcaster

실시간 알람을 프론트엔드에 전송하는 WebSocket 서버
"""

import asyncio
import logging
import json
from typing import Set, Dict, Any
from datetime import datetime
import websockets
from websockets.server import WebSocketServerProtocol

logger = logging.getLogger(__name__)


class WebSocketBroadcaster:
    """
    WebSocket 브로드캐스터

    역할:
    1. WebSocket 클라이언트 연결 관리
    2. 실시간 알람 브로드캐스팅
    3. 연결 상태 모니터링
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 9003):
        """
        Args:
            host: WebSocket 서버 호스트
            port: WebSocket 서버 포트
        """
        self.host = host
        self.port = port
        self.clients: Set[WebSocketServerProtocol] = set()
        self.server = None

        logger.info(f"✅ WebSocketBroadcaster initialized (ws://{host}:{port})")

    async def start(self):
        """WebSocket 서버 시작"""
        self.server = await websockets.serve(
            self._handle_client,
            self.host,
            self.port
        )

        logger.info(f"🚀 WebSocket server started on ws://{self.host}:{self.port}")

        # 서버 실행 유지
        await asyncio.Future()  # Run forever

    async def stop(self):
        """WebSocket 서버 중지"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("🛑 WebSocket server stopped")

    # ============================================
    # 클라이언트 연결 관리
    # ============================================

    async def _handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """
        클라이언트 연결 처리

        Args:
            websocket: WebSocket 연결
            path: 요청 경로
        """
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"🔌 Client connected: {client_id} (path={path})")

        # 클라이언트 등록
        self.clients.add(websocket)

        try:
            # 환영 메시지 전송
            await self._send_welcome(websocket)

            # 클라이언트 메시지 수신 루프
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._handle_client_message(websocket, data)
                except json.JSONDecodeError:
                    logger.warning(f"⚠️ Invalid JSON from {client_id}")
                except Exception as e:
                    logger.error(f"❌ Error handling message: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🔌 Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"❌ Client error: {e}", exc_info=True)
        finally:
            # 클라이언트 제거
            self.clients.discard(websocket)
            logger.info(f"   Active clients: {len(self.clients)}")

    async def _send_welcome(self, websocket: WebSocketServerProtocol):
        """환영 메시지 전송"""
        welcome_msg = {
            "type": "connection",
            "status": "connected",
            "timestamp": datetime.now().isoformat(),
            "message": "WebSocket connection established"
        }

        await websocket.send(json.dumps(welcome_msg))

    async def _handle_client_message(
        self,
        websocket: WebSocketServerProtocol,
        data: Dict[str, Any]
    ):
        """
        클라이언트로부터 받은 메시지 처리

        지원 메시지:
        - {"type": "ping"} → {"type": "pong"}
        - {"type": "subscribe", "channels": [...]} → 채널 구독
        """
        msg_type = data.get("type")

        if msg_type == "ping":
            # Ping-Pong
            await websocket.send(json.dumps({
                "type": "pong",
                "timestamp": datetime.now().isoformat()
            }))

        elif msg_type == "subscribe":
            # 채널 구독 (향후 확장용)
            channels = data.get("channels", [])
            logger.info(f"   Client subscribed to: {channels}")
            await websocket.send(json.dumps({
                "type": "subscribed",
                "channels": channels
            }))

        else:
            logger.warning(f"⚠️ Unknown message type: {msg_type}")

    # ============================================
    # 브로드캐스팅
    # ============================================

    async def broadcast(self, message: Dict[str, Any]):
        """
        모든 연결된 클라이언트에게 메시지 브로드캐스트

        Args:
            message: 전송할 메시지 (dict)
        """
        if not self.clients:
            logger.debug("📡 No clients connected, skipping broadcast")
            return

        # JSON 직렬화
        message_json = json.dumps(message)

        # 모든 클라이언트에게 전송
        disconnected_clients = set()

        for client in self.clients:
            try:
                await client.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"❌ Broadcast error: {e}")
                disconnected_clients.add(client)

        # 연결 종료된 클라이언트 제거
        self.clients -= disconnected_clients

        logger.info(f"📡 Broadcasted to {len(self.clients)} clients")

    async def send_to_client(
        self,
        websocket: WebSocketServerProtocol,
        message: Dict[str, Any]
    ):
        """
        특정 클라이언트에게만 메시지 전송

        Args:
            websocket: 대상 WebSocket 연결
            message: 전송할 메시지
        """
        try:
            message_json = json.dumps(message)
            await websocket.send(message_json)
        except Exception as e:
            logger.error(f"❌ Send error: {e}")

    # ============================================
    # 상태 조회
    # ============================================

    def get_stats(self) -> Dict[str, Any]:
        """
        서버 통계 조회

        Returns:
            {
                "connected_clients": int,
                "host": str,
                "port": int,
                "running": bool
            }
        """
        return {
            "connected_clients": len(self.clients),
            "host": self.host,
            "port": self.port,
            "running": self.server is not None
        }


# ============================================
# Standalone 실행용 (테스트)
# ============================================

async def test_broadcaster():
    """테스트 실행"""
    broadcaster = WebSocketBroadcaster(host="0.0.0.0", port=9003)

    # 백그라운드에서 서버 실행
    server_task = asyncio.create_task(broadcaster.start())

    # 5초마다 테스트 메시지 브로드캐스트
    try:
        await asyncio.sleep(2)  # 서버 시작 대기

        for i in range(10):
            test_message = {
                "type": "test",
                "count": i,
                "timestamp": datetime.now().isoformat(),
                "message": f"Test broadcast {i}"
            }

            await broadcaster.broadcast(test_message)
            print(f"📡 Sent test message {i}")

            await asyncio.sleep(5)

    except KeyboardInterrupt:
        print("\n🛑 Stopping broadcaster...")
        await broadcaster.stop()
        server_task.cancel()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    asyncio.run(test_broadcaster())

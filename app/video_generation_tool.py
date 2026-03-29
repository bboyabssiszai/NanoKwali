from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.bus.events import OutboundMessage


class VideoGenerationTool(Tool):
    def __init__(
        self,
        generate_callback: Callable[..., Awaitable[None]],
        send_callback: Callable[[OutboundMessage], Awaitable[None]] | None = None,
    ) -> None:
        self._generate_callback = generate_callback
        self._send_callback = send_callback
        self._session_id = ""
        self._channel = ""
        self._request_text = ""
        self._is_scheduled_turn = False
        self._sent_in_turn = False

    def set_context(self, channel: str, chat_id: str, _message_id: str | None = None) -> None:
        self._channel = channel
        if channel == "web":
            self._session_id = chat_id

    def set_request_text(self, text: str) -> None:
        self._request_text = text or ""
        self._is_scheduled_turn = self._request_text.startswith("[Scheduled Task]")

    def start_turn(self) -> None:
        self._sent_in_turn = False

    def _looks_like_scheduled_request(self) -> bool:
        text = self._request_text
        if self._is_scheduled_turn:
            return False
        markers = (
            "提醒",
            "分钟后",
            "小时后",
            "天后",
            "今晚",
            "明天",
            "后天",
            "稍后",
            "之后",
            "先",
        )
        return any(marker in text for marker in markers)

    @property
    def name(self) -> str:
        return "generate_video"

    @property
    def description(self) -> str:
        return (
            "Generate a playable AI video clip with Kling for the current user session. "
            "Use this when the user clearly wants a video created now. "
            "Do not use this for reminders, planning-only requests, or future-scheduled tasks."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Direct video-generation prompt or scene description.",
                    "minLength": 1,
                },
                "negative_prompt": {
                    "type": "string",
                    "description": "Optional negative prompt.",
                },
                "model_name": {
                    "type": "string",
                    "description": "Video model name. Defaults to kling-v2-6.",
                },
                "mode": {
                    "type": "string",
                    "description": "Generation mode, for example pro.",
                },
                "duration": {
                    "type": "string",
                    "description": "Duration in seconds as a string, for example 10.",
                },
                "aspect_ratio": {
                    "type": "string",
                    "description": "Aspect ratio such as 16:9 or 9:16.",
                },
            },
            "required": ["prompt"],
        }

    async def execute(
        self,
        prompt: str,
        negative_prompt: str | None = None,
        model_name: str = "kling-v2-6",
        mode: str = "pro",
        duration: str = "10",
        aspect_ratio: str = "16:9",
        **_kwargs: Any,
    ) -> str:
        if not self._session_id:
            return "Error: no active web session for video generation"
        if self._looks_like_scheduled_request():
            return (
                "Error: this request is future-timed or multi-step. "
                "Schedule or plan it first, and only generate the video when execution time arrives."
            )
        await self._generate_callback(
            session_id=self._session_id,
            prompt=prompt,
            negative_prompt=negative_prompt,
            model_name=model_name,
            mode=mode,
            duration=duration,
            aspect_ratio=aspect_ratio,
        )
        if self._send_callback and self._channel and self._session_id:
            await self._send_callback(OutboundMessage(
                channel=self._channel,
                chat_id=self._session_id,
                content="视频任务已开始执行，生成完成后会直接返回可播放结果。",
            ))
            self._sent_in_turn = True
        return (
            "Video generation started for the current session. "
            "Do not repeat status updates or add a long creative preview unless the user explicitly asked for one."
        )

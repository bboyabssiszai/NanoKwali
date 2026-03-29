from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from nanobot.agent.tools.base import Tool


class VideoGenerationTool(Tool):
    def __init__(
        self,
        generate_callback: Callable[..., Awaitable[None]],
    ) -> None:
        self._generate_callback = generate_callback
        self._session_id = ""

    def set_context(self, channel: str, chat_id: str) -> None:
        if channel == "web":
            self._session_id = chat_id

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
        await self._generate_callback(
            session_id=self._session_id,
            prompt=prompt,
            negative_prompt=negative_prompt,
            model_name=model_name,
            mode=mode,
            duration=duration,
            aspect_ratio=aspect_ratio,
        )
        return (
            "Video generation started for the current session. "
            "Do not repeat status updates or add a long creative preview unless the user explicitly asked for one."
        )

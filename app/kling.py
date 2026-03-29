from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import jwt
import requests


@dataclass(slots=True)
class KlingConfig:
    access_key: str
    secret_key: str
    base_url: str = "https://api-beijing.klingai.com"


class KlingClient:
    def __init__(self, config: KlingConfig):
        self.config = config

    def _token(self) -> str:
        now = int(time.time())
        return jwt.encode(
            {
                "iss": self.config.access_key,
                "exp": now + 1800,
                "nbf": now - 5,
            },
            self.config.secret_key,
            algorithm="HS256",
            headers={"alg": "HS256", "typ": "JWT"},
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token()}",
        }

    def create_text_to_video(
        self,
        *,
        prompt: str,
        model_name: str = "kling-v2-1",
        mode: str = "std",
        duration: str = "5",
        aspect_ratio: str = "16:9",
        negative_prompt: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "model_name": model_name,
            "prompt": prompt,
            "negative_prompt": negative_prompt or "",
            "cfg_scale": 0.6,
            "mode": mode,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
        }
        response = requests.post(
            f"{self.config.base_url}/v1/videos/text2video",
            json=payload,
            headers=self._headers(),
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def get_text_to_video(self, task_id: str) -> dict[str, Any]:
        response = requests.get(
            f"{self.config.base_url}/v1/videos/text2video/{task_id}",
            headers=self._headers(),
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

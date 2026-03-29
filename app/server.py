from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from nanobot.agent.loop import AgentLoop
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.cli.commands import _make_provider
from nanobot.config.loader import load_config, save_config, set_config_path
from nanobot.cron.service import CronService
from nanobot.cron.types import CronJob
from nanobot.heartbeat.service import HeartbeatService
from nanobot.session.manager import SessionManager
from nanobot.utils.helpers import sync_workspace_templates
import typer

from app.kling import KlingClient, KlingConfig


ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "web"
BOOTSTRAP_WORKSPACE_DIR = ROOT / "bootstrap_workspace"
DEFAULT_RUNTIME_DIR = ROOT / "runtime"
RUNTIME_DIR = Path(os.getenv("NANOKWALI_RUNTIME_DIR", str(DEFAULT_RUNTIME_DIR))).expanduser()
WORKSPACE_DIR = RUNTIME_DIR / "workspace"
CONFIG_PATH = RUNTIME_DIR / "nanobot-config.json"
CONFIG_EXAMPLE_PATH = ROOT / "runtime" / "nanobot-config.example.json"
load_dotenv(ROOT / ".env")


def _copy_missing_tree(source: Path, target: Path) -> None:
    if not source.exists():
        return
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        destination = target / relative
        if item.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(item, destination)


def _seed_runtime_dir() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists() and CONFIG_EXAMPLE_PATH.exists():
        shutil.copy2(CONFIG_EXAMPLE_PATH, CONFIG_PATH)
    _copy_missing_tree(BOOTSTRAP_WORKSPACE_DIR, WORKSPACE_DIR)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class SessionRequest(BaseModel):
    session_id: str | None = None


class VideoGenerateRequest(BaseModel):
    session_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    negative_prompt: str | None = None
    model_name: str = "kling-v2-1"
    mode: str = "std"
    duration: str = "5"
    aspect_ratio: str = "16:9"
    kling_access_key: str | None = None
    kling_secret_key: str | None = None


class AgentService:
    def __init__(self) -> None:
        self.bus = MessageBus()
        self.session_manager = SessionManager(WORKSPACE_DIR)
        self.cron = CronService(WORKSPACE_DIR / "cron" / "jobs.json")
        self.active_web_sessions: dict[str, float] = {}
        self.streams: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}
        self._tasks: list[asyncio.Task[Any]] = []
        self._started = False
        self.startup_error: str | None = None
        self.agent: AgentLoop | None = None
        self.heartbeat: HeartbeatService | None = None
        self.current_provider: str | None = None
        self.kling_client: KlingClient | None = None

    async def start(self) -> None:
        if self._started:
            return

        try:
            config = self._load_runtime_config()
            self.current_provider = config.agents.defaults.provider
            sync_workspace_templates(config.workspace_path)
            provider = _make_provider(config)
            self.kling_client = self._build_kling_client()
            self.agent = AgentLoop(
                bus=self.bus,
                provider=provider,
                workspace=config.workspace_path,
                model=config.agents.defaults.model,
                max_iterations=config.agents.defaults.max_tool_iterations,
                context_window_tokens=config.agents.defaults.context_window_tokens,
                web_search_config=config.tools.web.search,
                web_proxy=config.tools.web.proxy or None,
                exec_config=config.tools.exec,
                cron_service=self.cron,
                restrict_to_workspace=config.tools.restrict_to_workspace,
                session_manager=self.session_manager,
                mcp_servers=config.tools.mcp_servers,
                channels_config=config.channels,
                timezone=config.agents.defaults.timezone,
            )
        except typer.Exit as exc:
            code = getattr(exc, "exit_code", 1)
            provider_name = self.current_provider or "unknown"
            if provider_name == "moonshot":
                self.startup_error = (
                    "Moonshot provider startup failed. "
                    "Please confirm Zeabur environment variable MOONSHOT_API_KEY is set "
                    "and redeploy the service."
                )
            else:
                self.startup_error = (
                    f"Provider startup failed for '{provider_name}' "
                    f"(exit code {code}). Please check service environment variables."
                )
            return
        except BaseException as exc:
            self.startup_error = str(exc)
            return

        async def on_cron_job(job: CronJob) -> str | None:
            from nanobot.agent.tools.cron import CronTool
            from nanobot.agent.tools.message import MessageTool
            from nanobot.utils.evaluator import evaluate_response

            reminder_note = (
                "[Scheduled Task] Timer finished.\n\n"
                f"Task '{job.name}' has been triggered.\n"
                f"Scheduled instruction: {job.payload.message}"
            )

            cron_tool = self.agent.tools.get("cron")
            cron_token = None
            if isinstance(cron_tool, CronTool):
                cron_token = cron_tool.set_cron_context(True)
            try:
                resp = await self.agent.process_direct(
                    reminder_note,
                    session_key=f"cron:{job.id}",
                    channel=job.payload.channel or "web",
                    chat_id=job.payload.to or "default",
                )
            finally:
                if isinstance(cron_tool, CronTool) and cron_token is not None:
                    cron_tool.reset_cron_context(cron_token)

            response = resp.content if resp else ""

            message_tool = self.agent.tools.get("message")
            if isinstance(message_tool, MessageTool) and message_tool._sent_in_turn:
                return response

            if job.payload.deliver and job.payload.to and response:
                should_notify = await evaluate_response(
                    response, job.payload.message, provider, self.agent.model,
                )
                if should_notify:
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=job.payload.channel or "web",
                        chat_id=job.payload.to,
                        content=response,
                        metadata={"kind": "reminder"},
                    ))
            return response

        self.cron.on_job = on_cron_job

        async def on_heartbeat_execute(tasks: str) -> str:
            chat_id = self._pick_heartbeat_target()
            resp = await self.agent.process_direct(
                tasks,
                session_key="heartbeat",
                channel="web",
                chat_id=chat_id,
                on_progress=self._silent_progress,
            )
            session = self.agent.sessions.get_or_create("heartbeat")
            session.retain_recent_legal_suffix(config.gateway.heartbeat.keep_recent_messages)
            self.agent.sessions.save(session)
            return resp.content if resp else ""

        async def on_heartbeat_notify(response: str) -> None:
            chat_id = self._pick_heartbeat_target()
            if not chat_id:
                return
            await self.bus.publish_outbound(OutboundMessage(
                channel="web",
                chat_id=chat_id,
                content=response,
                metadata={"kind": "heartbeat"},
            ))

        hb_cfg = config.gateway.heartbeat
        self.heartbeat = HeartbeatService(
            workspace=config.workspace_path,
            provider=provider,
            model=self.agent.model,
            on_execute=on_heartbeat_execute,
            on_notify=on_heartbeat_notify,
            interval_s=hb_cfg.interval_s,
            enabled=hb_cfg.enabled,
            timezone=config.agents.defaults.timezone,
        )

        self._tasks = [
            asyncio.create_task(self.agent.run(), name="nanokwali-agent"),
            asyncio.create_task(self._fan_out_outbound(), name="nanokwali-fanout"),
        ]
        await self.cron.start()
        await self.heartbeat.start()
        self._started = True
        self.startup_error = None

    async def stop(self) -> None:
        if not self._started:
            return
        if self.heartbeat is not None:
            self.heartbeat.stop()
        self.cron.stop()
        if self.agent is not None:
            self.agent.stop()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with suppress(asyncio.CancelledError):
                await task
        if self.agent is not None:
            await self.agent.close_mcp()
        self._started = False

    def _build_kling_client(self) -> KlingClient | None:
        access_key = os.getenv("KLING_ACCESS_KEY", "").strip()
        secret_key = os.getenv("KLING_SECRET_KEY", "").strip()
        if not access_key or not secret_key:
            return None
        return KlingClient(KlingConfig(access_key=access_key, secret_key=secret_key))

    def _resolve_kling_client(
        self,
        *,
        access_key: str | None = None,
        secret_key: str | None = None,
    ) -> KlingClient | None:
        request_access_key = (access_key or "").strip()
        request_secret_key = (secret_key or "").strip()
        if request_access_key and request_secret_key:
            return KlingClient(
                KlingConfig(access_key=request_access_key, secret_key=request_secret_key)
            )
        return self.kling_client

    def _load_runtime_config(self):
        from nanobot.providers.registry import PROVIDERS

        set_config_path(CONFIG_PATH)
        if not CONFIG_PATH.exists():
            raise RuntimeError(
                f"Missing config file: {CONFIG_PATH}. Copy runtime/nanobot-config.example.json "
                "to runtime/nanobot-config.json and fill in your model and API key."
            )
        config = load_config(CONFIG_PATH)
        config.agents.defaults.workspace = str(WORKSPACE_DIR)

        migrated = False
        moonshot_key = os.getenv("MOONSHOT_API_KEY", "").strip()
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()

        if (
            config.agents.defaults.provider == "openrouter"
            and moonshot_key
            and not openrouter_key
        ):
            config.agents.defaults.provider = "moonshot"
            if not config.agents.defaults.model or config.agents.defaults.model.startswith("openrouter/"):
                config.agents.defaults.model = "kimi-k2.5"
            config.providers.moonshot.api_base = "https://api.moonshot.cn/v1"
            migrated = True

        for spec in PROVIDERS:
            if not spec.env_key:
                continue
            provider_cfg = getattr(config.providers, spec.name, None)
            env_key = os.getenv(spec.env_key, "").strip()
            if provider_cfg is not None and not provider_cfg.api_key and env_key:
                provider_cfg.api_key = env_key

        if migrated:
            save_config(config, CONFIG_PATH)
        return config

    async def _fan_out_outbound(self) -> None:
        while True:
            msg = await self.bus.consume_outbound()
            if msg.channel != "web":
                continue
            await self._broadcast(msg.chat_id, self._to_event(msg))

    async def _broadcast(self, session_id: str, event: dict[str, Any]) -> None:
        queues = list(self.streams.get(session_id, set()))
        if not queues:
            return
        for queue in queues:
            await queue.put(event)

    async def _emit_session_event(
        self,
        session_id: str,
        event_type: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self._broadcast(
            session_id,
            {
                "type": event_type,
                "content": content,
                "metadata": metadata or {},
                "timestamp": time.time(),
            },
        )

    def _to_event(self, msg: OutboundMessage) -> dict[str, Any]:
        metadata = dict(msg.metadata or {})
        if metadata.get("_stream_delta"):
            event_type = "stream_delta"
        elif metadata.get("_stream_end"):
            event_type = "stream_end"
        elif metadata.get("_progress"):
            event_type = "progress"
        else:
            event_type = metadata.get("kind") or "message"

        return {
            "type": event_type,
            "content": msg.content,
            "metadata": metadata,
            "timestamp": time.time(),
        }

    async def _silent_progress(self, *_args: Any, **_kwargs: Any) -> None:
        return

    def register_session(self, session_id: str) -> None:
        self.active_web_sessions[session_id] = time.time()

    def create_session(self) -> str:
        session_id = uuid.uuid4().hex
        self.register_session(session_id)
        return session_id

    def _pick_heartbeat_target(self) -> str:
        if not self.active_web_sessions:
            return "default"
        return max(self.active_web_sessions.items(), key=lambda item: item[1])[0]

    async def enqueue_message(self, session_id: str, message: str) -> None:
        if self.startup_error:
            raise RuntimeError(self.startup_error)
        self.register_session(session_id)
        await self.bus.publish_inbound(InboundMessage(
            channel="web",
            sender_id="user",
            chat_id=session_id,
            content=message,
            metadata={"_wants_stream": True},
        ))

    def _track_task(self, coro, *, name: str) -> None:
        task = asyncio.create_task(coro, name=name)
        self._tasks.append(task)
        task.add_done_callback(lambda done: self._tasks.remove(done) if done in self._tasks else None)

    async def enqueue_video_generation(
        self,
        *,
        session_id: str,
        prompt: str,
        negative_prompt: str | None,
        model_name: str,
        mode: str,
        duration: str,
        aspect_ratio: str,
        kling_access_key: str | None = None,
        kling_secret_key: str | None = None,
    ) -> None:
        kling_client = self._resolve_kling_client(
            access_key=kling_access_key,
            secret_key=kling_secret_key,
        )
        if not kling_client:
            raise RuntimeError(
                "Kling video generation is not configured. Please add Kling AK/SK in the page settings first."
            )
        self.register_session(session_id)
        self._track_task(
            self._run_video_generation(
                session_id=session_id,
                prompt=prompt,
                negative_prompt=negative_prompt,
                model_name=model_name,
                mode=mode,
                duration=duration,
                aspect_ratio=aspect_ratio,
                kling_client=kling_client,
            ),
            name=f"video-generation:{session_id}:{time.time_ns()}",
        )

    async def _run_video_generation(
        self,
        *,
        session_id: str,
        prompt: str,
        negative_prompt: str | None,
        model_name: str,
        mode: str,
        duration: str,
        aspect_ratio: str,
        kling_client: KlingClient,
    ) -> None:
        await self._emit_session_event(
            session_id,
            "video_status",
            "正在提交视频生成任务，这通常需要几分钟。",
            {"stage": "queued"},
        )
        try:
            create_result = await asyncio.to_thread(
                kling_client.create_text_to_video,
                prompt=prompt,
                model_name=model_name,
                mode=mode,
                duration=duration,
                aspect_ratio=aspect_ratio,
                negative_prompt=negative_prompt,
            )
        except Exception as exc:
            await self._emit_session_event(
                session_id,
                "video_error",
                f"视频任务创建失败：{exc}",
            )
            return

        task_id = ((create_result or {}).get("data") or {}).get("task_id")
        if not task_id:
            await self._emit_session_event(
                session_id,
                "video_error",
                "视频任务创建失败：未拿到 task_id。",
                {"raw": create_result},
            )
            return

        await self._emit_session_event(
            session_id,
            "video_status",
            "视频任务已提交，正在等待 Kling 生成结果。",
            {"stage": "submitted", "taskId": task_id},
        )

        start = time.time()
        while True:
            if time.time() - start > 1800:
                await self._emit_session_event(
                    session_id,
                    "video_error",
                    "视频生成超时，请稍后重试。",
                    {"taskId": task_id},
                )
                return
            try:
                status_result = await asyncio.to_thread(kling_client.get_text_to_video, task_id)
            except Exception as exc:
                await self._emit_session_event(
                    session_id,
                    "video_error",
                    f"查询视频状态失败：{exc}",
                    {"taskId": task_id},
                )
                return

            data = (status_result or {}).get("data") or {}
            task_status = data.get("task_status")
            if task_status == "succeed":
                videos = ((data.get("task_result") or {}).get("videos") or [])
                video_url = videos[0].get("url") if videos else None
                if not video_url:
                    await self._emit_session_event(
                        session_id,
                        "video_error",
                        "视频任务完成了，但没有返回可播放链接。",
                        {"taskId": task_id},
                    )
                    return
                await self._emit_session_event(
                    session_id,
                    "video_result",
                    "视频生成完成，可以直接预览。",
                    {
                        "taskId": task_id,
                        "videoUrl": video_url,
                        "prompt": prompt,
                        "modelName": model_name,
                        "duration": duration,
                        "aspectRatio": aspect_ratio,
                    },
                )
                return
            if task_status == "failed":
                await self._emit_session_event(
                    session_id,
                    "video_error",
                    f"视频生成失败：{data.get('task_status_msg') or '未知错误'}",
                    {"taskId": task_id},
                )
                return

            await self._emit_session_event(
                session_id,
                "video_status",
                "视频仍在生成中，请稍等。",
                {"stage": task_status or "processing", "taskId": task_id},
            )
            await asyncio.sleep(10)

    async def stream(self, session_id: str):
        self.register_session(session_id)
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.streams.setdefault(session_id, set()).add(queue)
        await queue.put({"type": "ready", "content": "", "timestamp": time.time()})
        try:
            while True:
                event = await queue.get()
                payload = f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                yield payload.encode("utf-8")
        finally:
            streams = self.streams.get(session_id)
            if streams:
                streams.discard(queue)
                if not streams:
                    self.streams.pop(session_id, None)


service = AgentService()
app = FastAPI(title="NanoKwali Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.on_event("startup")
async def startup() -> None:
    _seed_runtime_dir()
    await service.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await service.stop()


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
async def status() -> JSONResponse:
    return JSONResponse({
        "ok": service.startup_error is None,
        "configExists": CONFIG_PATH.exists(),
        "workspace": str(WORKSPACE_DIR),
        "startupError": service.startup_error,
        "provider": service.current_provider,
        "env": {
            "MOONSHOT_API_KEY": bool(os.getenv("MOONSHOT_API_KEY", "").strip()),
            "KLING_ACCESS_KEY": bool(os.getenv("KLING_ACCESS_KEY", "").strip()),
            "KLING_SECRET_KEY": bool(os.getenv("KLING_SECRET_KEY", "").strip()),
            "NANOKWALI_RUNTIME_DIR": os.getenv("NANOKWALI_RUNTIME_DIR", ""),
        },
        "videoConfig": {
            "supportsBrowserKlingKeys": True,
            "serverKlingConfigured": service.kling_client is not None,
        },
    })


@app.post("/api/session")
async def create_session(payload: SessionRequest) -> JSONResponse:
    session_id = payload.session_id or service.create_session()
    service.register_session(session_id)
    return JSONResponse({"sessionId": session_id})


@app.post("/api/chat")
async def chat(payload: ChatRequest) -> JSONResponse:
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    try:
        await service.enqueue_message(payload.session_id, payload.message.strip())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JSONResponse({"queued": True})


@app.post("/api/video/generate")
async def generate_video(payload: VideoGenerateRequest) -> JSONResponse:
    if not payload.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
    try:
        await service.enqueue_video_generation(
            session_id=payload.session_id,
            prompt=payload.prompt.strip(),
            negative_prompt=payload.negative_prompt,
            model_name=payload.model_name,
            mode=payload.mode,
            duration=payload.duration,
            aspect_ratio=payload.aspect_ratio,
            kling_access_key=payload.kling_access_key,
            kling_secret_key=payload.kling_secret_key,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JSONResponse({"queued": True})


@app.get("/api/events")
async def events(session_id: str) -> StreamingResponse:
    if not session_id.strip():
        raise HTTPException(status_code=400, detail="session_id is required.")
    return StreamingResponse(
        service.stream(session_id.strip()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/favicon.ico")
async def favicon() -> FileResponse:
    return FileResponse(ROOT / "nanobot" / "nanobot_logo.png")

const chatLog = document.getElementById("chatLog");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const notifyButton = document.getElementById("notifyButton");
const sendButton = document.getElementById("sendButton");
const videoButton = document.getElementById("videoButton");
const videoConfigButton = document.getElementById("videoConfigButton");
const videoConfigPanel = document.getElementById("videoConfigPanel");
const klingAccessKeyInput = document.getElementById("klingAccessKeyInput");
const klingSecretKeyInput = document.getElementById("klingSecretKeyInput");
const saveVideoConfigButton = document.getElementById("saveVideoConfigButton");
const clearVideoConfigButton = document.getElementById("clearVideoConfigButton");
const videoConfigStatus = document.getElementById("videoConfigStatus");

const KLING_ACCESS_KEY_STORAGE = "nanokwali_kling_access_key";
const KLING_SECRET_KEY_STORAGE = "nanokwali_kling_secret_key";

let sessionId = localStorage.getItem("nanokwali_session_id") || "";
let currentAssistantBubble = null;
let appStatus = null;

function addBubble(role, content) {
  const bubble = document.createElement("article");
  bubble.className = `bubble ${role}`;
  bubble.textContent = content;
  chatLog.appendChild(bubble);
  chatLog.scrollTop = chatLog.scrollHeight;
  return bubble;
}

function addVideoBubble(videoUrl, caption = "已生成视频") {
  const bubble = document.createElement("article");
  bubble.className = "bubble assistant video-bubble";

  const label = document.createElement("p");
  label.className = "video-label";
  label.textContent = caption;

  const video = document.createElement("video");
  video.className = "generated-video";
  video.src = videoUrl;
  video.controls = true;
  video.playsInline = true;
  video.preload = "metadata";

  const link = document.createElement("a");
  link.href = videoUrl;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = "打开原视频";
  link.className = "video-link";

  bubble.appendChild(label);
  bubble.appendChild(video);
  bubble.appendChild(link);
  chatLog.appendChild(bubble);
  chatLog.scrollTop = chatLog.scrollHeight;
  return bubble;
}

function addIntro() {
  addBubble(
    "assistant",
    "我是你的“一键成片”专属 agent。你可以直接让我拆选题、写脚本、排镜头，或者说“今晚 8 点提醒我开始剪第一版”。",
  );
}

function maskSecret(value) {
  if (!value) {
    return "未配置";
  }
  if (value.length <= 8) {
    return `${value.slice(0, 2)}***${value.slice(-2)}`;
  }
  return `${value.slice(0, 4)}...${value.slice(-4)}`;
}

function getStoredKlingConfig() {
  return {
    accessKey: localStorage.getItem(KLING_ACCESS_KEY_STORAGE) || "",
    secretKey: localStorage.getItem(KLING_SECRET_KEY_STORAGE) || "",
  };
}

function setVideoConfigStatus(message) {
  videoConfigStatus.textContent = message;
}

function refreshVideoConfigUI() {
  const config = getStoredKlingConfig();
  if (klingAccessKeyInput) {
    klingAccessKeyInput.value = config.accessKey;
  }
  if (klingSecretKeyInput) {
    klingSecretKeyInput.value = config.secretKey;
  }
  if (config.accessKey && config.secretKey) {
    setVideoConfigStatus(`已保存浏览器本地 Kling 凭证：AK ${maskSecret(config.accessKey)} / SK ${maskSecret(config.secretKey)}`);
    return;
  }
  if (appStatus && appStatus.videoConfig && appStatus.videoConfig.serverKlingConfigured) {
    setVideoConfigStatus("当前服务端已经配置了 Kling 凭证，可以直接生成视频。");
    return;
  }
  setVideoConfigStatus("还没有保存 Kling 凭证。");
}

function toggleVideoConfigPanel(forceOpen) {
  const shouldOpen = typeof forceOpen === "boolean"
    ? forceOpen
    : videoConfigPanel.classList.contains("hidden");
  videoConfigPanel.classList.toggle("hidden", !shouldOpen);
}

async function ensureSession() {
  const response = await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId || null }),
  });
  const data = await response.json();
  sessionId = data.sessionId;
  localStorage.setItem("nanokwali_session_id", sessionId);
}

function startEventStream() {
  const source = new EventSource(`/api/events?session_id=${encodeURIComponent(sessionId)}`);

  source.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    handleEvent(payload);
  };

  source.onerror = () => {
    source.close();
    setTimeout(startEventStream, 1200);
  };
}

function handleEvent(payload) {
  if (payload.type === "ready") {
    return;
  }

  if (payload.type === "progress") {
    return;
  }

  if (payload.type === "stream_delta") {
    if (!currentAssistantBubble) {
      currentAssistantBubble = addBubble("assistant", "");
    }
    currentAssistantBubble.textContent += payload.content;
    chatLog.scrollTop = chatLog.scrollHeight;
    return;
  }

  if (payload.type === "stream_end") {
    currentAssistantBubble = null;
    return;
  }

  if (payload.type === "heartbeat" || payload.type === "reminder") {
    addBubble("meta", payload.content);
    maybeNotify(payload.content);
    return;
  }

  if (payload.type === "video_status") {
    addBubble("meta", payload.content);
    return;
  }

  if (payload.type === "video_error") {
    addBubble("meta", payload.content);
    return;
  }

  if (payload.type === "video_result") {
    addVideoBubble(payload.metadata.videoUrl, payload.content || "视频生成完成");
    return;
  }

  if (payload.metadata && payload.metadata._streamed) {
    return;
  }

  addBubble("assistant", payload.content || "");
}

async function sendMessage(message) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      message,
    }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "发送失败" }));
    throw new Error(payload.detail || "发送失败");
  }
}

async function generateVideo(prompt) {
  const klingConfig = getStoredKlingConfig();
  const response = await fetch("/api/video/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      prompt,
      kling_access_key: klingConfig.accessKey || undefined,
      kling_secret_key: klingConfig.secretKey || undefined,
    }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "视频生成失败" }));
    throw new Error(payload.detail || "视频生成失败");
  }
}

async function maybeEnableNotifications() {
  if (!("Notification" in window)) {
    addBubble("meta", "当前浏览器不支持桌面提醒。");
    return;
  }
  const permission = await Notification.requestPermission();
  if (permission === "granted") {
    addBubble("meta", "桌面提醒已开启。之后定时提醒到了会直接通知你。");
  } else {
    addBubble("meta", "你暂时没有开启浏览器提醒，不过页面里仍然会收到提醒消息。");
  }
}

function maybeNotify(content) {
  if ("Notification" in window && Notification.permission === "granted") {
    new Notification("NanoKwali 提醒", { body: content });
  }
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) {
    return;
  }

  addBubble("user", message);
  messageInput.value = "";
  currentAssistantBubble = null;
  sendButton.disabled = true;

  try {
    await sendMessage(message);
  } catch (error) {
    addBubble("meta", error.message || "发送失败，请稍后再试。");
  } finally {
    sendButton.disabled = false;
    messageInput.focus();
  }
});

notifyButton.addEventListener("click", maybeEnableNotifications);

videoConfigButton.addEventListener("click", () => {
  toggleVideoConfigPanel();
});

saveVideoConfigButton.addEventListener("click", () => {
  const accessKey = klingAccessKeyInput.value.trim();
  const secretKey = klingSecretKeyInput.value.trim();
  if (!accessKey || !secretKey) {
    setVideoConfigStatus("请同时填写 Kling Access Key 和 Secret Key。");
    return;
  }
  localStorage.setItem(KLING_ACCESS_KEY_STORAGE, accessKey);
  localStorage.setItem(KLING_SECRET_KEY_STORAGE, secretKey);
  refreshVideoConfigUI();
  addBubble("meta", "Kling 视频配置已保存到当前浏览器。之后点“生成视频”会自动使用它。");
});

clearVideoConfigButton.addEventListener("click", () => {
  localStorage.removeItem(KLING_ACCESS_KEY_STORAGE);
  localStorage.removeItem(KLING_SECRET_KEY_STORAGE);
  refreshVideoConfigUI();
  addBubble("meta", "已清空当前浏览器中的 Kling 视频配置。");
});

videoButton.addEventListener("click", async () => {
  const prompt = messageInput.value.trim();
  if (!prompt) {
    addBubble("meta", "先输入你想生成的视频描述，再点击“生成视频”。");
    return;
  }
  const klingConfig = getStoredKlingConfig();
  const hasBrowserConfig = Boolean(klingConfig.accessKey && klingConfig.secretKey);
  const hasServerConfig = Boolean(appStatus && appStatus.videoConfig && appStatus.videoConfig.serverKlingConfigured);
  if (!hasBrowserConfig && !hasServerConfig) {
    toggleVideoConfigPanel(true);
    addBubble("meta", "先点上方“视频设置”填入你的 Kling AK/SK。只需要在当前浏览器保存一次。");
    return;
  }

  addBubble("user", `请根据这个描述直接生成视频：${prompt}`);
  videoButton.disabled = true;
  sendButton.disabled = true;

  try {
    await generateVideo(prompt);
  } catch (error) {
    addBubble("meta", error.message || "视频生成失败，请稍后再试。");
  } finally {
    videoButton.disabled = false;
    sendButton.disabled = false;
    messageInput.focus();
  }
});

async function boot() {
  addIntro();
  const status = await fetch("/api/status").then((res) => res.json()).catch(() => null);
  appStatus = status;
  if (status && !status.ok && status.startupError) {
    addBubble("meta", `当前服务还没完全就绪: ${status.startupError}`);
    addBubble("meta", "先把 runtime/nanobot-config.json 配好，再刷新页面即可开始对话。");
  }
  refreshVideoConfigUI();
  await ensureSession();
  startEventStream();
}

boot();

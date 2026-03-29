# NanoKwali

基于 [HKUDS/nanobot](https://github.com/HKUDS/nanobot) 做的“一键成片”专属网页 Agent。

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/bboyabssiszai/NanoKwali)

这一版已经包含：

- 居中网页聊天界面
- `nanobot` 作为底层 agent 引擎
- 浏览器内实时流式回复
- 通过 `nanobot` 的 `cron` / `heartbeat` 回流网页提醒

## 目录结构

```text
.
├── app/                     # FastAPI 后端
├── web/                     # 中央聊天界面
├── runtime/                 # 运行时配置和 workspace
├── nanobot/                 # 上游 nanobot 源码
└── requirements.txt
```

## 运行方式

### 1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置 nanobot

先复制示例配置：

```bash
cp runtime/nanobot-config.example.json runtime/nanobot-config.json
```

然后配置环境变量，不把 API Key 写进 `json`：

```bash
cp .env.example .env
```

把 `.env` 里的 `MOONSHOT_API_KEY` 改成你自己的 key。

`runtime/nanobot-config.json` 里至少确认这些字段：

- 模型名
- provider

当前默认已经切到 `moonshot + kimi-k2.5`。

如果你要启用 Kling 直连视频生成，再补两项环境变量：

- `KLING_ACCESS_KEY`
- `KLING_SECRET_KEY`

### 3. 启动网页 Agent

```bash
uvicorn app.server:app --reload
```

启动后打开：

```text
http://127.0.0.1:8000
```

## 提醒能力

网页中的聊天实际使用的是 `web` 这个虚拟 channel。

这意味着你可以直接对它说：

- `今晚 8 点提醒我开始剪第一版`
- `每天下午 3 点提醒我检查视频发布数据`

如果浏览器已允许通知，提醒会同时以桌面通知形式出现。

## 视频生成

项目已经支持通过 Kling API 直接生成视频。

需要环境变量：

- `KLING_ACCESS_KEY`
- `KLING_SECRET_KEY`

前端会提供“生成视频”按钮。提交后，后端会异步创建 Kling 文生视频任务，并在生成完成后把视频直接展示在聊天区。

## 部署

### Zeabur

如果你在 Render 上受限于信用卡，优先推荐 Zeabur。

这个项目已经带有 [Dockerfile](/Users/kwaibear/Documents/NanoKwali/Dockerfile:1)，Zeabur 可以直接识别并用 Docker 部署。

部署建议：

1. 在 Zeabur 中导入 GitHub 仓库 `bboyabssiszai/NanoKwali`
2. 让 Zeabur 自动识别 `Dockerfile`
3. 设置环境变量：
   `MOONSHOT_API_KEY`
4. 在服务里挂载持久化 Volume，并把挂载目录设为：
   `/data/nanokwali`
5. 再增加环境变量：
   `NANOKWALI_RUNTIME_DIR=/data/nanokwali`

这样这些内容会被持久化保存：

- 会话历史
- cron 提醒任务
- heartbeat 文件
- 你的 agent 人格模板副本

Zeabur 相关官方资料：

- Dockerfile 部署: https://zeabur.com/docs/en-US/deploy/dockerfile
- 持久化 Volumes: https://zeabur.com/docs/en-US/data-management/volumes
- 公网访问: https://zeabur.com/docs/en-US/networking/public
- 定价/试用: https://zeabur.cn/zh-CN/pricing
- 方案与支付方式: https://zeabur.com/docs/zh-CN/billing/plans

我之所以优先推荐它，是因为 Zeabur 当前文档明确写了：

- 免费试用方案可用，且“无需绑定信用卡”
- 团队方案支持“信用卡和支付宝付款”

### Sealos

如果你更想走国内云原生平台，也可以考虑 Sealos。

它的文档明确支持：

- 公网 URL
- 自定义域名
- 持久化存储

参考：

- App Launchpad: https://sjrkwxeygluy.bja.sealos.run/en/docs/5.0.0/user-guide/app-launchpad/
- 平台介绍: https://sealos.run/docs/overview/intro

这条路线也能跑你的项目，但相对 Zeabur，第一次上手会更偏“云平台操作”一些。

### Render

这个项目已经带好了：

- [Dockerfile](/Users/kwaibear/Documents/NanoKwali/Dockerfile)
- [render.yaml](/Users/kwaibear/Documents/NanoKwali/render.yaml)
- 可持久化运行目录环境变量 `NANOKWALI_RUNTIME_DIR`

推荐直接部署到 Render Web Service，并挂载持久化磁盘。

部署时需要至少设置：

- `MOONSHOT_API_KEY`

`render.yaml` 已经默认把持久化目录指向 `/var/data/nanokwali`，这样这些内容会保留下来：

- 会话历史
- cron 提醒任务
- heartbeat 相关文件
- 你的 agent 人格模板副本

首次启动时，应用会自动把默认配置和短视频 agent 模板写入持久化目录。

### 本地 Docker

也可以先在本地试：

```bash
docker build -t nanokwali .
docker run --rm -p 8000:10000 \
  -e MOONSHOT_API_KEY=你的key \
  -e NANOKWALI_RUNTIME_DIR=/app/runtime \
  nanokwali
```

## 下一步建议

这一版先把基础交互和提醒链路打通了。后面很适合继续补：

- 专属 system prompt，收敛成“短视频导演 / 编导 / 剪辑统筹”人格
- 上传素材、脚本、分镜的多模态入口
- 一键生成拍摄清单、字幕文案、封面标题
- 对接微信/飞书，把网页提醒同步到外部渠道

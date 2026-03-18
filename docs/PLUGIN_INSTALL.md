# 插件安装说明

这个仓库只包含 MoviePilot 插件本体，不包含 Gateway 镜像。

使用顺序建议：

1. 先启动 Gateway
2. 再安装插件
3. 最后在插件里填写 Webhook 地址

---

## 第一步：先启动 Gateway

推荐配套镜像：

```text
liuyuexi/moviepilot-ai-recognizer-gateway:2.0.0-alpha.1
```

### 方案 1：direct_llm

适合：

- 直接接千问 / OpenAI 兼容接口
- 不想单独部署 OpenClaw

直接使用：

- [docker-compose.direct-llm.yml](https://github.com/liuyuexi1987/moviepilot-ai-recognizer-gateway/blob/main/docker-compose.direct-llm.yml)

启动命令：

```bash
docker compose -f docker-compose.direct-llm.yml up -d
```

### 方案 2：OpenClaw / external_recognizer

适合：

- 你已经有 OpenClaw
- 或你有自己的外部识别端

直接使用：

- [docker-compose.openclaw.yml](https://github.com/liuyuexi1987/moviepilot-ai-recognizer-gateway/blob/main/docker-compose.openclaw.yml)

启动命令：

```bash
docker compose -f docker-compose.openclaw.yml up -d
```

---

## 第二步：安装插件

支持两种方式：

- MoviePilot 自定义插件仓库安装
- 本地 ZIP 安装

### 方式 1：插件仓库安装

将本仓库添加到 MoviePilot 自定义插件仓库后安装。

### 方式 2：本地 ZIP 安装

到仓库 Releases 页面下载 ZIP：

- [Releases 页面](https://github.com/liuyuexi1987/MoviePilot-Plugins/releases)

然后在 MoviePilot 里本地上传安装。

---

## 第三步：填写插件 Webhook 地址

Gateway 启动后，在插件中一般填写：

### 方案 A（推荐）

同一 Docker 网络内，填写容器名：

```text
http://moviepilot-ai-recognizer-gateway:9000/webhook
```

### 方案 B

没有自定义 Docker 网络名时，填写宿主机内网地址：

```text
http://192.168.x.x:9000/webhook
```

不推荐：

```text
http://127.0.0.1:9000/webhook
```

---

## 插件设置建议

- 保持 MoviePilot 原生识别优先
- 默认使用 `standard`
- 网盘拼音、漏词、规避命名较多时再切 `enhanced`

---

## 补充说明

- 本仓库只包含插件，不包含 Gateway 镜像
- Gateway 默认推荐 `direct_llm`
- 如果你已经有 OpenClaw，可以改用 `external_recognizer`
- 默认推荐 MoviePilot 与 Gateway 同机部署
- 不建议把跨主机 / 跨 NAS 作为默认方案

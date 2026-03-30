# MoviePilot-Plugins

这个仓库现在主要放两个 MoviePilot 插件，给新手直接这么理解就行：

## 1. AI 识别增强插件

插件名：

- `AIRecoginzerForwarder`

作用很简单：

- MoviePilot 原生 TMDB 识别失败
- 插件把标题和文件信息转发给 Gateway
- Gateway 识别完成后异步回调
- 插件继续触发二次整理

适合：

- PT / 网盘资源名字很乱
- 原生识别经常失败
- 想在 MoviePilot 原生识别后面再补一层 AI 识别

## 2. 飞书命令桥接插件

插件名：

- `FeishuCommandBridgeLong`

作用很简单：

- 用飞书长连接接收消息
- 直接在飞书里发命令
- 桥接到 MoviePilot 和 115 整理 / STRM 流程

适合：

- 想在飞书里直接操作 MoviePilot
- 想发 `刮削`、`生成STRM`、`全量STRM`、`版本`
- 不想折腾公网 webhook 和 HTTPS 回调地址

---

下面这一大段主要是 **AI 识别增强插件** 的说明。

配套网关仓库：

- [moviepilot-ai-recognizer-gateway](https://github.com/liuyuexi1987/moviepilot-ai-recognizer-gateway)

配套 DockerHub 镜像：

```text
liuyuexi/moviepilot-ai-recognizer-gateway:2.0.0-alpha.2
```

---

## 和官方插件的区别

MoviePilot 官方已经有“直接填 OpenAI / 千问兼容接口”的插件，适合轻量用户直接做 AI 辅助识别。

这个项目的重点不在于替代那个轻量玩法，而在于：

- 原生失败后再走一条补救链路
- Gateway 做 TMDB 二次复核
- 识别完成后异步回调
- 插件继续触发二次整理
- 兼容 OpenClaw / 外部识别端

简单理解：

- 官方插件更偏“轻量 AI 辅助识别”
- 这个项目更偏“识别失败后的增强闭环”

---

## Docker 部署

插件本体不跑 Docker，但推荐你先把 Gateway 用 Docker 跑起来。

### 方案 1：direct_llm

适合：

- 直接接千问 / OpenAI 兼容接口
- 不想单独部署 OpenClaw

`docker-compose.direct-llm.yml`

```yaml
services:
  moviepilot-ai-recognizer-gateway:
    image: liuyuexi/moviepilot-ai-recognizer-gateway:2.0.0-alpha.2
    container_name: moviepilot-ai-recognizer-gateway
    environment:
      PORT: "9000"
      MP_BASE_URL: "http://192.168.x.x:3000" # 小白推荐直接写 MoviePilot 的宿主机内网地址和外部端口；熟悉 Docker 网络后也可改成 http://moviepilot-v2:3001；不要写 127.0.0.1
      MP_API_KEY: "replace_with_moviepilot_api_key" # 改成你的 MoviePilot API Key
      RECOGNIZER_MODE: "direct_llm"
      LLM_BASE_URL: "https://dashscope.aliyuncs.com/compatible-mode/v1" # 改成你的 OpenAI 兼容接口根路径
      LLM_API_KEY: "replace_with_llm_api_key" # 改成你的大模型 API Key
      LLM_MODEL: "qwen-plus" # 推荐先用 qwen-plus
      LLM_TEMPERATURE: "0.1" # 温度越低越保守，越容易稳定输出 JSON；不懂就保持 0.1
      LLM_ENABLE_THINKING: "false" # 推荐保持 false，稳定输出 JSON
      TMDB_API_KEY: "replace_with_tmdb_api_key" # 改成你的 TMDB API Key
      RECOGNIZER_TIMEOUT_MS: "60000"
    ports:
      - "9000:9000"
    restart: unless-stopped
    networks:
      - moviepilot

networks:
  moviepilot:
    external: true
    name: moviepilot
```

启动命令：

```bash
docker compose -f docker-compose.direct-llm.yml up -d
```

### 方案 2：OpenClaw / external_recognizer

适合：

- 你已经有 OpenClaw
- 或你有自己的外部识别端

`docker-compose.openclaw.yml`

```yaml
services:
  moviepilot-ai-recognizer-gateway:
    image: liuyuexi/moviepilot-ai-recognizer-gateway:2.0.0-alpha.2
    container_name: moviepilot-ai-recognizer-gateway
    environment:
      PORT: "9000"
      MP_BASE_URL: "http://192.168.x.x:3000" # 小白推荐直接写 MoviePilot 的宿主机内网地址和外部端口；熟悉 Docker 网络后也可改成 http://moviepilot-v2:3001；不要写 127.0.0.1
      MP_API_KEY: "replace_with_moviepilot_api_key" # 改成你的 MoviePilot API Key
      RECOGNIZER_MODE: "external_recognizer"
      OPENCLAW_RECOGNIZE_URL: "http://192.168.x.x:19000/recognize" # 这里不是固定可用地址，必须改成你自己已经部署好并能访问的 OpenClaw / 外部识别端 HTTP 接口
      TMDB_API_KEY: "replace_with_tmdb_api_key" # 推荐保留，用于最终 TMDB 复核
      RECOGNIZER_TIMEOUT_MS: "60000"
    ports:
      - "9000:9000"
    restart: unless-stopped
    networks:
      - moviepilot

networks:
  moviepilot:
    external: true
    name: moviepilot
```

启动命令：

```bash
docker compose -f docker-compose.openclaw.yml up -d
```

两种方案启动后，在插件里一般都填写：

```text
http://192.168.x.x:9000/webhook
```

如果你熟悉 Docker 网络，并且 MoviePilot 与 Gateway 在同一网络中，也可以填：

```text
http://moviepilot-ai-recognizer-gateway:9000/webhook
```

补充说明：

- 方案 A：同一 Docker 网络，写容器名，例如 `http://moviepilot-v2:3001`
- 方案 B（小白推荐）：直接改成 MoviePilot 宿主机内网地址，例如 `http://192.168.x.x:3000`
- 不建议写 `http://127.0.0.1:3001`

如果你想接 OpenClaw，也可以这样改：

```yaml
RECOGNIZER_MODE: "external_recognizer"
OPENCLAW_RECOGNIZE_URL: "http://你的-openclaw-识别端/recognize"
```

注意：

- OpenClaw 不是必须
- 不是把这行地址原样抄进去就能用
- 你必须先自己部署好 OpenClaw 或其他外部识别端，并确认这个 HTTP 地址真的能返回识别 JSON
- 如果你没有现成的 OpenClaw，直接走 `direct_llm` 更省事

---

## 插件安装

支持两种方式：

- MoviePilot 自定义插件仓库安装
- 本地 ZIP 安装

当前 Release 附件中的 ZIP 可直接用于本地安装。

仓库根目录也已补齐 MoviePilot 自定义仓库常用结构：

- `package.json`
- `package.v2.json`
- `plugins/airecoginzerforwarder`
- `plugins.v2/airecoginzerforwarder`

---

## 插件设置建议

- 保持 MoviePilot 原生识别优先
- 默认使用 `standard`
- 网盘拼音、漏词、规避命名较多时再切 `enhanced`
- 默认推荐 MoviePilot 与 Gateway 同机部署

---

## 说明

- 本仓库只包含插件，不包含 Gateway 镜像
- Gateway 默认推荐 `direct_llm`
- 不建议把跨主机 / 跨 NAS 作为默认方案

---

## 文档

- [插件安装说明](./docs/PLUGIN_INSTALL.md)
- [插件 ZIP 打包说明](./docs/PACKAGING.md)
- [GitHub 发布说明](./docs/GITHUB_PUBLISH.md)
- [v2.0.0-alpha.1 发布文案](./docs/RELEASE_v2.0.0-alpha.1.md)
- [网关 direct_llm compose](https://github.com/liuyuexi1987/moviepilot-ai-recognizer-gateway/blob/main/docker-compose.direct-llm.yml)
- [网关 OpenClaw compose](https://github.com/liuyuexi1987/moviepilot-ai-recognizer-gateway/blob/main/docker-compose.openclaw.yml)
- [Releases 页面](https://github.com/liuyuexi1987/MoviePilot-Plugins/releases)

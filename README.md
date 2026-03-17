# moviepilot-ai-recognizer-plugin

一个给 MoviePilot 用的 AI 识别转发插件。

作用很简单：

- MoviePilot 原生 TMDB 识别失败
- 插件把标题和文件信息转发给 Gateway
- Gateway 识别完成后异步回调
- 插件继续触发二次整理

配套网关仓库：

- [moviepilot-ai-recognizer-gateway](https://github.com/liuyuexi1987/moviepilot-ai-recognizer-gateway)

配套 DockerHub 镜像：

```text
liuyuexi/moviepilot-ai-recognizer-gateway:2.0.0-alpha.1
```

---

## Docker 部署

插件本体不跑 Docker，但推荐你先把 Gateway 用 Docker 跑起来。

最常用的 `docker compose` 示例：

```yaml
services:
  moviepilot-ai-recognizer-gateway:
    image: liuyuexi/moviepilot-ai-recognizer-gateway:2.0.0-alpha.1
    container_name: moviepilot-ai-recognizer-gateway
    environment:
      PORT: "9000"
      MP_BASE_URL: "http://moviepilot-v2:3001" # 方案A：同一 Docker 网络写容器名；方案B：改成宿主机内网地址；不要写 127.0.0.1
      MP_API_KEY: "replace_with_moviepilot_api_key" # 改成你的 MoviePilot API Key
      RECOGNIZER_MODE: "direct_llm"
      LLM_BASE_URL: "https://dashscope.aliyuncs.com/compatible-mode/v1" # 改成你的 OpenAI 兼容接口根路径
      LLM_API_KEY: "replace_with_llm_api_key" # 改成你的大模型 API Key
      LLM_MODEL: "qwen-plus"
      LLM_TEMPERATURE: "0.1"
      LLM_ENABLE_THINKING: "false"
      TMDB_API_KEY: "replace_with_tmdb_api_key" # 改成你的 TMDB API Key
      OPENCLAW_RECOGNIZE_URL: "http://openclaw-recognizer:19000/recognize" # 仅 external_recognizer 模式使用
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
docker compose up -d
```

Gateway 启动后，在插件里一般填写：

```text
http://moviepilot-ai-recognizer-gateway:9000/webhook
```

如果你没有自定义 Docker 网络名，也可以直接填宿主机内网地址：

```text
http://192.168.x.x:9000/webhook
```

补充说明：

- 方案 A：同一 Docker 网络，优先写容器名，例如 `http://moviepilot-v2:3001`
- 方案 B：没有自定义网络名时，直接改成 MoviePilot 宿主机内网地址
- 不建议写 `http://127.0.0.1:3001`

---

## 插件安装

支持两种方式：

- MoviePilot 自定义插件仓库安装
- 本地 ZIP 安装

当前 Release 附件中的 ZIP 可直接用于本地安装。

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
- [Releases 页面](https://github.com/liuyuexi1987/moviepilot-ai-recognizer-plugin/releases)

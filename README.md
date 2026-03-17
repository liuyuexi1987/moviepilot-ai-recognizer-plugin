# moviepilot-ai-recognizer-plugin

一个面向 `v2.0` 架构的 MoviePilot AI 识别转发插件。

这个仓库只负责 **MoviePilot 插件本体**，运行时网关与 AI 后端分离：

- 插件仓库：负责事件接管、异步回调、二次整理
- Gateway 仓库：负责识别请求、TMDB 复核、回调插件

这样更适合：

- 插件和镜像分开发布
- NAS 用户分别升级插件与网关
- 同时兼容 `direct_llm` 和 `external_recognizer`
- 同时兼容 MoviePilot 仓库安装与本地 ZIP 安装

## 当前定位

当前版本：

- `v2.0.0-alpha.1`

核心定位：

- MoviePilot 原生识别失败后的 AI 补救插件
- 默认推荐“原生优先，AI 兜底”
- 异步回调后自动触发二次整理

## 典型部署方式

### 同机 Docker

如果 MoviePilot 和 Gateway 在同一台 Docker 主机，并处于同一网络，插件中一般填写：

```text
http://moviepilot-ai-recognizer-gateway:9000/webhook
```

### 跨主机 / 跨 NAS

如果 Gateway 在另一台机器上，插件中填写对端可访问地址，例如：

```text
http://<host-ip>:9000/webhook
```

但不建议把这类跨主机方式作为默认部署方案。

原因是：

- 容器网络、宿主机地址、端口映射更容易混淆
- 超时和回调链路更难排查
- 不同 NAS / Docker 环境下网络策略差异更大

更推荐：

- MoviePilot 和 Gateway 在同一台 Docker 主机
- 或至少在同一 Docker 网络中互通

## 识别增强模式

插件内置两种模式：

- `standard`
  - 推荐默认使用
  - 更适合 PT 规范命名
  - 更稳，误匹配风险更低

- `enhanced`
  - 更适合网盘拼音、漏词、规避版权命名
  - 召回率更高，但误命中风险略高

## 这个仓库不包含什么

本仓库 **不包含**：

- AI Gateway 镜像
- OpenClaw 本体
- 大模型 API 服务

这些由网关仓库或用户自建环境负责。

## 插件目录结构

为了兼容 MoviePilot 本地 ZIP 安装与插件仓库安装，插件目录内保留完整安装文件：

- `AIRecoginzerForwarder/__init__.py`
- `AIRecoginzerForwarder/README.md`
- `AIRecoginzerForwarder/requirements.txt`

其中：

- 仓库根目录 `README.md` 用于 GitHub 首页说明
- 插件目录内 `README.md` 用于插件包说明

另外，仓库根目录还提供官方插件仓库所需结构：

- `package.v2.json`
- `plugins.v2/airecoginzerforwarder/__init__.py`

## 文档入口

- [插件安装说明](/Volumes/acasis/Downloads/moviepilot-openclaw-forwarder-v2/plugin-repo/docs/PLUGIN_INSTALL.md)
- [插件 ZIP 打包说明](/Volumes/acasis/Downloads/moviepilot-openclaw-forwarder-v2/plugin-repo/docs/PACKAGING.md)
- [GitHub 发布说明](/Volumes/acasis/Downloads/moviepilot-openclaw-forwarder-v2/plugin-repo/docs/GITHUB_PUBLISH.md)
- [v2.0.0-alpha.1 发布文案](/Volumes/acasis/Downloads/moviepilot-openclaw-forwarder-v2/plugin-repo/docs/RELEASE_v2.0.0-alpha.1.md)
- [首发时要上传的 ZIP](/Volumes/acasis/Downloads/moviepilot-openclaw-forwarder-v2/plugin-repo/dist/AIRecoginzerForwarder-v2.0.0-alpha.1.zip)

## 本地打包

如果需要生成可上传到 MoviePilot 的本地安装 ZIP：

```bash
bash scripts/sync-repo-layout.sh
bash scripts/package-plugin.sh
```

## 后续方向

- 与 `moviepilot-ai-recognizer-gateway` 配套发布
- 收敛插件设置说明
- 继续验证 `v2.0` 双仓库发布体验

# 插件安装说明

## 适用范围

这个仓库只包含 MoviePilot 插件本体，不包含 Gateway 镜像。

在使用前，请先准备：

- 已安装 MoviePilot
- 已部署 `moviepilot-ai-recognizer-gateway`
- 已确认 Gateway 地址可从 MoviePilot 访问

推荐直接使用 DockerHub 镜像：

- [liuyuexi/moviepilot-ai-recognizer-gateway](https://hub.docker.com/repository/docker/liuyuexi/moviepilot-ai-recognizer-gateway)

推荐 tag：

```text
liuyuexi/moviepilot-ai-recognizer-gateway:2.0.0-alpha.1
```

拉取命令：

```bash
docker pull liuyuexi/moviepilot-ai-recognizer-gateway:2.0.0-alpha.1
```

## 安装方式

将目录：

```text
AIRecoginzerForwarder
```

放入 MoviePilot 的插件目录中，然后重启 MoviePilot。

## 仓库安装兼容

为了兼容 MoviePilot 自定义插件仓库安装，本仓库同时保留：

```text
package.v2.json
plugins.v2/airecoginzerforwarder/__init__.py
```

其中：

- `AIRecoginzerForwarder/` 用于本地 ZIP 安装
- `plugins.v2/airecoginzerforwarder/` 用于 MP 仓库识别结构

## 核心配置

在插件设置中重点填写：

- `AI Gateway Webhook 地址`
- `AI Gateway Webhook Headers（JSON）`
- `AI Gateway Webhook 超时（秒）`
- `识别增强模式`

## Webhook 地址示例

### 同机 Docker

```text
http://moviepilot-ai-recognizer-gateway:9000/webhook
```

### 跨主机

```text
http://<host-ip>:9000/webhook
```

## 关于跨主机 / 跨 NAS

跨主机方案不是不能做，但不建议作为默认推荐方案。

在我们实际开发和联调过程中，跨主机场景更容易遇到这些问题：

- 容器内 `127.0.0.1` 与宿主机 `127.0.0.1` 语义不同
- 容器名只在同一 Docker 网络内可解析，跨主机不可直接使用
- 回调链路涉及双向可达，超时更难定位
- NAS 厂商对 Docker 网络、桥接、端口暴露的细节差异较大

因此更推荐：

- MoviePilot 与 Gateway 同机部署
- 同一 Docker 网络内通过容器名互通

只有在确有必要时，再考虑跨主机部署。

## 推荐设置

- 保持 MoviePilot 原生识别优先
- 插件只在原生识别失败时兜底
- 默认使用 `standard`
- 只有在网盘拼音、漏词、规避命名较多时，再切换到 `enhanced`

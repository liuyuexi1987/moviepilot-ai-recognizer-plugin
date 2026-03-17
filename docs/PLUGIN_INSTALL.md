# 插件安装说明

## 适用范围

这个仓库只包含 MoviePilot 插件本体，不包含 Gateway 镜像。

在使用前，请先准备：

- 已安装 MoviePilot
- 已部署 `moviepilot-ai-recognizer-gateway`
- 已确认 Gateway 地址可从 MoviePilot 访问

## 安装方式

将目录：

```text
AIRecoginzerForwarder
```

放入 MoviePilot 的插件目录中，然后重启 MoviePilot。

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

## 推荐设置

- 保持 MoviePilot 原生识别优先
- 插件只在原生识别失败时兜底
- 默认使用 `standard`
- 只有在网盘拼音、漏词、规避命名较多时，再切换到 `enhanced`

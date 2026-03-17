# v2.0.0-alpha.1 发布文案

## Tag

```text
v2.0.0-alpha.1
```

## Title

```text
v2.0.0-alpha.1 首个拆分仓库版本
```

## Release Notes

```md
## v2.0.0-alpha.1 首个拆分仓库版本

这是 `moviepilot-ai-recognizer-plugin` 的首个 `v2.0` alpha 版本。

本版本的目标，是将 MoviePilot 插件本体从运行时网关中拆分出来，形成更适合 GitHub 和 NAS 用户使用的双仓库发布结构。

## 本版本包含

- 独立插件仓库结构
- AI Gateway 对接配置
- 异步回调处理
- 二次整理触发逻辑
- `standard` / `enhanced` 识别增强模式

## 当前定位

- 插件仓库只负责 MoviePilot 插件本体
- Gateway 运行时由独立镜像仓库提供
- 默认与 `moviepilot-ai-recognizer-gateway` 配套使用

## 适用场景

- MoviePilot 原生识别失败补救
- PT 资源标准命名识别
- 网盘拼音、漏词、规避命名识别
- 本地文件与云盘挂载回调后二次整理
```

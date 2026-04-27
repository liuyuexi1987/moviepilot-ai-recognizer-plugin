# v2.0.0-alpha.1 历史发布文案

> 这是旧 AI Gateway 拆分阶段的历史发布草稿，仅保留作归档参考。
> 当前仓库已经演进为多插件套件，发布前请以 `docs/GITHUB_PUBLISH.md` 和 `scripts/pre-release-check.sh` 为准。

## GitHub Release 页面填写

### Tag version

```text
v2.0.0-alpha.1
```

### Release title

```text
v2.0.0-alpha.1 首个拆分仓库版本
```

### 是否勾选 Pre-release

建议：

- 勾选

因为当前版本仍属于 `alpha` 阶段。

### 是否勾选 latest

建议：

- 不要手动强调为稳定版

## 建议上传的附件

建议在 GitHub Release 页面上传这个 ZIP：

```text
dist/AIRecoginzerForwarder-v2.0.0-alpha.1.zip
```

这个 ZIP 已经是可用于 MoviePilot 本地安装的插件包。

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

这是 `MoviePilot-Plugins` 仓库的首个 `v2.0` alpha 版本。

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

## 首发建议

- Release 页面上传插件 ZIP
- 仓库安装与本地 ZIP 安装都保留
- 插件默认推荐与 `moviepilot-ai-recognizer-gateway` 配套使用
- 默认更推荐同机 Docker / 同网络部署，不建议默认走跨主机方案
```

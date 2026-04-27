# 插件 ZIP 打包说明

## 目标

用于生成可在 MoviePilot 本地上传安装的插件 ZIP 包。

打包内容会保留以下标准结构：

```text
<PluginName>/
  __init__.py
  README.md
  requirements.txt
```

## 一键打包

在仓库根目录执行：

```bash
bash scripts/package-plugin.sh
bash scripts/package-plugin.sh --help
```

默认打包 `AIRecoginzerForwarder`。

查看当前可打包插件：

```bash
bash scripts/package-plugin.sh --list
```

只打包全部插件、不运行完整发布检查：

```bash
bash scripts/package-plugin.sh --all
```

`--all` 和 `pre-release-check.sh` 会在打包前清理 `dist/*.zip`，避免旧版本 ZIP 混在发布附件里。

如需打包其他插件，例如 `AgentResourceOfficer` 或飞书桥接插件：

```bash
bash scripts/package-plugin.sh AgentResourceOfficer
bash scripts/package-plugin.sh FeishuCommandBridgeLong
```

脚本会自动先同步一次官方仓库布局，再生成 ZIP。

同步脚本会根据 `package.json` 自动发现根目录中带 `__init__.py` 的源码插件，并同步到 `plugins/` 和 `plugins.v2/`。

插件名会优先按 `package.json` 做大小写不敏感匹配。例如 `hdhiveopenapi` 会被规范为 `HdhiveOpenApi`，生成的 ZIP 根目录也会保持标准插件 ID。

如果插件代码目录来自 `plugins/` 或 `plugins.v2/`，但说明文档保留在仓库顶层同名目录下，打包脚本会自动把顶层 `README.md` 补进 ZIP。

发布前完整检查会一次打包当前仓库清单里的可本地安装插件：

```bash
bash scripts/pre-release-check.sh
```

当前完整检查覆盖：

- `AIRecoginzerForwarder`
- `AIRecognizerEnhancer`
- `AgentResourceOfficer`
- `FeishuCommandBridgeLong`
- `HdhiveOpenApi`
- `HDHiveDailySign`
- `QuarkShareSaver`
- `ZspaceMediaFreshMix`

完整检查还会校验：

- 插件代码和仓库内 Skill helper 脚本必须能通过 Python 语法检查
- `AgentResourceOfficer` 和 `hdhive-search-unlock-to-115` Skill helper 的本地 `selftest` 必须通过
- `AgentResourceOfficer` Skill 安装脚本的 `--dry-run` 必须通过
- 发布脚本中的插件清单必须和 `package.json` 一致
- `package-plugin.sh --list` 输出必须和发布插件清单一致
- `package.json` 插件市场展示字段和图标文件必须存在
- `package.json` 中每个插件必须标记 `v2: true`
- `package.json` 中每个插件都必须能在根目录、`plugins/` 或 `plugins.v2/` 找到 `__init__.py`
- `docs/PLUGIN_INSTALL.md` 必须列出当前版本对应的 ZIP 文件名
- 每个 ZIP 必须包含 `<PluginName>/__init__.py`
- 每个 ZIP 必须包含 `<PluginName>/README.md`
- ZIP 中不能包含 `__pycache__`、`.pyc`、`.pyo`、`.DS_Store`

## 输出位置

打包结果输出到：

```text
dist/
```

文件名格式：

```text
<PluginName>-<plugin_version>.zip
```

例如：

```text
AgentResourceOfficer-0.1.107.zip
```

## 使用方式

1. 打开 MoviePilot
2. 进入 设置 -> 插件
3. 选择本地安装插件
4. 上传 `dist/` 下生成的 ZIP 文件

## 注意事项

- `plugin_version` 取自目标插件目录下的 `__init__.py`
- 如果改了版本号，重新运行脚本即可生成对应文件名
- `dist/` 目录默认不纳入 Git 版本管理
- 提交前建议以 `bash scripts/pre-release-check.sh` 作为最终验收

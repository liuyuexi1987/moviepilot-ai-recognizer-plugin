# 插件和 Skill ZIP 打包说明

开始打包或发布前，先执行一次仓库卫生检查：

```bash
bash scripts/repo-hygiene.sh
```

如果只想快速查维护/发布命令，不想先读完整文档，直接看：

- `docs/MAINTENANCE_COMMANDS.md`

如果要直接跑完整发版前检查，执行：

```bash
bash scripts/release-preflight.sh
```

## 目标

用于生成可在 MoviePilot 本地上传安装的插件 ZIP 包，以及可复制到外部智能体环境的公开 Skill ZIP 包。

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

默认打包 `AIRecognizerEnhancer`。

查看当前可打包插件：

```bash
bash scripts/package-plugin.sh --list
```

只打包全部插件、不运行完整发布检查：

```bash
bash scripts/package-plugin.sh --all
```

`--all` 和 `pre-release-check.sh` 会在打包前清理 `dist/*.zip`、`SHA256SUMS.txt` 和 `MANIFEST.json`；完整发布检查还会清理并重建 `dist/skills/`，避免旧版本产物混在发布附件里。

`--all` 会在打包后自动生成 `SHA256SUMS.txt`、`MANIFEST.json` 并执行 `scripts/verify-dist.sh`。

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

如果改了 `package.json`，可以先同步派生清单：

```bash
bash scripts/sync-package-v2.sh
```

`pre-release-check.sh` 也会自动运行这个同步脚本；如果 `package.v2.json` 因此发生变化，工作区检查会失败并提示先提交。

完整检查会在 `dist/` 下额外生成 `SHA256SUMS.txt` 和 `MANIFEST.json`，用于核对每个 ZIP 的 SHA256，并给自动化脚本读取插件 ID、展示名、版本、文件名和大小。

完整检查还会在 `dist/skills/` 下生成公开 Skill ZIP、`SHA256SUMS.txt` 和 `MANIFEST.json`：

```bash
bash scripts/package-skills.sh
bash scripts/verify-skill-dist.sh
```

如需只刷新当前 `dist/*.zip` 的校验清单和机器可读 manifest：

```bash
bash scripts/write-dist-sha256.sh
```

如果只想校验已经生成或从 `Release Preflight` artifact 下载下来的完整发布产物目录：

```bash
bash scripts/verify-release-assets.sh
bash scripts/verify-dist.sh
bash scripts/verify-skill-dist.sh
```

也可以校验其他目录：

```bash
bash scripts/verify-release-assets.sh /path/to/downloaded-artifact
DIST_DIR=/path/to/downloaded-artifact bash scripts/verify-dist.sh
DIST_DIR=/path/to/downloaded-artifact/skills bash scripts/verify-skill-dist.sh
```

如果要生成可复制到 GitHub Release 的 Markdown 表格：

```bash
bash scripts/print-release-summary.sh
```

如果本地运行测试后产生了 `__pycache__`、`.pyc` 或 `.DS_Store`，可以清理生成物：

```bash
bash scripts/clean-generated.sh
bash scripts/clean-generated.sh --dist
```

如果要下载并校验最近一次成功 `Release Preflight` artifact：

```bash
bash scripts/verify-release-preflight-artifact.sh
```

如果要创建 GitHub Draft Release，先 dry-run：

```bash
bash scripts/create-draft-release.sh <tag> --dry-run
```

也可以走 GitHub Actions 手动 dry-run：

```bash
gh workflow run draft-release.yml -f tag=<tag> -f dry_run=true
```

当前完整检查覆盖：

- `AIRecognizerEnhancer`
- `AgentResourceOfficer`
- `FeishuCommandBridgeLong`
- `HdhiveOpenApi`
- `QuarkShareSaver`

完整检查还会校验：

- 仓库内发布脚本和 Skill shell helper 必须能通过 shell 语法检查
- 插件代码和仓库内 Skill helper 脚本必须能通过 Python 语法检查
- `AgentResourceOfficer` 和 `hdhive-search-unlock-to-115` Skill helper 的本地 `selftest` 必须通过
- `AgentResourceOfficer` Skill 的 `external-agent` 入口必须能输出 `external_agent.v1`、3 个最小工具和有效 `EXTERNAL_AGENTS.md`；`workbuddy` 仅作为兼容别名保留，并已标记为 deprecated。
- `AgentResourceOfficer` 和 `hdhive-search-unlock-to-115` Skill helper 版本必须同步到 README 和 CHANGELOG
- `AgentResourceOfficer` 和 `hdhive-search-unlock-to-115` Skill 安装脚本的 `--dry-run` 必须通过
- 如果设置 `RUN_AGENT_RESOURCE_OFFICER_LIVE_SMOKE=1`，完整检查还会执行 `scripts/smoke-agent-resource-officer.py --include-search`，对本机 MoviePilot 做真实只读 smoke
- 以上 Skill 检查可以单独运行 `bash scripts/check-skills.sh`
- 发布脚本中的插件清单必须和 `package.json` 一致
- `package-plugin.sh --list` 输出必须和发布插件清单一致
- `package.json` 插件市场展示字段和图标文件必须存在
- `package.json` 中 `version`、`labels`、`level`、`history` 等字段类型必须符合预期
- `package.json` 中每个插件必须标记 `v2: true`
- `package.json` 当前版本必须出现在对应插件的 `history` 中
- `package.json` 中每个插件都必须能在根目录、`plugins/` 或 `plugins.v2/` 找到 `__init__.py`
- 仓库首页 `README.md` 必须列出 `package.json` 中每个插件的 ID、展示名和当前版本
- `docs/PLUGIN_INSTALL.md` 必须列出当前版本对应的 ZIP 文件名
- `dist/SHA256SUMS.txt` 必须随 ZIP 一起生成
- `dist/MANIFEST.json` 必须随 ZIP 一起生成
- `dist/skills/` 必须生成公开 Skill ZIP、`SHA256SUMS.txt` 和 `MANIFEST.json`
- `scripts/verify-dist.sh` 必须能验证 ZIP SHA256、MANIFEST、插件元数据、基础目录结构和不应发布的生成文件
- `scripts/verify-skill-dist.sh` 必须能验证 Skill ZIP SHA256、MANIFEST、基础目录结构、不应发布的生成文件，以及 `agent-resource-officer` ZIP 解压后的 `external-agent` 入口
- `scripts/verify-release-assets.sh` 必须能一次校验插件 ZIP 和 Skill ZIP
- `scripts/verify-release-preflight-artifact.sh` 必须能下载并校验 GitHub Actions artifact
- `scripts/print-release-summary.sh` 必须能基于 `MANIFEST.json` 输出 Release Markdown 表格
- `scripts/generate-release-notes.sh` 必须能生成统一 Release 正文，并包含 `external-agent / external-agent --full` 重点
- `.github/workflows/ci.yml` 和 `draft-release.yml` 必须使用 artifact 上传步骤，并包含插件 ZIP、Skill ZIP、`SHA256SUMS.txt`、`MANIFEST.json`
- `draft-release.yml` 必须保留手动触发、`dry_run` 输入和创建 Draft Release 所需的 `contents: write` 权限
- Markdown 文档中的本地相对链接必须存在
- 仓库文本中不能包含已知本机路径、历史密码、历史 API Key 或 Bearer JWT 片段
- 每个 ZIP 必须包含 `<PluginName>/__init__.py`
- 每个 ZIP 必须包含 `<PluginName>/README.md`
- ZIP 中不能包含 `__pycache__`、`.pyc`、`.pyo`、`.DS_Store`

## 输出位置

打包结果输出到：

```text
dist/
dist/skills/
```

文件名格式：

```text
<PluginName>-<plugin_version>.zip
```

例如：

```text
AgentResourceOfficer-<当前版本>.zip
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
- 提交前建议以 `bash scripts/release-preflight.sh` 作为最终验收

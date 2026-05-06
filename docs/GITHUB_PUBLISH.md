# GitHub 发布说明

## 推荐仓库名

```text
MoviePilot-Plugins
```

## 推荐描述

```text
Personal MoviePilot plugin suite for agent-driven resource workflows, AI recognition fallback, Feishu control, HDHive, Quark and media refresh helpers
```

## 发布建议

- 开始发版或仓库维护前，先执行一次：
  - `bash scripts/repo-hygiene.sh`
- 如果想一条命令跑完整发版前检查，优先执行：
  - `bash scripts/release-preflight.sh`
- README 首页保持中文
- GitHub 仓库描述使用简短英文
- 当前对外文档优先以 `docs/INDEX.md` 为导航；不要把历史规划文档当成当前说明
- 如果只想快速查维护/发布命令，不想先读长文，直接看：
  - `docs/MAINTENANCE_COMMANDS.md`
- 如果只想单独跑底层发布检查，再执行：
  - `bash scripts/pre-release-check.sh`
- 如果只想先验证“当前状态”文档有没有版本漂移，可以单独执行：
  - `python3 scripts/check-doc-current-state.py`
- Release 附件可上传 `dist/` 下生成的插件 ZIP，以及 `dist/skills/` 下生成的公开 Skill ZIP；校验文件在 Release 附件中使用 `PLUGIN_` / `SKILL_` 前缀避免重名
- `Release Preflight` workflow 通过后会把插件 ZIP、Skill ZIP、`SHA256SUMS.txt` 和 `MANIFEST.json` 上传为 Actions artifact，可直接下载核对或作为 Release 附件来源
- 可以用 `bash scripts/create-draft-release.sh <tag> --dry-run` 预览 Release 附件和说明，再去掉 `--dry-run` 创建 Draft Release
- 也可以手动运行 GitHub Actions -> Draft Release；默认 `dry_run=true`，并会上传 release asset artifact 供核对
- Draft Release 核对无误后，用 `gh release edit <tag> --draft=false --latest --target main` 发布正式 Release
- 正式发布后执行 `bash scripts/verify-release-download.sh <tag>`，确认公开附件可下载且校验通过
- GitHub Actions 已支持手动运行，可在 Actions -> Release Preflight -> Run workflow 主动触发一次完整发布检查
- 具体发版步骤见：[RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md)

## 当前对外文档

真正对用户和外部智能体公开的主文档，发布前至少确认这几份没有落后于代码：

- `README.md`
- `docs/INDEX.md`
- `docs/PLUGIN_INSTALL.md`
- `docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md`
- `docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md`

## 当前 ZIP 覆盖

`release-preflight.sh` 的完整检查阶段会生成当前清单里的 8 个本地安装包：

- `AIRecognizerEnhancer`
- `AgentResourceOfficer`
- `FeishuCommandBridgeLong`
- `HdhiveOpenApi`
- `QuarkShareSaver`

## 历史说明

早期 `v2.0.0-alpha.1` 是旧 AI Gateway 拆分阶段的首发说明，已移到历史文档：

- [RELEASE_v2.0.0-alpha.1.md](./RELEASE_v2.0.0-alpha.1.md)

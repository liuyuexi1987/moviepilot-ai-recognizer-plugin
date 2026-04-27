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

- README 首页保持中文
- GitHub 仓库描述使用简短英文
- 发布前执行一次：
  - `bash scripts/pre-release-check.sh`
- Release 附件可上传 `dist/` 下生成的全部 ZIP
- CI 通过后会把 `dist/*.zip` 上传为 Actions artifact，可直接下载核对或作为 Release 附件来源
- GitHub Actions 已支持手动运行，可在 Actions -> CI -> Run workflow 主动触发一次完整发布检查
- 具体发版步骤见：[RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md)

## 当前 ZIP 覆盖

`pre-release-check.sh` 会生成当前清单里的 8 个本地安装包：

- `AIRecoginzerForwarder`
- `AIRecognizerEnhancer`
- `AgentResourceOfficer`
- `FeishuCommandBridgeLong`
- `HDHiveDailySign`
- `HdhiveOpenApi`
- `QuarkShareSaver`
- `ZspaceMediaFreshMix`

## 历史说明

早期 `v2.0.0-alpha.1` 是旧 AI Gateway 拆分阶段的首发说明，已移到历史文档：

- [RELEASE_v2.0.0-alpha.1.md](./RELEASE_v2.0.0-alpha.1.md)

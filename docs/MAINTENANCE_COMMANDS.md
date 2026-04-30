# 仓库维护命令索引

这份文档只列当前常用的仓库维护与发布命令，不解释历史方案。

## 最常用入口

- 仓库卫生检查：

```bash
bash scripts/repo-hygiene.sh
```

- 发版前完整检查：

```bash
bash scripts/release-preflight.sh
```

- 低层发布检查：

```bash
bash scripts/pre-release-check.sh
```

## 状态与审计

- 检查当前状态文档是否和代码版本一致：

```bash
python3 scripts/check-doc-current-state.py
```

- 审计远端和本地历史分支：

```bash
python3 scripts/audit-remote-branches.py
```

- 归档本地非 `main` 分支到 `archive/*` tag：

```bash
python3 scripts/archive-local-branches.py
python3 scripts/archive-local-branches.py --apply
```

## 打包与发布

- 创建 Draft Release 前 dry-run：

```bash
bash scripts/create-draft-release.sh <tag> --dry-run
```

- 创建 Draft Release：

```bash
bash scripts/create-draft-release.sh <tag>
```

- 用当前 `dist/` 覆盖已有 Draft Release 附件：

```bash
bash scripts/update-draft-release-assets.sh <tag>
```

- 校验公开 Release 下载附件：

```bash
bash scripts/verify-release-download.sh <tag>
```

## Artifact 与产物校验

- 下载并校验最近一次成功的 `Release Preflight` workflow artifact：

```bash
bash scripts/verify-release-preflight-artifact.sh
bash scripts/verify-release-preflight-artifact.sh <run_id>
```

- 校验本地 release 资产目录：

```bash
bash scripts/verify-release-assets.sh
bash scripts/verify-release-assets.sh /path/to/release-assets
```

- 校验插件 ZIP：

```bash
DIST_DIR=dist bash scripts/verify-dist.sh
```

- 校验 Skill ZIP：

```bash
DIST_DIR=dist/skills bash scripts/verify-skill-dist.sh
```

## 汇总输出

- 打印插件 ZIP Markdown 表格：

```bash
bash scripts/print-release-summary.sh
```

- 打印 Skill ZIP Markdown 表格：

```bash
bash scripts/print-skill-release-summary.sh
```

- 生成 Release notes：

```bash
bash scripts/generate-release-notes.sh <tag>
```

## 帮助

这些脚本现在都支持 `--help` 或 `-h`，包括：

- `repo-hygiene.sh`
- `release-preflight.sh`
- `pre-release-check.sh`
- `create-draft-release.sh`
- `update-draft-release-assets.sh`
- `verify-release-preflight-artifact.sh`
- `verify-ci-artifact.sh`
- `verify-release-download.sh`
- `verify-release-assets.sh`
- `verify-dist.sh`
- `verify-skill-dist.sh`
- `print-release-summary.sh`
- `print-skill-release-summary.sh`
- `check-doc-current-state.py`
- `audit-remote-branches.py`
- `archive-local-branches.py`

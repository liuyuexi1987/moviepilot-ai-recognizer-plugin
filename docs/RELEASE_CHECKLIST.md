# Release Checklist

发布前按这个顺序执行，避免漏包、错包或上传旧 ZIP。

## 1. 确认工作区

```bash
git status --short --branch
```

工作区应当干净。

## 2. 查看插件清单

```bash
bash scripts/package-plugin.sh --list
```

确认输出的插件和版本符合本次发布预期。

## 3. 执行完整检查

如果只改了 Skill，可以先跑轻量检查：

```bash
bash scripts/check-skills.sh
```

最终发布前仍然执行完整检查：

```bash
bash scripts/pre-release-check.sh
```

这个命令会同步 `plugins/` 和 `plugins.v2/`，检查元数据、Skill helper、ZIP 内容，并重新生成插件 ZIP、Skill ZIP、`SHA256SUMS.txt` 和 `MANIFEST.json`。

## 4. 上传 ZIP

Release 附件上传 `dist/` 下的插件 ZIP、`dist/skills/` 下的 Skill ZIP，以及对应的 `SHA256SUMS.txt` 和 `MANIFEST.json`：

```bash
ls -1 dist/*.zip
ls -1 dist/skills/*.zip
cat dist/SHA256SUMS.txt
cat dist/MANIFEST.json
cat dist/skills/SHA256SUMS.txt
cat dist/skills/MANIFEST.json
bash scripts/verify-release-assets.sh
bash scripts/verify-dist.sh
bash scripts/verify-skill-dist.sh
bash scripts/print-release-summary.sh
bash scripts/print-skill-release-summary.sh
```

不要上传历史旧包。`pre-release-check.sh` 会在打包前清理旧 ZIP。

## 5. 远端确认

推送后确认 GitHub Actions 通过：

```bash
gh run list --limit 3
```

CI 通过后会在该 run 的 Artifacts 区域生成 `moviepilot-release-assets-<commit>`，里面包含本次插件 ZIP、Skill ZIP、`SHA256SUMS.txt` 和 `MANIFEST.json`。

如需在本地下载并校验最近一次成功 CI artifact：

```bash
bash scripts/verify-ci-artifact.sh
```

也可以指定 run id：

```bash
bash scripts/verify-ci-artifact.sh 25017759143
```

也可以在 GitHub 页面手动运行：Actions -> CI -> Run workflow。

## 6. 创建 Draft Release

先 dry-run，确认附件和说明能生成：

```bash
bash scripts/create-draft-release.sh v2026.04.28 --dry-run
```

确认无误后创建 GitHub Draft Release：

```bash
bash scripts/create-draft-release.sh v2026.04.28
```

也可以在 GitHub Actions 手动触发：

```bash
gh workflow run draft-release.yml -f tag=v2026.04.28 -f dry_run=true
```

dry-run 通过后会生成 `moviepilot-release-assets-<tag>-<commit>` artifact，可先下载核对。确认无误后，再用 `dry_run=false` 创建 Draft Release。

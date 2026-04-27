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

```bash
bash scripts/pre-release-check.sh
```

这个命令会同步 `plugins/` 和 `plugins.v2/`，检查元数据、Skill helper、ZIP 内容，并重新生成 `dist/*.zip`。

## 4. 上传 ZIP

Release 附件上传 `dist/` 下的全部 ZIP 和 `SHA256SUMS.txt`：

```bash
ls -1 dist/*.zip
cat dist/SHA256SUMS.txt
```

不要上传历史旧包。`pre-release-check.sh` 会在打包前清理旧 ZIP。

## 5. 远端确认

推送后确认 GitHub Actions 通过：

```bash
gh run list --limit 3
```

CI 通过后会在该 run 的 Artifacts 区域生成 `moviepilot-plugin-zips-<commit>`，里面包含本次 `dist/*.zip` 和 `SHA256SUMS.txt`。

也可以在 GitHub 页面手动运行：Actions -> CI -> Run workflow。

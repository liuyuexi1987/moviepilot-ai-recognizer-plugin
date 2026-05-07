# 夸克 Cookie 导出

这个目录提供了一个轻量的夸克 Cookie 导出工具，用来从本机浏览器读取当前登录态，并自动写回 MoviePilot 插件配置。

适合场景：

1. 没有部署 CookieCloud
2. 夸克提示登录态失效、`require login [guest]`
3. 想快速恢复 `AgentResourceOfficer` / `QuarkShareSaver` 的夸克转存能力

## 能做什么

- 从 Edge / Chrome / Brave / Firefox 读取 `pan.quark.cn` 的当前 Cookie
- 可选复制到剪贴板
- 自动写回：
  - `plugin.AgentResourceOfficer.quark_cookie`
  - `plugin.QuarkShareSaver.cookie`
- 可选自动重启 `moviepilot-v2`

## 命令行用法

安装依赖：

```bash
pip3 install -r requirements.txt
```

直接从 Edge 读取并写回 MoviePilot：

```bash
python3 export_quark_cookie.py https://pan.quark.cn \
  --browser edge \
  --write-mp \
  --restart-container moviepilot-v2
```

只导出并复制到剪贴板：

```bash
python3 export_quark_cookie.py https://pan.quark.cn --browser edge
```

默认写入数据库：

- `/Applications/Dockge/moviepilotv2/config/user.db`

如果你是从 `MoviePilot-Plugins` 仓库里使用，推荐直接保留这个目录结构不动，并把：

- `ARO_QUARK_COOKIE_EXPORT_DIR`

指向本目录。

## 双击使用

直接双击：

`夸克Cookie导出.command`

它会固定执行：

1. 从 Edge 读取 `https://pan.quark.cn`
2. 自动写回 MoviePilot
3. 自动重启 `moviepilot-v2`

## 推荐流程

1. 先在 Edge 打开并登录 [https://pan.quark.cn](https://pan.quark.cn)
2. 双击 `夸克Cookie导出.command`
3. 回到智能体或 MoviePilot 重试夸克转存

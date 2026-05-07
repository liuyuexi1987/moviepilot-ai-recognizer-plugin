# 影巢 Cookie 快速导出

这个目录里提供了一个小脚本，可以直接从本机浏览器里读取指定站点的登录 Cookie，
并自动拼成插件配置需要的完整 `Cookie` 字符串。

另外还附带了一个可双击运行的 macOS 启动器：

`影巢Cookie导出.command`

现在它还支持把最新 Cookie 直接写回 MoviePilot 的
`plugin.HdhiveSign` 配置，同时同步写入
`/Applications/Dockge/moviepilotv2/config/plugins/hdhivedailysign.json`，
并同步写入 `plugin.AgentResourceOfficer.hdhive_checkin_cookie`，
并自动重启 `moviepilot-v2` 容器。

## 安装

```bash
pip3 install -r requirements.txt
```

如果你是从 `MoviePilot-Plugins` 仓库里使用，推荐直接保留这个目录结构不动，并把：

- `ARO_HDHIVE_COOKIE_EXPORT_DIR`

指向本目录。

## 用法

Chrome:

```bash
python3 export_yc_cookie.py yc.example.com
```

Edge:

```bash
python3 export_yc_cookie.py yc.example.com --browser edge
```

如果你拿到的是完整网址，也可以直接传：

```bash
python3 export_yc_cookie.py https://yc.example.com
```

脚本会：

1. 从浏览器读取该域名下的 Cookie。
2. 自动拼成 `name=value; name2=value2` 格式。
3. 自动复制到 macOS 剪贴板。
4. 检查是否包含 `token` 和 `csrf_access_token`。
5. 如果只有 `token` 没有 `csrf_access_token`，会提示这更可能是站点或插件兼容性问题。

## 直接写回 MoviePilot

如果你希望把最新登录态直接同步到 MoviePilot：

```bash
python3 export_yc_cookie.py https://hdhive.com --browser edge --write-mp --restart-container moviepilot-v2
```

默认写入位置：

- 数据库：`/Applications/Dockge/moviepilotv2/config/user.db`
- 配置键：`plugin.HdhiveSign`
- 资源官键：`plugin.AgentResourceOfficer.hdhive_checkin_cookie`
- 旧签到 JSON：`/Applications/Dockge/moviepilotv2/config/plugins/hdhivedailysign.json`

写回时会优先生成插件真正需要的最小 Cookie：

- `token`
- `csrf_access_token`（如果浏览器里存在）
- `refresh_token`（当前影巢网页签到兜底也依赖它）

## 双击使用

如果你不想每次手动敲命令，可以直接双击：

`影巢Cookie导出.command`

它会提示你输入：

1. 影巢域名或完整网址
2. 浏览器类型
3. 操作模式
   - 只导出到剪贴板
   - 导出并写回 MoviePilot（推荐）

推荐模式下，它会：

1. 从浏览器读取最新 Cookie
2. 写回 MoviePilot 的 `plugin.HdhiveSign`
3. 同步写入 `plugin.AgentResourceOfficer.hdhive_checkin_cookie`
4. 同步写入 `hdhivedailysign.json`
5. 自动重启 `moviepilot-v2`
6. 让新 Cookie 立即生效

## 推荐流程

1. 先正常登录影巢站点。
2. 打开一次站点首页或任意已登录页面。
3. 双击 `影巢Cookie导出.command`
4. 选择“导出并写回 MoviePilot（推荐）”

如果你只想手动复制，也可以选“只导出到剪贴板”。

## 说明

- 如果站点改了域名，换成新域名重新执行一次。
- 如果脚本提示缺少 `token` 或 `csrf_access_token`，通常说明登录态已经过期，或者当前域名不对。
- 如果脚本明确提示“只有 token，没有 csrf_access_token”，说明脚本已经成功读到浏览器 Cookie，但站点当前登录流没有给出 `csrf_access_token`。这种情况更像插件规则过时，而不是你不会抓 Cookie。
- 这个方案的目标不是“让 Cookie 永不过期”，而是“过期后 10 秒内重新拿到最新 Cookie”。
- 写回 MoviePilot 后，如果容器重启成功，新 Cookie 会立即生效。

# Agent影视助手跨机器部署

当前插件版本：`Agent影视助手 0.2.68`

当前 helper 版本：`agent-resource-officer 0.1.46`

这份文档只讲一种常见情况：

```text
MoviePilot 在 NAS / Docker / 远程主机
外部智能体在 Win / Mac 电脑
```

这属于正常用法，不是特殊模式。关键只有一个：智能体要能访问到 MoviePilot。

---

## 先填对 ARO_BASE_URL

外部智能体所在电脑的配置文件一般是：

```text
~/.config/agent-resource-officer/config
```

如果 MoviePilot 在 NAS，配置应类似：

```text
ARO_BASE_URL=http://192.168.1.100:3000
ARO_API_KEY=你的 MoviePilot API_TOKEN
```

不要写：

```text
ARO_BASE_URL=http://127.0.0.1:3000
```

因为这里的 `127.0.0.1` 代表智能体自己这台电脑，不是 NAS。

只有 MoviePilot 和智能体在同一台机器时，才用：

```text
ARO_BASE_URL=http://127.0.0.1:3000
```

---

## 多套 MoviePilot 时要注意

`ARO_BASE_URL` 指向哪套 MoviePilot，下面这些命令就使用哪套 MoviePilot：

```text
MP搜索
PT搜索
下载
订阅
转存
更新检查
```

如果你有一套 MoviePilot 只用于网盘 / STRM，不要在这套实例里确认 PT 下载。

如果你真正下载用的是 NAS 上另一套 MoviePilot，就把 `ARO_BASE_URL` 指向那一套。

---

## MP 和 qB 不同机时

如果 MoviePilot 和 qBittorrent 不在一台机器，可以在 `Agent影视助手` 设置页填写：

```text
PT 下载保存路径
```

简单理解：

- MoviePilot 和 qB 在同一台机器：通常不用填。
- MoviePilot 和 qB 不在一台机器：填 qB 能识别的真实下载目录。

示例：

```text
/downloads
/volume1/downloads
local:/downloads
```

不要填你当前电脑上的临时路径，除非 qB 也真的在这台电脑上。

---

## 盘搜 API 地址按 MoviePilot 视角填

这里容易混：

- `ARO_BASE_URL` 是外部智能体访问 MoviePilot 的地址。
- `盘搜 API 地址` 是 MoviePilot 插件访问 PanSou 的地址。

如果 PanSou 和 MoviePilot 在同一台 NAS / Docker 网络里，`盘搜 API 地址` 要填 MoviePilot 那边能访问到的地址，不一定是你电脑能访问到的地址。

---

## Cookie 修复读的是哪台电脑

这些命令会用到浏览器 Cookie：

```text
刷新影巢Cookie
修复影巢签到
刷新夸克Cookie
修复夸克转存
```

跨机器时，它们读取的是**智能体所在电脑**的浏览器登录态，然后写回 NAS 上的 MoviePilot。

所以如果 MoviePilot 在 NAS、智能体在 Mac：

1. 在 Mac 浏览器里登录 `https://hdhive.com` 或 `https://pan.quark.cn`。
2. 再让智能体执行修复命令。
3. 不需要去 NAS 桌面上找浏览器 Cookie。

---

## 最小验证

在智能体所在机器执行：

```bash
python3 scripts/aro_request.py readiness
```

如果通过，说明智能体已经能访问 MoviePilot 插件。

再试一个只读命令：

```bash
python3 scripts/aro_request.py route "115状态"
```

如果也能返回，跨机器主链基本就通了。

---

## 常见错误

### 1. NAS 环境还写 127.0.0.1

表现：智能体连接失败、请求打到自己电脑。

解决：把 `ARO_BASE_URL` 改成 NAS 的局域网 IP 或域名。

### 2. 改了仓库文件，但 MoviePilot 还在跑旧插件

仓库里的文件改完后，不等于容器里的插件已经更新。

如果页面或接口还是旧表现，先确认 MoviePilot 实际加载的是最新插件。

### 3. 长线程被旧上下文污染

表现：

- `15详情` 被当成 `选择 15`
- 编号接到旧搜索结果
- 明明更新了规则，智能体还是按旧说法执行

直接对智能体说：

```text
校准影视技能
```

不要在普通搜索前固定清会话，否则会破坏正常编号续接。

---

## 推荐阅读

- [外部智能体接入](./AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)
- [全部命令](./ALL_COMMANDS.md)
- [插件安装说明](./PLUGIN_INSTALL.md)

# Cookie 导出工具

这个目录收录了两个可分发的本机导出工具：

- [影巢 Cookie 导出](./hdhive-cookie-export/README.md)
- [夸克 Cookie 导出](./quark-cookie-export/README.md)

它们的定位是：

- 从**当前电脑浏览器**读取登录态 Cookie
- 写回 `MoviePilot` / `Agent影视助手` 的插件配置
- 作为 `刷新影巢Cookie`、`修复影巢签到`、`刷新夸克Cookie`、`修复夸克转存` 这类命令的宿主机执行层

注意：

- 这些工具运行在**外部智能体所在电脑**，不是运行在 NAS 容器里
- 如果 `MoviePilot` 在 NAS，而智能体在 Win / Mac，Cookie 会先从当前电脑浏览器导出，再写回 NAS 上的 `MoviePilot`
- 默认更适合 macOS；如果是别的环境，请先确认 `python3`、浏览器 Cookie 读取和容器重启命令是否可用

安装依赖示例：

```bash
cd tools/hdhive-cookie-export && python3 -m pip install -r requirements.txt
cd tools/quark-cookie-export && python3 -m pip install -r requirements.txt
```

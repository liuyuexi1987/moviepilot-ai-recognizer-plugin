# FeishuCommandBridgeLong

飞书命令桥接插件的长连接版本，面向 MoviePilot 使用。

## 目标

- 不再依赖公网 webhook / HTTPS 回调地址
- 使用飞书长连接直接接收 `im.message.receive_v1`
- 将飞书文本命令映射成 MoviePilot 内部命令或 115 整理动作
- 对关键动作回执开始、完成、统计结果

## 当前支持

- 飞书长连接接收消息
- 群聊 / 用户白名单
- 中文别名映射
- 跨实例事件去重，避免同一 `event_id` 重复执行
- 可选回执消息
- 115 手动整理默认目录批量执行
- STRM 增量 / 全量命令桥接

## 依赖

```txt
lark-oapi==1.5.3
```

## 飞书后台配置

在飞书开放平台中：

1. 打开应用
2. 开启事件订阅
3. 订阅方式改为“长连接”
4. 勾选事件：`im.message.receive_v1`
5. 填写应用的 `App ID`、`App Secret`
6. `Verification Token` 可填写，但长连接模式本身不依赖公网 challenge

## 当前命令语义

### 基础命令

```txt
版本
```

对应：

```txt
/version
```

### 115 整理命令

```txt
刮削
```

- 不带参数时：读取 `P115StrmHelper.pan_transfer_paths`
- 如果配置了多个待整理目录，会全部逐个执行

```txt
刮削 /待整理/
```

- 只执行指定目录

### STRM 命令

```txt
生成STRM
同步STRM
```

- 走 `/p115_inc_sync`
- 按 `P115StrmHelper.increment_sync_strm_paths` 中配置的全部媒体库做增量生成

```txt
全量STRM
```

- 走 `/p115_full_sync`
- 按 `P115StrmHelper.full_sync_strm_paths` 中配置的全部媒体库做全量生成

```txt
指定路径STRM /某路径
```

- 走 `/p115_strm /某路径`
- 只对指定路径做全量生成

## 回执

对 `刮削` 命令会回：

- 开始回执
- 完成回执
- 总计 / 成功 / 失败 / 跳过统计
- 失败示例（最多 3 条）

## 已知限制

- 长连接线程启动后暂未实现无重启主动停止
- 修改 `app_id / app_secret` 后建议重启 MoviePilot
- 115 相关命令依赖 `P115StrmHelper`

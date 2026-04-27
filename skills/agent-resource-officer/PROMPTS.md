# AgentResourceOfficer Prompt Examples

## Startup

```text
使用 agent-resource-officer skill，先调用 startup，读取 recommended_request_templates，然后按推荐 recipe 获取低 token 请求模板。
```

## PanSou Search

```text
使用 agent-resource-officer skill，盘搜搜索“大君夫人”，分别展示 115 和夸克结果，让我选择编号。不要直接转存，等我确认编号。
```

## HDHive Search

```text
使用 agent-resource-officer skill，影巢搜索“蜘蛛侠”。如果有多个候选影片，先让我选择影片；再展示资源列表。
```

## Direct Share Link

```text
使用 agent-resource-officer skill，处理这个分享链接并转存到默认目录：https://pan.quark.cn/s/xxxx
```

## Custom Path

```text
使用 agent-resource-officer skill，把这个夸克链接转存到 /飞书：链接 https://pan.quark.cn/s/xxxx path=/飞书
```

## Continue Choice

```text
使用 agent-resource-officer skill，继续当前会话，选择 1。如果返回 confirmation_message，先给我确认提示。
```

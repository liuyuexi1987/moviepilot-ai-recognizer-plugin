# Agent资源官架构草案

`Agent资源官` 是重构后的资源工作流主插件，重点不是把旧代码简单拼一起，而是把职责重新压平。

## 设计目标

- 一个插件承接“搜索 -> 选择 -> 解锁 -> 转存 -> 签到/用户态 -> 远程入口”
- 智能体、飞书、CLI、后续 MP Agent Tool 共享同一套执行服务
- 会话交互与底层执行解耦，避免继续把大量业务逻辑堆在消息入口层

## 模块分层

### 1. adapters

负责不同外部入口和外部平台接入：

- `feishu`
- `hdhive`
- `quark`
- `pansou`
- 后续 `agent_tool`

原则：

- 只负责协议和输入输出转换
- 不负责复杂业务编排

### 2. services

负责核心业务能力：

- `search_service`
- `unlock_service`
- `transfer_service`
- `signin_service`
- `user_service`

原则：

- 统一返回结构
- 尽量不感知飞书、页面、CLI 等具体入口

### 3. session

负责交互上下文：

- 搜索候选缓存
- 翻页状态
- 选择上下文
- 详情/审查补充信息（已支持候选页按需补主演）

原则：

- 入口层共享同一套会话数据
- 后续优先支持内存 + 轻量持久化

### 4. models

负责统一数据模型：

- 搜索候选
- 资源条目
- 解锁结果
- 转存结果
- 用户信息

目标：

- 减少旧插件之间字段名不一致的问题

## 首期配置模型

### 基础

- `enabled`
- `notify`
- `debug`

### 影巢

- `hdhive_base_url`
- `hdhive_api_key`
- `hdhive_default_path`
- `hdhive_candidate_page_size`

### 夸克

- `quark_cookie`
- `quark_default_path`
- `quark_timeout`
- `quark_auto_import_cookiecloud`

### 飞书

- `feishu_enabled`
- `feishu_app_id`
- `feishu_app_secret`
- `feishu_verification_token`
- `feishu_allow_all`
- `feishu_allowed_chat_ids`
- `feishu_allowed_user_ids`

### 智能体 / 工具层预留

- `agent_tools_enabled`
- `tool_debug`

## 迁移映射

### 从 `QuarkShareSaver`

优先迁入：

- 分享链接解析
- 目录创建
- 转存执行
- CookieCloud 自动导入

当前已开始拆出：

- `services/quark_transfer.py`

### 从 `P115StrmHelper` 协同层

当前已开始拆出：

- `services/p115_transfer.py`

### 从 `HdhiveOpenApi`

随后迁入：

- 搜索
- 候选解析
- 解锁
- 用户信息
- 配额
- 分享管理

当前已开始拆出：

- `services/hdhive_openapi.py`

### 从 `HDHiveDailySign`

补入：

- 普通签到
- 赌狗签到
- 自动登录与状态记录

### 从 `FeishuCommandBridgeLong`

最后收口：

- 飞书长连接入口
- 自然语言别名解析
- 搜索/选择会话衔接

## 暂不迁入的内容

- PT 搜索/订阅工作流仍保持在旧桥接插件，后续单独评估
- 与 `P115StrmHelper` 的兼容性问题不在首期重构内处理

## 首个里程碑

第一个可用版本只追求三件事：

1. 夸克分享链接直接转存
2. 影巢搜索并解锁
3. 飞书调用同一套执行服务

当前进度：

- 已拆出夸克执行服务
- 已拆出影巢基础 OpenAPI 服务
- 已拆出 115 转存执行服务
- 已补上 Agent资源官 自己的统一智能入口（assistant route / pick）
- 主插件已具备：
  - 夸克健康检查
  - 夸克转存
  - 影巢健康检查
  - 影巢搜索
  - 影巢关键词候选搜索
  - 影巢解锁
  - 115 依赖健康检查
  - 115 分享转存
  - 影巢解锁后自动路由到夸克执行层
  - 影巢解锁后自动路由到 115 执行层
  - 影巢会话搜索与按编号继续选择
  - 盘搜搜索与按编号继续执行
  - 统一智能入口对直链、盘搜、影巢三类输入的会话分流

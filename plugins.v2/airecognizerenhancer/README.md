# AI识别增强

这是重构后的新识别插件目录，用来逐步替代当前依赖外部 AI Gateway 的旧识别转发思路。

当前第一版已经可用，目标不是简单复制旧插件，而是改成：

- 直接复用 MoviePilot 当前已启用的 LLM 配置
- 在原生识别失败后做本地结构化 AI 辅助识别
- 自动回到 MoviePilot 整理链路继续处理

## 计划承接的来源

- `AIRecoginzerForwarder`

## 当前能力

- 监听 `ChainEventType.NameRecognize`
- 用 MP 当前 LLM 结构化判断标题、年份、类型、季集
- 把识别结果回写到 `name/year/season/episode`
- 交回 MoviePilot 原生链路继续二次识别
- 提供 `/health`、`/recognize`、`/failed_samples`、`/sample_worklist`、`/sample_insights`、`/suggest_identifiers`、`/suggest_identifiers_from_sample`、`/apply_identifiers`、`/apply_suggested_identifier`、`/remove_failed_sample`、`/replay_failed_sample`、`/replay_failed_samples`、`/clear_failed_samples` 十三个 API
- 可选保存低置信度样本，并对重复样本自动去重、限制保留上限，再继续做样本洞察和 MoviePilot 原生自定义识别词建议

## 当前接口

- `GET /api/v1/plugin/AIRecognizerEnhancer/health`
  返回启用状态、LLM 提供方、模型名、阈值和超时配置
- `POST /api/v1/plugin/AIRecognizerEnhancer/recognize`
  用当前 LLM 对指定标题做一次本地结构化识别测试
- `GET /api/v1/plugin/AIRecognizerEnhancer/failed_samples`
  查看最近保存的低置信度样本
- `GET /api/v1/plugin/AIRecognizerEnhancer/sample_worklist`
  返回适合智能体直接消费的失败样本摘要列表
- `GET /api/v1/plugin/AIRecognizerEnhancer/sample_insights`
  聚合失败样本原因、重复问题和优先处理样本，方便先挑最值得写规则的那批
- `POST /api/v1/plugin/AIRecognizerEnhancer/suggest_identifiers`
  根据标题、目标结果和当前识别结果生成 MoviePilot 自定义识别词建议
- `POST /api/v1/plugin/AIRecognizerEnhancer/suggest_identifiers_from_sample`
  直接基于最近失败样本或指定样本生成识别词建议
- `POST /api/v1/plugin/AIRecognizerEnhancer/apply_identifiers`
  将确认后的规则追加写入系统 `CustomIdentifiers`
- `POST /api/v1/plugin/AIRecognizerEnhancer/apply_suggested_identifier`
  直接把最近失败样本或指定样本生成的建议规则写入系统 `CustomIdentifiers`，并按需自动移除该样本
- `POST /api/v1/plugin/AIRecognizerEnhancer/remove_failed_sample`
  按索引移除单条失败样本
- `POST /api/v1/plugin/AIRecognizerEnhancer/replay_failed_sample`
  用当前识别词和当前识别器重新复查某条失败样本，并可在确认已修复后自动出队
- `POST /api/v1/plugin/AIRecognizerEnhancer/replay_failed_samples`
  批量复查失败样本，并可在确认已修复后批量出队
- `POST /api/v1/plugin/AIRecognizerEnhancer/clear_failed_samples`
  清空失败样本文件

## 二期方向

- 生成“自定义识别词”建议
- 识别失败样本沉淀
- 与 MP 原生 Agent / Skill 能力联动

## 迁移原则

- 不再把外部 Gateway 当作唯一依赖
- 尽量减少容器间回调和额外网络链路
- 保持插件职责只聚焦在“识别增强”

## 当前状态

- `0.1.7` 已补上失败样本批量复查动作，可批量重跑样本并在确认修复后批量出队
- 方向已切到 MP 内置 LLM 本地兜底
- 还会继续补提示词、样本分析和识别词建议

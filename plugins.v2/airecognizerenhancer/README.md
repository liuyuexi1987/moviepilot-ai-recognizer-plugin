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
- 提供 `/health` 与 `/recognize` 两个测试 API
- 可选保存低置信度样本，便于后续优化提示词或补自定义识别词

## 当前接口

- `GET /api/v1/plugin/AIRecognizerEnhancer/health`
  返回启用状态、LLM 提供方、模型名、阈值和超时配置
- `POST /api/v1/plugin/AIRecognizerEnhancer/recognize`
  用当前 LLM 对指定标题做一次本地结构化识别测试

## 二期方向

- 生成“自定义识别词”建议
- 识别失败样本沉淀
- 与 MP 原生 Agent / Skill 能力联动

## 迁移原则

- 不再把外部 Gateway 当作唯一依赖
- 尽量减少容器间回调和额外网络链路
- 保持插件职责只聚焦在“识别增强”

## 当前状态

- 第一版插件代码已落地
- 方向已切到 MP 内置 LLM 本地兜底
- 还会继续补提示词、样本分析和识别词建议

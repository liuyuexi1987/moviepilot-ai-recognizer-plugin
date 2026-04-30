# 文档索引

这份索引只区分两类内容：

- 当前有效文档：现在安装、接入、发布时应该优先看的
- 历史归档文档：保留上下文，不作为当前操作手册

## 当前有效文档

### 使用与接入

- [PLUGIN_INSTALL.md](./PLUGIN_INSTALL.md)
  当前安装方式、ZIP 打包入口、Skill 安装方式

- [AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md](./AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)
  外部智能体接入 `Agent影视助手 / AgentResourceOfficer`

- [AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md](./AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md)
  `MoviePilot` 在 NAS、Windows、远程 Docker 主机时的接入与排查

### 发布与打包

- [PACKAGING.md](./PACKAGING.md)
  插件与 Skill 的本地打包、检查与发布产物规则

- [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md)
  发布前检查清单

- [GITHUB_PUBLISH.md](./GITHUB_PUBLISH.md)
  GitHub 页面发布与仓库同步说明

## 历史归档文档

- [REBUILD_AGENT_SUITE.md](./REBUILD_AGENT_SUITE.md)
  早期重构规划记录。用于回看设计演进，不作为当前使用说明

- [RELEASE_v2.0.0-alpha.1.md](./RELEASE_v2.0.0-alpha.1.md)
  旧 AI Gateway 阶段的历史发布草稿，不作为当前发布说明

## 阅读顺序建议

### 新用户 / 新环境

1. `README.md`
2. `PLUGIN_INSTALL.md`
3. `AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md`
4. 如果跨机器，再看 `AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md`

### 外部智能体接入

1. `skills/agent-resource-officer/SKILL.md`
2. `skills/agent-resource-officer/README.md`
3. `AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md`
4. 如果跨机器，再看 `AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md`

### 发布前

1. `PACKAGING.md`
2. `RELEASE_CHECKLIST.md`
3. `GITHUB_PUBLISH.md`

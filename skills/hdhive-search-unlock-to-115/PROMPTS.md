# Recommended Prompts

## Search Only

```text
使用 hdhive-search-unlock-to-115 skill，搜索《黑客帝国》，列出前10个资源让我选。默认优先 115、免费资源，不要直接解锁。
```

## Search Then Unlock by Choice

```text
使用 hdhive-search-unlock-to-115 skill，搜索《黑客帝国》，列出前10个资源让我选。我选中后按编号解锁；如果是 115 资源，就放到 /待整理。收费资源必须先征求我确认。
```

## TV Search

```text
使用 hdhive-search-unlock-to-115 skill，搜索《绝命毒师》，自动判断电影或剧集，列出前10个资源让我选。
```

## Force Year

```text
使用 hdhive-search-unlock-to-115 skill，搜索《超级马里奥兄弟大电影》，年份 2023，列出前10个资源让我选。
```

## Agent Notes

- 优先使用单入口脚本 `scripts/hdhive_agent_tool.py`
- 默认使用文本输出，不必回传整段 JSON
- 只有在后续步骤需要结构化数据时才加 `--output json`
- 默认不要付费解锁，除非用户明确确认
- `115.com/s/...` 也是有效的 115 分享链接，不要先入为主判成“非 115”
- 是否转存成功，以插件实际返回结果为准

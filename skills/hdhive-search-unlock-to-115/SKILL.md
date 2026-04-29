---
name: hdhive-search-unlock-to-115
description: HDHive agent skill template. Use when an agent should search HDHive resources by movie or TV title, show the top 10 candidate results, let the user choose one, then unlock the selected resource and try to transfer 115 links into MoviePilot's configured `/待整理` directory.
---

# HDHive Search, Choose, Unlock, and Drop to 115

This is the public repository copy of the skill.

After copying this skill into your own external-agent skill environment, adapt runtime paths with:

- `MP_APP_ENV`
- `MP_BASE_URL`
- `TMDB_API_KEY`
- command-line flags like `--app-env` and `--mp-base-url`

## Use This Skill When

- “影巢搜索某部电影”
- “列出前 10 个资源让我选”
- “选中后帮我解锁并放到 115”

## Preconditions

- MoviePilot is reachable locally.
- `HdhiveOpenApi` and `P115StrmHelper` are already installed.
- Search is done through the MoviePilot plugin API, not by calling HDHive raw APIs directly.
- Prefer the plugin keyword search endpoint. Do not assume HDHive OpenAPI itself supports keyword search.

## Local Discovery

Before acting:

1. Read MoviePilot API token from `app.env`.
2. Prefer `MP_APP_ENV` when available.
3. Otherwise use `--app-env` or one of your local default paths.
4. Never print API keys, cookies, or full secrets back to the user.
5. In this workflow, prefer `apikey=...` on local MoviePilot API requests over `login/access-token`.

## Preferred Tooling

Prefer the bundled helper scripts instead of ad hoc `curl` or temporary Python:

- `scripts/hdhive_agent_tool.py`
- `scripts/search_hdhive.py`
- `scripts/unlock_hdhive.py`
- `PROMPTS.md`

Preferred single-entry commands:

```bash
python3 scripts/hdhive_agent_tool.py search "黑客帝国"
python3 scripts/hdhive_agent_tool.py show
python3 scripts/hdhive_agent_tool.py unlock --index 1
```

- `search` writes a normalized cache file.
- `show` re-displays the latest cached result.
- `unlock --index N` unlocks by cached index and tries 115 transfer by default.
- Use `--output json` only when structured output is necessary.
- When candidate titles are ambiguous, the search script can enrich them with 1-2 actor names.
- `115.com/s/...` is also a valid 115 share form. Do not pre-judge it as “non-115”; trust the plugin's actual transfer result.

## Workflow

### 1. Search Through MoviePilot

Preferred path:

```bash
python3 scripts/hdhive_agent_tool.py search "片名"
```

- The tool reads the local MoviePilot API token, calls the plugin search endpoint, picks the better media type, and writes a normalized cache.
- Use `--output json` only if the next step really needs structured data.
- Fall back to lower-level scripts only when the single-entry tool is unavailable or clearly broken.

### 2. Handle Ambiguous Titles

- If keyword search returns multiple TMDB candidates, use `candidates`.
- Prefer the built-in actor enrichment instead of web search or ad hoc TMDB probing.
- Ask a short follow-up only when the results clearly mix different works.
- If one work is already obvious, show the resource list directly.

### 3. Rank and Present Results

When you need to re-rank:

1. `pan_type=115`
2. free items first
3. valid or unknown links before invalid ones
4. `4K` before `1080P`
5. `蓝光原盘/REMUX` before `WEB-DL/WEBRip`

Show each choice with:

- index
- title
- matched title if different
- pan type
- size
- resolution
- source
- unlock points

Example:

```text
1. 黑客帝国 (1999) | 115 | 64.91GB | 4K | 蓝光原盘/REMUX | 免费
```

### 4. Let the User Choose

- Stop after the top 10.
- Ask the user to choose by number.
- Do not unlock before the user chooses.
- If the chosen item costs points, ask for confirmation first.

### 5. Unlock and Transfer

Preferred path:

```bash
python3 scripts/hdhive_agent_tool.py unlock --index 1
```

- This reads the cached search result.
- It tries 115 transfer by default.
- It refuses paid unlocks unless `--allow-paid` is provided.
- Use `--path /待整理` to override the target directory if needed.
- Do not assume `115.com/s/...` cannot be transferred. Let the plugin decide.

### 6. Non-115 Items

- If the chosen item is clearly not `115`, warn the user that it cannot be auto-dropped into 115.
- Offer `unlock only` instead of pretending it can be auto-landed.

### 7. Report the Result

After unlock:

- say whether unlock succeeded
- say whether transfer succeeded
- report the final target path
- if transfer failed, include the short failure reason

## Guardrails

- Never expose secrets from `app.env`, database, or plugin configs.
- Never spend points without explicit user confirmation when `unlock_points > 0`.
- Never claim a non-115 link was dropped into 115.
- Never pre-judge `115.com/s/...` as non-115.
- Prefer cache index based unlocks over hand-copied slug text.
- Do not use ad hoc browser search just to fetch actors; use built-in enrichment first.

## Output Style

- Be concise.
- Show the top 10.
- Ask the user to choose one number.
- After selection, report the landing result in plain language.

---
name: web-search
description: Search the web for current information, trends, references, and source-backed answers.
metadata: {"nanobot":{"emoji":"🔎"}}
---

# Web Search

Use this skill when the user needs current, source-backed, or trend-sensitive information.

## When To Use

Use `web_search` when the request depends on information that may change over time, for example:

- latest trends
- current events
- current platform rules
- current product info
- current examples or references
- recent social-media topics
- competitor research
- hot search directions
- industry signals

Also use it when the user explicitly asks:

- 帮我搜一下
- 看看最近有什么
- 查一下最新情况
- 找几个参考
- 给我网页资料

## Core Rule

Do not guess when the user asks for "latest", "current", "today", "recent", or "what's trending".
Search first, then answer.

## Recommended Workflow

1. Clarify the search target in your own reasoning.
2. Use `web_search` with a focused query.
3. If needed, use `web_fetch` to open the most relevant result pages.
4. Extract the useful facts.
5. Answer in a concise, production-friendly format.
6. Include source links when they matter.

## Query Patterns

Use search phrases like:

- `"2026 烧烤 短视频 话题 趋势"`
- `"小红书 烧烤 文案 爆款"`
- `"抖音 烧烤 探店 热门 选题"`
- `"BBQ short video trends 2026"`
- `"best hooks for food videos"`

When useful, search from multiple angles:

- platform angle
- audience angle
- creator angle
- commercial angle

## Output Style

When search results are part of a creative workflow, prefer outputs like:

- Trend Summary
- Reference List
- Topic Opportunities
- Hook Directions
- Content Angle Recommendations

## For NanoKwali

For this project specifically, use web search to support:

- finding current short-video trends
- checking what topics are getting attention
- collecting reference styles and examples
- validating whether an angle feels outdated
- identifying title, hook, and format inspiration

If the user asks for a script based on current trends, search first and then write.

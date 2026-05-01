---
name: plot_generation
version: "1.1"
description: 情节生成指令 — 根据大纲节点生成章节情节
type: plot_generation
variables:
  - outline_path
  - chapter_title
  - chapter_summary
  - plot_points
  - emotional_tone
  - previous_chapter_summary
  - previous_chapter_plot_memory
  - previous_chapter_content
  - next_chapter_summary
  - volume_summary
  - act_summary
  - previous_plot_memories
---

## 情节约束

当前章节位置：**{{outline_path}}**

### 所属卷背景
{{volume_summary}}

### 当前幕要求 — 路线指导
{{act_summary}}
以上幕级要求对本次章节创作具有整体的路线指导意义，请在情节推进和氛围营造中严格体现。

### 本章定位
- **标题**：{{chapter_title}}
- **摘要**：{{chapter_summary}}
- **情感基调**：{{emotional_tone}}

### 必须包含的情节点
{{plot_points}}

### 衔接要求
{{previous_chapter_summary}}

### 前一章剧情记忆 — 情节提要
上一章的关键剧情与人物状态摘要，新章节必须在此基础上推进：
{{previous_chapter_plot_memory}}

### 前一章结尾片段 — 衔接锚点
以下是上一章的最后部分，仅作为续写起点。你严禁复述或重写上一章已发生的情节，必须直接续写新篇章内容，从上一章结束的地方自然推进：
{{previous_chapter_content}}

### 下一章方向预告
{{next_chapter_summary}}
本章结尾需为下一章做好铺垫和过渡，但不要提前写入下一章的内容。

### 更早章节剧情记忆 — 参考约束
以下是更早章节的关键剧情摘要，作为背景参考，必须遵循不能矛盾：
{{previous_plot_memories}}

### 创作守则
1. 严格按摘要展开，不遗漏任何情节点。
2. 情感基调必须贯穿全章，转折需有铺垫。
3. 与前一章的衔接自然，时间、空间、人物状态保持一致，减少重复提起相同的时间点。
4. 不得引入大纲外的新主线角色或重大事件，支线可适度展开但需可控。
5. 伏笔的埋设与回收要符合整体大纲安排。
6. 剧情逻辑必须严谨，符合常识：因果链条完整（凡事有因、结果合理），时间线连贯（无无法解释的跳跃），空间转换合理（移动耗时符合设定），人物行为基于其动机与已知信息（禁止为推剧情而强行降智或突然开悟）。
7. 重大事件发生后必须体现连锁反应，不能当作没发生过；角色的伤势、疲劳、资源消耗等状态必须持续影响后续行为。

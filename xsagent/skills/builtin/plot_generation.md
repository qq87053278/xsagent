---
name: plot_generation
version: "1.0"
description: 情节生成指令 — 根据大纲节点生成章节情节
type: plot_generation
variables:
  - outline_path
  - chapter_title
  - chapter_summary
  - plot_points
  - emotional_tone
  - previous_chapter_summary
---

## 情节约束

当前章节位置：**{{outline_path}}**

### 本章定位
- **标题**：{{chapter_title}}
- **摘要**：{{chapter_summary}}
- **情感基调**：{{emotional_tone}}

### 必须包含的情节点
{{plot_points}}

### 衔接要求
{{previous_chapter_summary}}

### 创作守则
1. 严格按摘要展开，不遗漏任何情节点。
2. 情感基调必须贯穿全章，转折需有铺垫。
3. 与前一章的衔接自然，时间、空间、人物状态保持一致。
4. 不得引入大纲外的新主线角色或重大事件，支线可适度展开但需可控。
5. 伏笔的埋设与回收要符合整体大纲安排。

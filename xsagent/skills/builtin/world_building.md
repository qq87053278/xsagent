---
name: world_building
version: "1.0"
description: 世界观约束指令 — 确保 AI 输出符合世界设定
skill_type: world_building
variables:
  - world_summary
  - world_name
  - world_rules
---

## 世界观约束

你正在为小说《{{world_name}}》创作内容。以下是世界观核心设定，你的输出必须严格遵守：

{{world_summary}}

### 核心规则
{{world_rules}}

### 创作守则
1. **不得违背** 上述任何规则，包括但不限于力量体系上限、科技水平、社会结构。
2. 出现新设定时，必须与已有世界观自洽；若存在模糊地带，优先保守处理，不擅自扩展。
3. 描写战斗、法术、科技时，严格参照力量体系的运作逻辑，避免战力崩坏。
4. 地理环境、势力分布、历史背景如与设定冲突，以设定为准。

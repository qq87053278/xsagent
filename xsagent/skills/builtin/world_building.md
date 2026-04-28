---
name: world_building
version: "1.1"
description: 世界观约束指令 — 确保 AI 输出符合世界设定
skill_type: world_building
variables:
  - world_name
  - world_genre
  - world_era
  - world_geography
  - world_history
  - world_power_system
  - world_society
  - world_rules
  - world_locations
  - world_factions
  - world_customs
  - world_notes
  - world_summary
---

## 世界观约束

你正在为小说《{{world_name}}》创作内容。以下是世界观核心设定，你的输出必须严格遵守：

### 基本信息
- **题材**: {{world_genre}}
- **时代背景**: {{world_era}}
- **世界名称**: {{world_name}}

{{world_summary}}

### 地理设定
{{world_geography}}

### 历史沿革
{{world_history}}

### 力量体系 / 科技水平
{{world_power_system}}

### 社会结构 / 势力分布
{{world_society}}

### 核心规则
{{world_rules}}

### 关键地点
{{world_locations}}

### 势力/组织
{{world_factions}}

### 风俗文化
{{world_customs}}

### 备忘
{{world_notes}}

### 创作守则
1. **不得违背** 上述任何规则，包括但不限于力量体系上限、科技水平、社会结构。
2. 出现新设定时，必须与已有世界观自洽；若存在模糊地带，优先保守处理，不擅自扩展。
3. 描写战斗、法术、科技时，严格参照力量体系的运作逻辑，避免战力崩坏。
4. 地理环境、势力分布、历史背景如与设定冲突，以设定为准。
5. 涉及特定地点或势力时，须与上述设定保持一致，不得擅自修改其性质或关系。

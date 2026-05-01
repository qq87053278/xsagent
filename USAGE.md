# XSAgent 使用文档

## 一、项目简介

XSAgent 是一套 AI 辅助小说创作系统。你负责设计创作流程、世界观、故事大纲与伏笔；大模型严格依据你设定的结构化 Skill 约束，自动生成章节内容、情节、对话与场景描写。

**核心定位**：人定框架，AI 填内容，Skill 文件锁边界。

---

## 二、环境安装

### 1. 系统要求
- Python 3.10+
- 可选：MySQL 5.7+（如需数据库持久化）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

依赖清单：
- `openai` — OpenAI API 调用
- `pyyaml` — YAML 配置解析
- `streamlit` — 可视化界面
- `pymysql` — MySQL 数据库连接

### 3. 配置 API 密钥

在环境变量中设置（推荐）：

```bash
# Windows PowerShell
$env:OPENAI_API_KEY="sk-xxxxxxxx"

# 或 Linux/macOS
export OPENAI_API_KEY="sk-xxxxxxxx"
```

也可直接写入 `config.yaml`（不推荐用于生产环境）：

```yaml
model:
  api_key: "sk-xxxxxxxx"
```

---

## 三、配置文件说明

`config.yaml` 为全局配置入口：

```yaml
model:
  backend: openai           # openai / azure_openai / anthropic / local
  model: gpt-4o             # 模型名称
  api_key: ""               # API Key（建议走环境变量）
  base_url: ""              # 自定义 API 地址（第三方中转）
  temperature: 0.7
  max_tokens: 7000
  timeout: 120

storage:
  backend: "json"           # json / mysql
  base_dir: "projects"      # JSON 模式存储目录
  auto_save: true
  mysql:                    # MySQL 配置（backend=mysql 时生效）
    host: "localhost"
    port: 3306
    user: "root"
    password: ""
    database: "xsagent"
    export_dir: "projects"

skills:
  load_builtin: true        # 是否加载内置 Skill
  custom_dirs: []           # 自定义 Skill 目录列表
```

---

## 四、快速开始

### 方式一：可视化界面（推荐）

```bash
streamlit run app.py
```

浏览器自动打开 `http://localhost:8501`。

**新建小说三步向导**：
1. **小说信息** — 输入名称、作者、题材、简介
2. **故事大纲** — 表单输入（`章节标题|摘要`，每行一章）或粘贴 JSON
3. **第一章情节** — 输入摘要、情节点、情感基调、出场人物、场景地点

完成后自动创建项目并进入创作界面。

### 方式二：命令行工具

```bash
# 创建演示项目（含示例世界观、人物、大纲）
python main.py quickstart

# 查看项目状态
python main.py status --project <项目ID>

# 生成第一章
python main.py generate chapter --project <项目ID> --seq 1 --stream
```

---

## 五、核心功能使用指南

### 5.1 世界观设定

进入 **世界观设定** 页面，填写：
- **世界名称、题材、时代背景**
- **地理设定、历史沿革**
- **力量体系 / 科技水平**（核心约束，AI 不可违背）
- **核心规则**（每行一条，如"跃迁不能在大质量天体引力井内进行"）
- **关键地点**（格式：`地名=描述`，每行一个）

保存后，这些信息会自动封装进世界观 Skill，作为 AI 生成的硬性约束。

### 5.2 人物设定

进入 **人物设定** 页面：
- **人物列表** — 查看已有角色卡
- **添加人物** — 填写姓名、角色定位（主角/配角/反派）、性格、动机、背景、人物弧线

人物信息会在生成章节时自动注入 `character_voice` Skill，确保角色言行不崩坏。

### 5.3 故事大纲

XSAgent 支持**卷/幕/章多级大纲**。

**导入方式**：
- 在 **故事大纲** 页面粘贴 JSON，格式示例：

```json
{
  "title": "第一卷：暗流",
  "level": 1,
  "summary": "卷摘要",
  "children": [
    {
      "title": "第一章：开端",
      "level": 3,
      "summary": "章节摘要",
      "plot_points": ["情节点1", "情节点2"],
      "characters_involved": [],
      "emotional_tone": "紧张"
    }
  ]
}
```

导入后系统自动同步生成章节占位。

### 5.4 伏笔设计（核心功能）

进入 **伏笔设计** 页面：

**第一步：创建伏笔**
- 填写伏笔名称、描述（读者最终看到什么）、埋设提示（可选）
- 设置重要性：`minor` / `medium` / `major` / `critical`

**第二步：绑定章节**
- 选择伏笔 → 选择章节 → 操作类型（埋设 / 回收）
- 点击绑定

**伏笔生命周期**：
```
PLANNED（已设计） → SEEDED（已埋设） → RESOLVED（已回收）
```

AI 生成章节时，会自动提取本章待埋设/回收的伏笔列表，通过 `foreshadowing` Skill 约束输出：
- 埋设要求：暗示自然融入，不突兀、不直白
- 回收要求：给予"原来如此"的顿悟感，避免机械填坑

### 5.5 风格设定

进入 **风格设定** 页面：

**基础风格**：
- 叙事视角、时态、整体语调、词汇风格、描写密度
- 禁用词（逗号分隔）
- 参考段落样例

**文笔模仿**：
1. 开启"启用文笔模仿模式"
2. 输入目标作者（如：金庸、古龙、刘慈欣）
3. 在"文笔模仿"标签页添加风格参考：
   - 参考名称、参考作者
   - 风格描述
   - 参考文本片段（粘贴名家段落）
4. 点击 **AI分析风格** — 系统自动从词汇、句式、描写、对话、节奏五个维度提取特征

生成时，`style_mimicry` Skill 会注入模仿守则，要求 AI 贴合目标调性但不抄袭原句。

### 5.6 章节创作（核心页面）

进入 **章节创作** 页面，三栏布局：

**左栏 — 情节流程**
- 编辑本章摘要、情节点、情感基调
- 选择出场人物（从已创建人物中勾选）

**中栏 — 伏笔绑定与风格确认**
- 勾选本章要**埋设**的伏笔（仅显示 PLANNED 状态）
- 勾选本章要**回收**的伏笔（仅显示 SEEDED 状态）
- 查看当前风格设定与模仿目标

**右栏 — 内容生成与编辑**
- 调整生成温度（0.0-1.0）与最大 Token 数
- 点击 **生成章节** — 流式输出，实时可见
- 在编辑框中微调正文
- 点击 **保存正文** — 自动统计字数
- 点击 **审校通过** — 标记为 COMPLETED

**生成原理**：
点击生成时，系统会自动组装一份完整提示词，包含：
1. 世界观约束（Skill: world_building）
2. 情节约束（Skill: plot_generation）
3. 人物约束（Skill: character_voice）
4. 风格约束（Skill: style_guidance）
5. 伏笔约束（Skill: foreshadowing）
6. 文笔模仿（Skill: style_mimicry）
7. 输出格式（Skill: output_format）

---

## 六、MySQL 存储配置

### 1. 创建数据库

```sql
CREATE DATABASE xsagent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. 修改配置

```yaml
storage:
  backend: "mysql"
  mysql:
    host: "localhost"
    port: 3306
    user: "root"
    password: "你的密码"
    database: "xsagent"
```

### 3. 启动系统

```bash
streamlit run app.py
```

首次连接时，`MySQLStorage` 会自动创建所需数据表（novels、chapters、characters、foreshadowings、style_refs），无需手动执行建表脚本。

### 4. 表结构速查

| 表名 | 说明 |
|---|---|
| `novels` | 小说主信息 + world/outline/style 等 JSON |
| `chapters` | 章节正文、状态、出场人物、伏笔绑定、生成历史 |
| `characters` | 人物数据 JSON |
| `foreshadowings` | 伏笔名称、状态、重要性、埋设/回收章节ID |
| `style_refs` | 风格参考名称、作者、启用状态 |

**注意**：即使使用 MySQL，系统仍会同时保留一份 JSON 备份到 `export_dir` 目录，便于迁移。

---

## 七、数据备份与导出

### 导出完整小说

在 **导出小说** 页面选择格式（txt / md），点击导出后可下载全文文件。

### CLI 导出

```bash
python main.py export --project <项目ID> --format md
```

### JSON 备份

无论使用 JSON 还是 MySQL 存储，项目数据均以 JSON 形式保存在 `projects/<项目ID>/project.json`，可直接复制备份。

---

## 八、文件结构速查

```
xsagent/
├── config.yaml              # 全局配置
├── requirements.txt         # Python 依赖
├── app.py                   # Streamlit 可视化界面（入口）
├── main.py                  # CLI 命令行入口
├── USAGE.md                 # 本文档
├── xsagent/
│   ├── core/models.py       # 数据模型（NovelProject/Chapter/Character/Foreshadowing/StyleReference）
│   ├── skills/
│   │   ├── skill_parser.py  # Skill 文件解析器
│   │   ├── skill_registry.py
│   │   └── builtin/         # 内置 Skill
│   │       ├── world_building.md
│   │       ├── plot_generation.md
│   │       ├── character_voice.md
│   │       ├── style_guidance.md
│   │       ├── foreshadowing.md
│   │       ├── style_mimicry.md
│   │       └── output_format.md
│   ├── generator/
│   │   ├── base.py          # 生成器基类
│   │   ├── openai_adapter.py
│   │   └── prompt_builder.py # 提示词组装器（核心）
│   ├── storage/
│   │   ├── json_storage.py  # JSON 文件存储
│   │   └── mysql_storage.py # MySQL 数据库存储
│   └── workflow/pipeline.py # 创作工作流引擎
└── projects/                # 项目数据目录（JSON 模式）
```

---

## 九、常见问题

**Q: 为什么生成内容偏离了世界观设定？**
A: 检查【世界观设定】是否已保存，且核心规则是否写入了 `rules` 字段。规则每行一条，AI 会通过 `world_building` Skill 强制执行。

**Q: 人物对话风格不一致怎么办？**
A: 在【人物设定】中完善每个人的性格、动机、人物弧线。生成时系统会通过 `character_voice` Skill 注入约束，要求 AI 根据性格区分台词风格。

**Q: 伏笔埋设太明显，读者一眼看穿？**
A: `foreshadowing` Skill 明确要求"暗示必须自然融入情节，不突兀、不直白，读者初次阅读时不易察觉"。你也可以在伏笔的"埋设提示"中补充更具体的暗示方式。

**Q: 可以切换存储后端而不丢失数据吗？**
A: 可以。MySQL 模式下系统仍会在 `projects/` 目录保留 JSON 备份。如需从 JSON 迁移到 MySQL，将 `backend` 改为 `mysql` 后重新加载项目并保存一次即可自动入库。

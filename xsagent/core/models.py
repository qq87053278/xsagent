"""
XSAgent - 核心数据模型
定义小说创作系统中所有结构化数据的 Schema
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any


class CharacterRole(str, Enum):
    """人物角色类型"""
    PROTAGONIST = "protagonist"      # 主角
    DEUTERAGONIST = "deuteragonist"  # 配角/第二主角
    ANTAGONIST = "antagonist"        # 反派
    SUPPORTING = "supporting"        # 次要角色
    MINOR = "minor"                  # 龙套


class ChapterStatus(str, Enum):
    """章节创作状态"""
    PLANNED = "planned"              # 已规划
    OUTLINED = "outlined"            # 已写大纲
    WRITING = "writing"              # 生成中
    REVIEW = "review"                # 待审校
    COMPLETED = "completed"          # 已完成


class ForeshadowingStatus(str, Enum):
    """伏笔生命周期状态"""
    PLANNED = "planned"              # 已设计，尚未埋设
    SEEDED = "seeded"                # 已在某章埋设
    RESOLVED = "resolved"            # 已在某章回收/呼应
    ABANDONED = "abandoned"          # 已废弃


class BranchStatus(str, Enum):
    """分支剧情状态"""
    OPEN = "open"                    # 已开启，待推进
    IN_PROGRESS = "in_progress"      # 正在推进中
    RESOLVED = "resolved"            # 已收束/完结
    ABANDONED = "abandoned"          # 已废弃


class LocationStatus(str, Enum):
    """地点状态"""
    ACTIVE = "active"                # 正常存在
    DESTROYED = "destroyed"          # 已毁灭
    HIDDEN = "hidden"                # 隐藏/秘密
    LOST = "lost"                    # 已失落/不可达
    UNDER_CONSTRUCTION = "under_construction"  # 建造中


class FactionStatus(str, Enum):
    """势力状态"""
    ACTIVE = "active"                # 活跃
    DISSOLVED = "dissolved"          # 已解散
    HIDDEN = "hidden"                # 隐秘
    AT_WAR = "at_war"                # 交战中
    DECLINING = "declining"          # 衰落中
    RISING = "rising"                # 崛起中


class ItemStatus(str, Enum):
    """物品状态"""
    NOTHING = "nothing"              # 无状态
    ACTIVE = "active"                # 正常存在/使用中
    LOST = "lost"                    # 已遗失
    DESTROYED = "destroyed"          # 已损毁
    SEALED = "sealed"                # 封印中
    DORMANT = "dormant"              # 潜伏/未觉醒


@dataclass
class Character:
    """人物设定卡片"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""                          # 姓名
    alias: List[str] = field(default_factory=list)  # 别名/称号
    role: CharacterRole = CharacterRole.SUPPORTING
    age: Optional[int] = None
    gender: Optional[str] = None
    appearance: str = ""                    # 外貌描写
    personality: str = ""                   # 性格特征
    background: str = ""                    # 身世背景
    motivation: str = ""                    # 核心动机/目标
    arc: str = ""                           # 人物弧线（成长轨迹）
    relationships: Dict[str, str] = field(default_factory=dict)  # 关系网 {角色名: 关系}
    abilities: List[str] = field(default_factory=list)  # 能力/技能
    spells_skills: str = ""                 # 法术/技能详细描述
    faction_id: Optional[str] = None        # 核心绑定势力ID
    faction_notes: str = ""                 # 势力关系描述（多势力时记录其他势力）
    notes: str = ""                         # 备忘笔记
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["role"] = self.role.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Character":
        data = dict(data)
        data["role"] = CharacterRole(data.get("role", "supporting"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class WorldBuilding:
    """世界观设定"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""                          # 世界名称
    genre: str = ""                         # 题材类型（玄幻/科幻/都市...）
    era: str = ""                           # 时代背景
    geography: str = ""                     # 地理设定
    history: str = ""                       # 历史沿革
    power_system: str = ""                  # 力量体系/科技水平
    society: str = ""                       # 社会结构/势力分布
    rules: List[str] = field(default_factory=list)  # 核心规则（如魔法限制）
    locations: Dict[str, str] = field(default_factory=dict)  # 关键地点 {地名: 描述}
    factions: Dict[str, str] = field(default_factory=dict)   # 势力/组织 {名称: 描述}
    customs: List[str] = field(default_factory=list)  # 风俗文化
    notes: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldBuilding":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Foreshadowing:
    """伏笔设计 — 支持全生命周期管理"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""                       # 伏笔名称/代号
    description: str = ""                # 伏笔内容描述
    hint_text: str = ""                  # 埋设时的暗示文本（可留空由AI生成）
    seed_chapter_id: Optional[str] = None      # 埋设章节ID
    resolve_chapter_id: Optional[str] = None   # 回收章节ID
    status: ForeshadowingStatus = ForeshadowingStatus.PLANNED
    importance: str = "medium"           # 重要性: minor / medium / major / critical
    related_characters: List[str] = field(default_factory=list)  # 关联角色ID
    related_plotlines: List[str] = field(default_factory=list)   # 关联支线
    notes: str = ""                      # 备忘

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Foreshadowing":
        data = dict(data)
        data["status"] = ForeshadowingStatus(data.get("status", "planned"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Location:
    """地点 — 支持层级管理与状态追踪"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""                        # 地点名称
    description: str = ""                 # 地点描述
    status: LocationStatus = LocationStatus.ACTIVE
    level: str = "normal"                 # 级别: minor / normal / important / core / sacred
    hierarchy: str = ""                   # 层级位置，如"东方大陆 > 青云国 > 京城"
    scale: str = ""                       # 规模: 小型村落 / 中型城市 / 大型宗门 等
    parent_location_id: Optional[str] = None  # 父地点ID
    tags: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Location":
        data = dict(data)
        data["status"] = LocationStatus(data.get("status", "active"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Faction:
    """势力/组织 — 支持地点绑定与状态追踪"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""                        # 势力名称
    description: str = ""                 # 势力描述
    status: FactionStatus = FactionStatus.ACTIVE
    level: str = "normal"                 # 级别: minor / normal / important / major / supreme
    location_id: Optional[str] = None     # 绑定地点ID
    leader_character_id: Optional[str] = None  # 首领人物ID
    tags: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Faction":
        data = dict(data)
        data["status"] = FactionStatus(data.get("status", "active"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Item:
    """物品定义 — 法宝/武器/丹药/材料/宝物等"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""                        # 物品名称
    description: str = ""                 # 物品描述
    item_type: str = "artifact"           # 类型: artifact法宝 / weapon武器 / armor护具 / consumable消耗品 / material材料 / treasure宝物 / other其他
    grade: str = "normal"                 # 品级: trash垃圾 / common普通 / uncommon优秀 / rare稀有 / epic史诗 / legendary传说 / divine神器
    effects: str = ""                     # 功效/能力描述
    origin: str = ""                      # 来源/出处
    owner_character_id: Optional[str] = None  # 当前持有者角色ID
    location_id: Optional[str] = None     # 所在地点ID
    status: ItemStatus = ItemStatus.ACTIVE
    tags: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Item":
        data = dict(data)
        data["status"] = ItemStatus(data.get("status", "active"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class StyleReference:
    """文笔风格参考 — 支持知名作者模仿"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""                       # 参考名称（如"金庸武侠风"）
    reference_author: str = ""           # 参考作者名
    description: str = ""                # 风格描述
    sample_texts: List[str] = field(default_factory=list)  # 参考文本片段
    analyzed_traits: List[str] = field(default_factory=list)  # AI分析出的特征标签
    vocabulary_notes: str = ""           # 词汇偏好说明
    sentence_patterns: str = ""          # 句式特点说明
    rhythm_description: str = ""         # 节奏感描述
    dialogue_style: str = ""             # 对话风格
    is_active: bool = True               # 是否启用

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StyleReference":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class BranchPlot:
    """分支剧情 — 章节中产生的可延续支线"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""                       # 分支名称
    description: str = ""                 # 分支描述/触发事件
    status: BranchStatus = BranchStatus.OPEN
    origin_chapter_id: Optional[str] = None   # 起源章节ID
    progress_chapter_ids: List[str] = field(default_factory=list)  # 推进过的章节ID
    importance: str = "medium"            # 重要性: minor / medium / major
    notes: str = ""                       # 进展记录/备忘
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BranchPlot":
        data = dict(data)
        data["status"] = BranchStatus(data.get("status", "open"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class OutlineNode:
    """大纲节点 — 支持总纲/卷/幕/章多级嵌套"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""                         # 节点标题
    level: int = 0                          # 层级 0=总纲 1=卷 2=幕 3=章
    summary: str = ""                       # 内容摘要
    plot_points: List[str] = field(default_factory=list)  # 关键情节点
    characters_involved: List[str] = field(default_factory=list)  # 涉及角色ID
    locations: List[str] = field(default_factory=list)  # 场景地点
    emotional_tone: str = ""                # 情感基调
    foreshadowing: List[str] = field(default_factory=list)      # 文本级伏笔描述（兼容旧版）
    foreshadowing_ids: List[str] = field(default_factory=list)  # 关联的伏笔ID列表
    callbacks: List[str] = field(default_factory=list)          # 呼应回收
    children: List["OutlineNode"] = field(default_factory=list)  # 子节点
    chapter_id: Optional[str] = None        # 关联的章节ID（仅 level=3）
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["children"] = [c.to_dict() for c in self.children]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OutlineNode":
        data = dict(data)
        children_data = data.pop("children", [])
        node = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        node.children = [cls.from_dict(c) for c in children_data]
        return node

    LEVEL_NAMES = {0: "总纲", 1: "卷", 2: "幕", 3: "章"}

    @property
    def level_name(self) -> str:
        return self.LEVEL_NAMES.get(self.level, "未知")

    def flatten_chapters(self) -> List["OutlineNode"]:
        """展平所有 level=3 的章节节点"""
        result = []
        if self.level == 3:
            result.append(self)
        for child in self.children:
            result.extend(child.flatten_chapters())
        return result


@dataclass
class StyleGuide:
    """写作风格要求"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "default"
    narrative_perspective: str = "third_person_limited"  # 视角
    tense: str = "past"                     # 时态
    tone: str = ""                          # 整体语调
    sentence_rhythm: str = ""               # 句式节奏偏好
    vocabulary_level: str = ""              # 词汇风格（古雅/通俗/华丽）
    dialogue_style: str = ""                # 对话风格
    description_density: str = "balanced"   # 描写密度
    pacing_preference: str = ""             # 节奏偏好
    banned_words: List[str] = field(default_factory=list)  # 禁用词
    signature_phrases: List[str] = field(default_factory=list)  # 标志性用语
    sample_paragraph: str = ""              # 参考段落样例
    mimicry_mode: bool = False              # 是否启用文笔模仿模式
    reference_author: str = ""              # 目标模仿作者名
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StyleGuide":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Chapter:
    """章节内容"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    sequence_number: int = 0                # 序号
    outline_summary: str = ""               # 大纲摘要
    content: str = ""                       # 正文内容
    status: ChapterStatus = ChapterStatus.PLANNED
    characters_present: List[str] = field(default_factory=list)  # 出场角色ID
    locations: List[str] = field(default_factory=list)           # 场景地点
    word_count: int = 0
    foreshadowing_seeded: List[str] = field(default_factory=list)    # 本章埋下的伏笔ID
    foreshadowing_resolved: List[str] = field(default_factory=list)  # 本章回收的伏笔ID
    generation_history: List[Dict[str, Any]] = field(default_factory=list)  # 生成记录
    plot_memory: str = ""                   # AI分析后的剧情记忆（关键情节/人物状态/地点）
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Chapter":
        data = dict(data)
        data["status"] = ChapterStatus(data.get("status", "planned"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def estimate_word_count(self) -> int:
        """估算中文字数"""
        if not self.content:
            return 0
        import re
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', self.content))
        return chinese_chars


@dataclass
class GenerationContext:
    """
    生成上下文 — 封装所有约束信息，传给 AI 作为核心指令依据
    这是确保 AI 输出贴合设定的关键数据结构
    """
    project_title: str = ""
    relevant_characters: List[Dict[str, Any]] = field(default_factory=list)
    outline_path: List[str] = field(default_factory=list)  # 当前节点路径 [卷, 幕, 章]
    current_node: Optional[OutlineNode] = None
    volume_summary: str = ""                # 所属卷的摘要（轻度影响）
    act_summary: str = ""                   # 所属幕的摘要（高度影响）
    previous_chapter_summary: str = ""      # 前一章摘要（保证衔接）
    style_directives: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)     # 硬性约束
    references: List[str] = field(default_factory=list)      # 参考文本片段
    skill_directives: Dict[str, str] = field(default_factory=dict)  # Skill 注入的指令
    foreshadowing_directives: List[str] = field(default_factory=list)  # 伏笔指令
    style_references: List[Dict[str, Any]] = field(default_factory=list)  # 风格参考数据
    mimicry_mode: bool = False
    reference_author: str = ""
    previous_chapter_content: str = ""        # 前一章结尾片段（用于衔接）
    previous_chapter_plot_memory: str = ""    # 前一章的剧情记忆
    previous_plot_memories: List[str] = field(default_factory=list)  # 前2-5章的剧情记忆
    next_chapter_summary: str = ""                # 下一章摘要（预告方向）
    branch_directives: List[str] = field(default_factory=list)  # 分支剧情指令

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "project_title": self.project_title,
            "relevant_characters": self.relevant_characters,
            "outline_path": self.outline_path,
            "current_node": self.current_node.to_dict() if self.current_node else None,
            "volume_summary": self.volume_summary,
            "act_summary": self.act_summary,
            "previous_chapter_summary": self.previous_chapter_summary,
            "previous_chapter_content": self.previous_chapter_content,
            "previous_chapter_plot_memory": self.previous_chapter_plot_memory,
            "style_directives": self.style_directives,
            "constraints": self.constraints,
            "references": self.references,
            "skill_directives": self.skill_directives,
            "foreshadowing_directives": self.foreshadowing_directives,
            "style_references": self.style_references,
            "mimicry_mode": self.mimicry_mode,
            "reference_author": self.reference_author,
            "previous_plot_memories": self.previous_plot_memories,
            "next_chapter_summary": self.next_chapter_summary,
            "branch_directives": self.branch_directives,
        }
        return data


@dataclass
class NovelProject:
    """小说项目 — 聚合所有创作要素"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = "未命名小说"
    author: str = ""
    description: str = ""
    world: Optional[WorldBuilding] = None
    outline: Optional[OutlineNode] = None
    characters: Dict[str, Character] = field(default_factory=dict)  # {id: Character}
    chapters: Dict[str, Chapter] = field(default_factory=dict)      # {id: Chapter}
    style: StyleGuide = field(default_factory=StyleGuide)
    skill_bindings: Dict[str, str] = field(default_factory=dict)    # {skill_type: skill_name}
    foreshadowings: Dict[str, Foreshadowing] = field(default_factory=dict)  # {id: Foreshadowing}
    style_references: Dict[str, StyleReference] = field(default_factory=dict)  # {id: StyleReference}
    branch_plots: Dict[str, BranchPlot] = field(default_factory=dict)  # {id: BranchPlot}
    locations: Dict[str, Location] = field(default_factory=dict)  # {id: Location}
    factions: Dict[str, Faction] = field(default_factory=dict)  # {id: Faction}
    items: Dict[str, Item] = field(default_factory=dict)  # {id: Item}
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "description": self.description,
            "world": self.world.to_dict() if self.world else None,
            "outline": self.outline.to_dict() if self.outline else None,
            "characters": {k: v.to_dict() for k, v in self.characters.items()},
            "chapters": {k: v.to_dict() for k, v in self.chapters.items()},
            "style": self.style.to_dict(),
            "skill_bindings": self.skill_bindings,
            "foreshadowings": {k: v.to_dict() for k, v in self.foreshadowings.items()},
            "style_references": {k: v.to_dict() for k, v in self.style_references.items()},
            "branch_plots": {k: v.to_dict() for k, v in self.branch_plots.items()},
            "locations": {k: v.to_dict() for k, v in self.locations.items()},
            "factions": {k: v.to_dict() for k, v in self.factions.items()},
            "items": {k: v.to_dict() for k, v in self.items.items()},
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NovelProject":
        data = dict(data)
        world_data = data.pop("world", None)
        outline_data = data.pop("outline", None)
        characters_data = data.pop("characters", {})
        chapters_data = data.pop("chapters", {})
        style_data = data.pop("style", {})
        foreshadowings_data = data.pop("foreshadowings", {})
        style_refs_data = data.pop("style_references", {})
        branch_plots_data = data.pop("branch_plots", {})
        locations_data = data.pop("locations", {})
        factions_data = data.pop("factions", {})
        items_data = data.pop("items", {})

        project = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        if world_data:
            project.world = WorldBuilding.from_dict(world_data)
            # 兼容旧数据：将 world.locations (Dict[str,str]) 迁移为独立 Location 对象
            if project.world and project.world.locations and not locations_data:
                for loc_name, loc_desc in project.world.locations.items():
                    loc = Location(name=loc_name, description=loc_desc)
                    project.locations[loc.id] = loc
            # 兼容旧数据：将 world.factions (Dict[str,str]) 迁移为独立 Faction 对象
            if project.world and project.world.factions and not factions_data:
                for fac_name, fac_desc in project.world.factions.items():
                    fac = Faction(name=fac_name, description=fac_desc)
                    project.factions[fac.id] = fac
        if outline_data:
            # 兼容旧数据：如果根节点 level != 0，自动包装为总纲
            if outline_data.get("level", 0) != 0:
                old_root = dict(outline_data)
                outline_data = {
                    "id": str(uuid.uuid4())[:8],
                    "title": "全书总纲",
                    "level": 0,
                    "summary": "",
                    "plot_points": [],
                    "characters_involved": [],
                    "locations": [],
                    "emotional_tone": "",
                    "foreshadowing": [],
                    "foreshadowing_ids": [],
                    "callbacks": [],
                    "children": [old_root],
                    "chapter_id": None,
                    "notes": "",
                }
            project.outline = OutlineNode.from_dict(outline_data)
        # 兼容旧数据：如果 characters/chapters 被存为 list 而非 dict，自动转换
        if isinstance(characters_data, list):
            characters_data = {c.get("id", str(uuid.uuid4())[:8]): c for c in characters_data}
        if isinstance(chapters_data, list):
            chapters_data = {c.get("id", str(uuid.uuid4())[:8]): c for c in chapters_data}
        project.characters = {k: Character.from_dict(v) for k, v in characters_data.items()}
        project.chapters = {k: Chapter.from_dict(v) for k, v in chapters_data.items()}
        project.style = StyleGuide.from_dict(style_data)
        project.foreshadowings = {k: Foreshadowing.from_dict(v) for k, v in foreshadowings_data.items()}
        project.style_references = {k: StyleReference.from_dict(v) for k, v in style_refs_data.items()}
        project.branch_plots = {k: BranchPlot.from_dict(v) for k, v in branch_plots_data.items()}
        project.locations = {k: Location.from_dict(v) for k, v in locations_data.items()}
        project.factions = {k: Faction.from_dict(v) for k, v in factions_data.items()}
        project.items = {k: Item.from_dict(v) for k, v in items_data.items()}
        return project

    def get_character(self, character_id: str) -> Optional[Character]:
        return self.characters.get(character_id)

    def get_chapter(self, chapter_id: str) -> Optional[Chapter]:
        return self.chapters.get(chapter_id)

    def get_chapter_sequence(self) -> List[Chapter]:
        """按序号排序获取所有章节"""
        return sorted(self.chapters.values(), key=lambda c: c.sequence_number)

    def build_generation_context(self, chapter_id: str) -> GenerationContext:
        """
        为指定章节构建完整的生成上下文
        """
        chapter = self.chapters.get(chapter_id)
        if not chapter:
            raise ValueError(f"章节不存在: {chapter_id}")

        ctx = GenerationContext()
        ctx.project_title = self.title

        # 世界观摘要

        # 相关角色
        for cid in chapter.characters_present:
            char = self.characters.get(cid)
            if char:
                ctx.relevant_characters.append({
                    "name": char.name,
                    "role": char.role.value,
                    "personality": char.personality,
                    "motivation": char.motivation,
                    "current_arc": char.arc,

                })

        # 大纲路径与当前节点
        if self.outline:
            flat = self.outline.flatten_chapters()
            for node in flat:
                if node.chapter_id == chapter_id:
                    ctx.current_node = node
                    ctx.outline_path = self._trace_outline_path(node)
                    # 提取所属卷和幕的摘要
                    path_nodes = self._trace_outline_path_nodes(node)
                    for pn in path_nodes:
                        if pn.level == 1:
                            ctx.volume_summary = pn.summary
                        elif pn.level == 2:
                            ctx.act_summary = pn.summary
                    break
            # fallback: 若通过 chapter_id 未匹配到（如手动添加的章节），尝试多种方式匹配
            if not ctx.current_node:
                ch = self.chapters.get(chapter_id)
                if ch:
                    # 1. 精确标题匹配
                    for node in flat:
                        if node.title == ch.title:
                            ctx.current_node = node
                            ctx.outline_path = self._trace_outline_path(node)
                            path_nodes = self._trace_outline_path_nodes(node)
                            for pn in path_nodes:
                                if pn.level == 1:
                                    ctx.volume_summary = pn.summary
                                elif pn.level == 2:
                                    ctx.act_summary = pn.summary
                            node.chapter_id = chapter_id
                            break
                    # 2. 如果只有一个章节节点，直接匹配
                    if not ctx.current_node and len(flat) == 1:
                        ctx.current_node = flat[0]
                        ctx.outline_path = self._trace_outline_path(flat[0])
                        path_nodes = self._trace_outline_path_nodes(flat[0])
                        for pn in path_nodes:
                            if pn.level == 1:
                                ctx.volume_summary = pn.summary
                            elif pn.level == 2:
                                ctx.act_summary = pn.summary
                        flat[0].chapter_id = chapter_id
                    # 3. 模糊标题匹配（互相包含）
                    if not ctx.current_node:
                        ch_title_clean = ch.title.strip()
                        for node in flat:
                            node_title_clean = node.title.strip()
                            if node_title_clean in ch_title_clean or ch_title_clean in node_title_clean:
                                ctx.current_node = node
                                ctx.outline_path = self._trace_outline_path(node)
                                path_nodes = self._trace_outline_path_nodes(node)
                                for pn in path_nodes:
                                    if pn.level == 1:
                                        ctx.volume_summary = pn.summary
                                    elif pn.level == 2:
                                        ctx.act_summary = pn.summary
                                node.chapter_id = chapter_id
                                break

        # 前一章摘要
        seq = self.get_chapter_sequence()
        current_idx = -1
        for i, ch in enumerate(seq):
            if ch.id == chapter_id:
                current_idx = i
                break

        if current_idx > 0:
            prev = seq[current_idx - 1]
            ctx.previous_chapter_summary = f"第{prev.sequence_number}章《{prev.title}》: {prev.outline_summary}"
            # 前一章剧情记忆 + 结尾片段，双重衔接保障
            if prev.plot_memory:
                ctx.previous_chapter_plot_memory = prev.plot_memory
            if prev.content:
                # 取最后 800 字作为衔接上下文
                tail = prev.content[-800:] if len(prev.content) > 800 else prev.content
                ctx.previous_chapter_content = tail

        # 下一章摘要（如果存在）
        if current_idx >= 0 and current_idx < len(seq) - 1:
            next_ch = seq[current_idx + 1]
            if next_ch.outline_summary:
                ctx.next_chapter_summary = f"第{next_ch.sequence_number}章《{next_ch.title}》: {next_ch.outline_summary}"

        # 前2-5章的剧情记忆（前一章用完整正文，所以这取更前面的4章）
        if current_idx > 1:
            start_idx = max(0, current_idx - 5)
            for prev_ch in seq[start_idx:current_idx - 1]:
                if prev_ch.plot_memory:
                    ctx.previous_plot_memories.append(
                        f"第{prev_ch.sequence_number}章《{prev_ch.title}》: {prev_ch.plot_memory}"
                    )

        # 风格指令
        style = self.style
        ctx.style_directives = [
            f"叙事视角: {style.narrative_perspective}",
            f"时态: {style.tense}",
            f"整体语调: {style.tone}",
            f"词汇风格: {style.vocabulary_level}",
            f"描写密度: {style.description_density}",
        ]
        if style.sample_paragraph:
            ctx.style_directives.append(f"参考样例: {style.sample_paragraph[:300]}")

        # 伏笔指令 — 本章需埋设与回收的伏笔
        if self.foreshadowings:
            to_seed = []
            to_resolve = []
            for fid in chapter.foreshadowing_seeded:
                fs = self.foreshadowings.get(fid)
                if fs and fs.status == ForeshadowingStatus.PLANNED:
                    to_seed.append(f"- [{fs.importance}] {fs.name}: {fs.description}")
            for fid in chapter.foreshadowing_resolved:
                fs = self.foreshadowings.get(fid)
                if fs and fs.status == ForeshadowingStatus.SEEDED:
                    to_resolve.append(f"- [{fs.importance}] {fs.name}: {fs.description}")
            if to_seed:
                ctx.foreshadowing_directives.append("【本章需埋设的伏笔】")
                ctx.foreshadowing_directives.extend(to_seed)
                ctx.foreshadowing_directives.append("埋设要求：暗示必须自然融入情节，不突兀、不直白，读者初次阅读时不易察觉。")
            if to_resolve:
                ctx.foreshadowing_directives.append("【本章需回收的伏笔】")
                ctx.foreshadowing_directives.extend(to_resolve)
                ctx.foreshadowing_directives.append("回收要求：呼应前文埋设的线索，给予合理解释或情感冲击，避免机械式填坑。")

        # 风格参考 — 文笔模仿
        active_refs = [r for r in self.style_references.values() if r.is_active]
        if active_refs:
            ctx.style_references = [r.to_dict() for r in active_refs]
        if style.mimicry_mode:
            ctx.mimicry_mode = True
            ctx.reference_author = style.reference_author

        # 分支剧情指令 — 本章需推进/呼应的活跃分支
        if self.branch_plots:
            active_branches = [
                b for b in self.branch_plots.values()
                if b.status in (BranchStatus.OPEN, BranchStatus.IN_PROGRESS)
            ]
            if active_branches:
                progressed = []
                referenced = []
                for branch in active_branches:
                    if chapter_id in branch.progress_chapter_ids:
                        progressed.append(
                            f"- [{branch.importance}] {branch.title}: {branch.description}"
                        )
                    else:
                        referenced.append(
                            f"- [{branch.importance}] {branch.title}: {branch.description}"
                        )
                if progressed:
                    ctx.branch_directives.append("【本章需推进的分支剧情】")
                    ctx.branch_directives.extend(progressed)
                    ctx.branch_directives.append("推进要求：在本章中让该分支有实质性进展，可以是触发新事件、揭示线索、改变人物关系等，避免一笔带过。")
                if referenced:
                    ctx.branch_directives.append("【本章需呼应的活跃分支】")
                    ctx.branch_directives.extend(referenced)
                    ctx.branch_directives.append("呼应要求：在合适的地方提及或暗示这些分支的存在，保持读者记忆，但不要喧宾夺主。")

        return ctx

    def _trace_outline_path(self, target: OutlineNode) -> List[str]:
        """追溯大纲路径（返回标题列表）"""
        def search(node: OutlineNode, path: List[str]) -> Optional[List[str]]:
            current = path + [node.title]
            if node.id == target.id:
                return current
            for child in node.children:
                result = search(child, current)
                if result:
                    return result
            return None
        if self.outline:
            return search(self.outline, []) or []
        return []

    def _trace_outline_path_nodes(self, target: OutlineNode) -> List[OutlineNode]:
        """追溯大纲路径（返回节点列表）"""
        def search(node: OutlineNode, path: List[OutlineNode]) -> Optional[List[OutlineNode]]:
            current = path + [node]
            if node.id == target.id:
                return current
            for child in node.children:
                result = search(child, current)
                if result:
                    return result
            return None
        if self.outline:
            return search(self.outline, []) or []
        return []

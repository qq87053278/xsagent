"""
创作工作流引擎 — 编排小说创作的完整流程
提供高阶 API 供 CLI / GUI 调用
"""

import json
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime

from xsagent.core.models import (
    NovelProject, Chapter, ChapterStatus, Character, WorldBuilding,
    OutlineNode, StyleGuide, CharacterRole, Foreshadowing, ForeshadowingStatus,
    StyleReference, BranchPlot, BranchStatus,
    Location, LocationStatus, Faction, FactionStatus,
    Item, ItemStatus
)
from xsagent.generator.base import BaseGenerator, GenerationRequest, create_request
from xsagent.generator.prompt_builder import PromptBuilder
from xsagent.skills.skill_registry import SkillRegistry
from xsagent.storage.json_storage import JSONStorage
from xsagent.utils.helpers import count_chinese_words


class CreationPipeline:
    """
    小说创作工作流管道
    封装从项目初始化到章节生成的完整流程
    """

    def __init__(
        self,
        storage: Optional[JSONStorage] = None,
        skill_registry: Optional[SkillRegistry] = None,
        generator: Optional[BaseGenerator] = None,
    ):
        self.storage = storage or JSONStorage()
        self.skills = skill_registry or SkillRegistry()
        self.generator = generator
        self.prompt_builder = PromptBuilder(self.skills)

    def initialize_project(
        self,
        title: str,
        author: str = "",
        description: str = "",
        world: Optional[WorldBuilding] = None,
        style: Optional[StyleGuide] = None,
    ) -> NovelProject:
        """初始化一个新小说项目"""
        project = NovelProject(
            title=title,
            author=author,
            description=description,
            world=world,
            style=style or StyleGuide(),
        )
        self.storage.save(project)
        return project

    def add_character(
        self,
        project: NovelProject,
        name: str,
        role: CharacterRole = CharacterRole.SUPPORTING,
        **kwargs
    ) -> Character:
        """为项目添加人物"""
        char = Character(name=name, role=role, **kwargs)
        project.characters[char.id] = char
        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)
        return char

    def add_world_setting(
        self,
        project: NovelProject,
        name: str,
        **kwargs
    ) -> WorldBuilding:
        """为项目设置/更新世界观"""
        world = WorldBuilding(name=name, **kwargs)
        project.world = world
        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)
        return world

    def add_chapter(
        self,
        project: NovelProject,
        title: str,
        outline_summary: str = "",
        sequence_number: Optional[int] = None,
    ) -> Chapter:
        """为项目手动添加一个章节（不依赖大纲同步）"""
        if sequence_number is None:
            sequence_number = max(
                (c.sequence_number for c in project.chapters.values()), default=0
            ) + 1
        else:
            # 避免序号冲突，自动递增到可用序号
            existing_seqs = {c.sequence_number for c in project.chapters.values()}
            while sequence_number in existing_seqs:
                sequence_number += 1
        ch = Chapter(
            title=title,
            sequence_number=sequence_number,
            outline_summary=outline_summary,
            status=ChapterStatus.PLANNED,
        )
        project.chapters[ch.id] = ch
        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)
        return ch

    def add_foreshadowing(
        self,
        project: NovelProject,
        name: str,
        description: str,
        importance: str = "medium",
        hint_text: str = "",
        related_characters: Optional[List[str]] = None,
        related_plotlines: Optional[List[str]] = None,
    ) -> Foreshadowing:
        """为项目添加伏笔设计"""
        fs = Foreshadowing(
            name=name,
            description=description,
            importance=importance,
            hint_text=hint_text,
            related_characters=related_characters or [],
            related_plotlines=related_plotlines or [],
        )
        project.foreshadowings[fs.id] = fs
        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)
        return fs

    def bind_foreshadowing_to_chapter(
        self,
        project: NovelProject,
        foreshadowing_id: str,
        chapter_id: str,
        action: str,  # "seed" or "resolve"
    ) -> None:
        """将伏笔绑定到章节（埋设或回收）"""
        fs = project.foreshadowings.get(foreshadowing_id)
        chapter = project.chapters.get(chapter_id)
        if not fs or not chapter:
            raise ValueError("伏笔或章节不存在")

        if action == "seed":
            chapter.foreshadowing_seeded.append(foreshadowing_id)
            fs.seed_chapter_id = chapter_id
            if fs.status == ForeshadowingStatus.PLANNED:
                fs.status = ForeshadowingStatus.SEEDED
        elif action == "resolve":
            chapter.foreshadowing_resolved.append(foreshadowing_id)
            fs.resolve_chapter_id = chapter_id
            if fs.status == ForeshadowingStatus.SEEDED:
                fs.status = ForeshadowingStatus.RESOLVED
        else:
            raise ValueError("action 必须是 'seed' 或 'resolve'")

        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)

    def add_style_reference(
        self,
        project: NovelProject,
        name: str,
        reference_author: str = "",
        description: str = "",
        sample_texts: Optional[List[str]] = None,
        is_active: bool = True,
    ) -> StyleReference:
        """添加文笔风格参考"""
        ref = StyleReference(
            name=name,
            reference_author=reference_author,
            description=description,
            sample_texts=sample_texts or [],
            is_active=is_active,
        )
        project.style_references[ref.id] = ref
        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)
        return ref

    def analyze_style_from_text(
        self,
        project: NovelProject,
        reference_id: str,
        sample_text: str,
    ) -> StyleReference:
        """
        让 AI 分析参考文本的风格特征，自动填充 StyleReference 的分析字段
        """
        if not self.generator:
            raise RuntimeError("未配置 AI 生成器")

        ref = project.style_references.get(reference_id)
        if not ref:
            raise ValueError("风格参考不存在")

        prompt = (
            "你是一位文学评论家。请对以下文本片段进行风格分析，"
            "提炼出其在词汇、句式、描写、对话、叙事节奏五个维度的特征。"
            "以简洁的要点形式输出。\n\n"
            f"【参考文本】\n{sample_text[:2000]}\n\n"
            "请输出: \n"
            "1. 词汇偏好特征\n"
            "2. 句式结构特征\n"
            "3. 描写手法特征\n"
            "4. 对话风格特征\n"
            "5. 叙事节奏特征"
        )
        request = create_request(prompt=prompt, temperature=0.3, max_tokens=1500)
        result = self.generator.generate(request)
        if not result.success:
            raise RuntimeError(f"风格分析失败: {result.error_message}")

        analysis = result.text
        # 简单解析分析结果到各字段
        ref.analyzed_traits = [line.strip("- • ") for line in analysis.splitlines() if line.strip().startswith(("-", "•", "1.", "2.", "3.", "4.", "5."))]
        ref.vocabulary_notes = analysis[:500]
        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)
        return ref

    def set_outline(self, project: NovelProject, outline: OutlineNode) -> None:
        """设置小说大纲"""
        # 兼容旧数据：如果根节点 level != 0，自动包装为总纲
        if outline.level != 0:
            old_root = outline
            outline = OutlineNode(
                title="全书总纲",
                level=0,
                summary="",
                children=[old_root],
            )
        project.outline = outline
        # 自动同步创建章节占位
        self._sync_chapters_from_outline(project)
        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)

    def _sync_chapters_from_outline(self, project: NovelProject) -> None:
        """根据大纲自动创建/同步章节占位"""
        if not project.outline:
            return
        chapters = project.outline.flatten_chapters()
        existing_ids = {ch.id for ch in project.chapters.values()}
        # 按标题建立已有章节的映射，避免重复创建同名章节
        existing_by_title = {ch.title: ch for ch in project.chapters.values()}
        for i, node in enumerate(chapters, start=1):
            if node.chapter_id and node.chapter_id in project.chapters:
                ch = project.chapters[node.chapter_id]
                # 只在没有设置过序号时才按遍历顺序分配，避免覆盖用户手动指定的序号
                if ch.sequence_number == 0:
                    ch.sequence_number = i
                ch.title = node.title
                ch.outline_summary = node.summary
                ch.characters_present = node.characters_involved
                ch.locations = node.locations
            elif node.title in existing_by_title:
                # 复用已有同名章节，避免重复创建
                ch = existing_by_title[node.title]
                node.chapter_id = ch.id
                if ch.sequence_number == 0:
                    ch.sequence_number = i
                ch.outline_summary = node.summary
                ch.characters_present = node.characters_involved
                ch.locations = node.locations
            else:
                ch = Chapter(
                    title=node.title,
                    sequence_number=i,
                    outline_summary=node.summary,
                    characters_present=node.characters_involved,
                    locations=node.locations,
                    status=ChapterStatus.PLANNED,
                )
                node.chapter_id = ch.id
                project.chapters[ch.id] = ch
                existing_by_title[ch.title] = ch

    # --- 大纲树操作 ---

    def _find_outline_node(self, root: OutlineNode, node_id: str) -> Optional[OutlineNode]:
        """递归查找大纲节点"""
        if root.id == node_id:
            return root
        for child in root.children:
            found = self._find_outline_node(child, node_id)
            if found:
                return found
        return None

    def _find_outline_node_parent(self, root: OutlineNode, node_id: str) -> Optional[OutlineNode]:
        """递归查找大纲节点的父节点"""
        for child in root.children:
            if child.id == node_id:
                return root
            found = self._find_outline_node_parent(child, node_id)
            if found:
                return found
        return None

    def update_outline_node(
        self,
        project: NovelProject,
        node_id: str,
        title: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> OutlineNode:
        """更新大纲节点信息"""
        if not project.outline:
            raise ValueError("项目尚无大纲")
        node = self._find_outline_node(project.outline, node_id)
        if not node:
            raise ValueError(f"节点不存在: {node_id}")
        if title is not None:
            node.title = title
        if summary is not None:
            node.summary = summary
        # 若该节点关联了章节，同步更新章节标题与摘要
        if node.chapter_id and node.chapter_id in project.chapters:
            ch = project.chapters[node.chapter_id]
            ch.title = node.title
            ch.outline_summary = node.summary
        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)
        return node

    def add_outline_node(
        self,
        project: NovelProject,
        parent_id: Optional[str],
        title: str,
        summary: str = "",
        level: int = 1,
    ) -> OutlineNode:
        """在大纲中新增节点。parent_id 为 None 时添加到根节点下"""
        if not project.outline:
            raise ValueError("项目尚无大纲")

        if parent_id is None or parent_id == project.outline.id:
            parent = project.outline
        else:
            parent = self._find_outline_node(project.outline, parent_id)

        if not parent:
            raise ValueError(f"父节点不存在: {parent_id}")

        # 自动推断并约束 level
        expected_level = parent.level + 1
        if level < expected_level:
            level = expected_level
        if level > 3:
            level = 3
        if parent.level >= 3:
            raise ValueError("章节点下不能再添加子节点")

        node = OutlineNode(title=title, level=level, summary=summary)
        parent.children.append(node)
        # 若新增的是章级节点，自动同步创建章节占位
        if level == 3:
            self._sync_chapters_from_outline(project)
        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)
        return node

    def remove_outline_node(
        self,
        project: NovelProject,
        node_id: str,
        remove_linked_chapter: bool = False,
    ) -> bool:
        """删除大纲节点。若节点关联了章节，可选择是否同时删除章节"""
        if not project.outline:
            return False
        if project.outline.id == node_id:
            # 删除根节点 = 清空整个大纲
            project.outline = None
            project.updated_at = datetime.now().isoformat()
            self.storage.save(project)
            return True
        parent = self._find_outline_node_parent(project.outline, node_id)
        if not parent:
            return False
        target = None
        for child in parent.children:
            if child.id == node_id:
                target = child
                break
        if not target:
            return False
        parent.children.remove(target)
        # 处理关联章节
        if target.chapter_id and target.chapter_id in project.chapters:
            if remove_linked_chapter:
                del project.chapters[target.chapter_id]
            else:
                # 仅解除关联
                project.chapters[target.chapter_id].outline_summary = ""
        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)
        return True

    def generate_chapter(
        self,
        project: NovelProject,
        chapter_id: str,
        temperature: float = 0.7,
        max_tokens: int = 7000,
        stream_callback: Optional[Callable[[str], None]] = None,
        extra_constraints: Optional[List[str]] = None,
    ) -> Chapter:
        """
        生成指定章节的正文内容
        这是核心创作方法
        """
        if not self.generator:
            raise RuntimeError("未配置 AI 生成器，请先设置 generator")

        chapter = project.chapters.get(chapter_id)
        if not chapter:
            raise ValueError(f"章节不存在: {chapter_id}")

        chapter.status = ChapterStatus.WRITING
        self.storage.save(project)

        # 构建提示词
        prompt = self.prompt_builder.build_chapter_prompt(
            project=project,
            chapter_id=chapter_id,
            extra_constraints=extra_constraints,
        )

        # 创建生成请求
        request = create_request(
            prompt=prompt,
            system_message="你是一位专业中文小说作家。严格遵守用户提供的所有设定约束。",
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # 执行生成
        if stream_callback:
            # 流式生成
            full_text = ""
            for chunk in self.generator.generate_stream(request):
                full_text += chunk
                stream_callback(chunk)
            result_text = full_text
        else:
            result = self.generator.generate(request)
            if not result.success:
                chapter.status = ChapterStatus.PLANNED
                self.storage.save(project)
                raise RuntimeError(f"生成失败: {result.error_message}")
            result_text = result.text

        # 更新章节
        chapter.content = result_text.strip()
        chapter.word_count = count_chinese_words(chapter.content)
        chapter.status = ChapterStatus.REVIEW
        chapter.generation_history.append({
            "timestamp": datetime.now().isoformat(),
            "model": self.generator.get_name(),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "prompt_length": len(prompt),
            "output_length": len(result_text),
        })

        # 更新伏笔生命周期状态
        for fid in chapter.foreshadowing_seeded:
            fs = project.foreshadowings.get(fid)
            if fs and fs.status == ForeshadowingStatus.PLANNED:
                fs.status = ForeshadowingStatus.SEEDED
                fs.seed_chapter_id = chapter_id
        for fid in chapter.foreshadowing_resolved:
            fs = project.foreshadowings.get(fid)
            if fs and fs.status == ForeshadowingStatus.SEEDED:
                fs.status = ForeshadowingStatus.RESOLVED
                fs.resolve_chapter_id = chapter_id

        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)

        return chapter

    def regenerate_chapter(
        self,
        project: NovelProject,
        chapter_id: str,
        revision_notes: str = "",
        **kwargs
    ) -> Chapter:
        """根据修改意见重新生成章节"""
        constraints = kwargs.pop("extra_constraints", []) or []
        if revision_notes:
            constraints.append(f"修改要求: {revision_notes}")
        return self.generate_chapter(
            project, chapter_id,
            extra_constraints=constraints,
            **kwargs
        )

    def revise_chapter(
        self,
        project: NovelProject,
        chapter_id: str,
        revision_notes: str,
        temperature: float = 0.7,
        max_tokens: int = 7000,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> Chapter:
        """
        修订重写章节：基于已有正文和作者修改意见，让 AI 在原文基础上修订。
        与 regenerate_chapter 的区别：
        - regenerate 是从零重新生成
        - revise 是把原文作为输入，按作者意见修订细节，保留整体结构
        """
        if not self.generator:
            raise RuntimeError("未配置 AI 生成器，请先设置 generator")

        chapter = project.chapters.get(chapter_id)
        if not chapter:
            raise ValueError(f"章节不存在: {chapter_id}")
        if not chapter.content or not chapter.content.strip():
            raise ValueError("章节正文为空，无法修订。请先生成章节内容。")
        if not revision_notes or not revision_notes.strip():
            raise ValueError("请输入修改意见")

        chapter.status = ChapterStatus.WRITING
        self.storage.save(project)

        # 收集上下文
        ctx = project.build_generation_context(chapter_id)
        outline_path = ' > '.join(ctx.outline_path) if ctx.outline_path else ''
        chapter_summary = chapter.outline_summary or (ctx.current_node.summary if ctx.current_node else '')

        # 收集出场人物信息
        char_info = ""
        if chapter.characters_present:
            char_lines = []
            for cid in chapter.characters_present:
                c = project.characters.get(cid)
                if c:
                    line = f"- {c.name}（{c.role.value}）: {c.personality}"
                    if c.motivation:
                        line += f"，动机: {c.motivation}"
                    char_lines.append(line)
            if char_lines:
                char_info = "\n".join(char_lines)

        # 构建修订提示词
        prompt = f"""你是一位资深的中文小说编辑，擅长在保留原作风格和整体结构的前提下，根据作者意见对章节进行精准修订。

## 任务
请根据作者的修改意见，对以下章节正文进行修订重写。

## 修订原则
1. **保留整体结构**：章节的大框架、主要情节走向、人物出场顺序应基本保持不变
2. **精准修改**：只针对作者指出的问题进行修改，不要改动作者没有提到的满意部分
3. **风格一致**：修订后的文字风格应与原文保持一致
4. **连贯性**：修改后的内容要与前后文自然衔接，不能出现断裂感
5. **输出完整章节**：请输出修订后的完整章节正文，不要只输出修改的片段

## 章节信息
- 位置: {outline_path}
- 标题: {chapter.title}
- 摘要: {chapter_summary}
{f'- 出场人物:\n{char_info}' if char_info else ''}

## ⚠️ 作者修改意见（必须严格执行）
{revision_notes.strip()}

## 原文正文
{chapter.content}

## 输出要求
请直接输出修订后的完整章节正文，不要任何额外的说明、注释或标记。"""

        request = create_request(
            prompt=prompt,
            system_message="你是一位专业中文小说编辑。请根据作者修改意见，在原文基础上进行精准修订，输出完整的修订后正文。",
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # 执行生成
        if stream_callback:
            full_text = ""
            for chunk in self.generator.generate_stream(request):
                full_text += chunk
                stream_callback(chunk)
            result_text = full_text
        else:
            result = self.generator.generate(request)
            if not result.success:
                chapter.status = ChapterStatus.REVIEW
                self.storage.save(project)
                raise RuntimeError(f"修订失败: {result.error_message}")
            result_text = result.text

        # 更新章节
        chapter.content = result_text.strip()
        chapter.word_count = count_chinese_words(chapter.content)
        chapter.status = ChapterStatus.REVIEW
        chapter.generation_history.append({
            "timestamp": datetime.now().isoformat(),
            "model": self.generator.get_name(),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "prompt_length": len(prompt),
            "output_length": len(result_text),
            "type": "revision",
        })

        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)

        return chapter

    def generate_dialogue(
        self,
        project: NovelProject,
        character_ids: List[str],
        scene_context: str,
        dialogue_goal: str,
    ) -> str:
        """生成独立对话片段"""
        if not self.generator:
            raise RuntimeError("未配置 AI 生成器")

        prompt = self.prompt_builder.build_dialogue_prompt(
            project, character_ids, scene_context, dialogue_goal
        )
        request = create_request(prompt=prompt, temperature=0.8, max_tokens=2000)
        result = self.generator.generate(request)
        if not result.success:
            raise RuntimeError(f"对话生成失败: {result.error_message}")
        return result.text

    def generate_scene(
        self,
        project: NovelProject,
        location: str,
        atmosphere: str,
        key_elements: List[str],
    ) -> str:
        """生成独立场景描写"""
        if not self.generator:
            raise RuntimeError("未配置 AI 生成器")

        prompt = self.prompt_builder.build_scene_prompt(
            project, location, atmosphere, key_elements
        )
        request = create_request(prompt=prompt, temperature=0.75, max_tokens=1500)
        result = self.generator.generate(request)
        if not result.success:
            raise RuntimeError(f"场景生成失败: {result.error_message}")
        return result.text

    def analyze_chapter(
        self,
        project: NovelProject,
        chapter_id: str,
    ) -> Dict[str, Any]:
        """
        使用AI分析章节正文，提取剧情记忆、新人物、新地点、分支剧情
        返回分析结果字典，不会自动保存到项目
        """
        if not self.generator:
            raise RuntimeError("未配置 AI 生成器")

        chapter = project.chapters.get(chapter_id)
        if not chapter:
            raise ValueError(f"章节不存在: {chapter_id}")

        existing_char_names = {c.name for c in project.characters.values()}
        existing_locations = set(project.world.locations.keys()) if project.world else set()
        existing_branches = {
            b.title: b.description
            for b in project.branch_plots.values()
            if b.status in (BranchStatus.OPEN, BranchStatus.IN_PROGRESS)
        }

        existing_faction_names = {f.name for f in project.factions.values()}
        existing_item_names = {i.name for i in project.items.values()}

        branches_text = ""
        if existing_branches:
            for title, desc in existing_branches.items():
                branches_text += f"  - {title}: {desc}\n"
        else:
            branches_text = "  无\n"

        prompt = f"""请分析以下小说章节，提取结构化信息并以JSON格式返回。

章节标题：{chapter.title}
章节正文（前3000字）：
{chapter.content[:3000]}

请提取以下信息：
1. plot_memory: 本章关键剧情摘要（200字以内），必须包含：
   - 关键情节转折和重要事件结果
   - 各主要人物在本章结束时的状态变化
   - 新出现的重要物品或能力
2. new_characters: 本章新出现的人物列表（已有同名人物不要重复），每人包含：
   - name: 姓名
   - role: 角色定位（protagonist主角/deuteragonist配角/antagonist反派/supporting次要角色/minor龙套）
   - description: 简短描述（外貌、性格、与本章的关系）
   - faction_name: 所属势力名称（如果有且与已有势力匹配，否则留空）
   - faction_affinity: 势力关系描述（如核心成员、外围弟子、敌对等，多势力可描述次要关系）
   - spells_skills: 法术/技能描述（如修炼功法、特殊能力、战斗技能等，没有则留空）
3. new_locations: 本章新出现的地点列表（已有同名地点不要重复），每个包含：
   - name: 地名
   - description: 简短描述
   - status: 地点状态（active正常/destroyed已毁灭/hidden隐藏/lost失落/under_construction建造中）
   - level: 级别（minor次要/normal一般/important重要/core核心/sacred圣地）
   - hierarchy: 层级位置（如东方大陆 > 青云国 > 京城，简单地点可留空）
   - scale: 规模（如小型村落/中型城市/大型宗门/秘境等）
4. new_factions: 本章新出现的势力/组织列表（已有同名势力不要重复），每个包含：
   - name: 势力名称
   - description: 势力描述
   - status: 势力状态（active活跃/dissolved已解散/hidden隐秘/at_war交战中/declining衰落中/rising崛起中）
   - level: 级别（minor次要/normal一般/important重要/major大宗/supreme至高）
   - location_name: 绑定地点名称（如果该势力有固定据点且地点已存在，填写名称匹配；否则留空）
5. new_items: 本章新出现的重要物品列表（已有同名物品不要重复），每个包含：
   - name: 物品名称
   - description: 物品描述（外观、特性等）
   - item_type: 类型（artifact法宝/weapon武器/armor护具/consumable消耗品/material材料/treasure宝物/other其他）
   - grade: 品级（trash垃圾/common普通/uncommon优秀/rare稀有/epic史诗/legendary传说/divine神器）
   - effects: 功效/能力描述
   - origin: 来源/出处（如果提及）
   - owner_name: 当前持有者姓名（如果有且与已有角色匹配，否则留空）
   - status: 状态（active正常/lost遗失/destroyed损毁/sealed封印/dormant潜伏）
6. branch_plots: 本章中新开启或可延续的分支剧情列表。分支剧情是指：
   - 本章中埋下但尚未解决的悬念/冲突
   - 新出现的支线任务或人物目标
   - 可独立发展的情节线索（与主线并行但不干扰主线）
   每个分支包含：
   - title: 分支名称（简洁概括）
   - description: 触发事件与当前状态描述
   - importance: 重要性（minor次要/medium一般/major重要）
   注意：如果本章只是推进了已有分支而非开启新分支，请返回空列表。

已知已有人物（不要重复提取）：{', '.join(existing_char_names) or '无'}
已知已有地点（不要重复提取）：{', '.join(existing_locations) or '无'}
已知已有势力（不要重复提取）：{', '.join(existing_faction_names) or '无'}
已知已有物品（不要重复提取）：{', '.join(existing_item_names) or '无'}
已知已有活跃分支（如果本章只是推进它们，请返回空列表，不要重复创建）：
{branches_text}
返回严格JSON格式，不要任何额外解释或markdown代码块标记：
{{"plot_memory": "string",
  "new_characters": [{{"name": "...", "role": "...", "description": "...", "faction_name": "...", "faction_affinity": "...", "spells_skills": "..."}}],
  "new_locations": [{{"name": "...", "description": "...", "status": "...", "level": "...", "hierarchy": "...", "scale": "..."}}],
  "new_factions": [{{"name": "...", "description": "...", "status": "...", "level": "...", "location_name": "..."}}],
  "new_items": [{{"name": "...", "description": "...", "item_type": "...", "grade": "...", "effects": "...", "origin": "...", "owner_name": "...", "status": "..."}}],
  "branch_plots": [{{"title": "...", "description": "...", "importance": "..."}}]
}}"""

        request = create_request(
            prompt=prompt,
            system_message="你是一位专业的小说编辑，擅长提炼剧情要点和识别叙事要素。请严格按JSON格式输出。",
            temperature=0.3,
            max_tokens=8000,
            extra_body={"enable_thinking": False},
        )

        result = self.generator.generate(request)
        if not result.success:
            raise RuntimeError(f"章节分析失败: {result.error_message}")

        # 容错：如果 content 为空但 reasoning_content 有内容，尝试从中提取
        text = result.text.strip()
        if not text and result.reasoning_content:
            text = result.reasoning_content.strip()

        analysis = self._extract_json_from_text(text)
        if not analysis:
            # 所有解析方式都失败，把原始文本作为 plot_memory 回退
            analysis = {
                "plot_memory": text[:500] if text else "",
                "new_characters": [],
                "new_locations": [],
                "new_factions": [],
                "new_items": [],
                "branch_plots": [],
            }

        return analysis

    def apply_chapter_analysis(
        self,
        project: NovelProject,
        chapter_id: str,
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        将章节分析结果应用到项目中：
        - 保存 plot_memory 到章节
        - 新增人物到人物设定（含势力绑定）
        - 新增地点到地点列表
        - 新增势力到势力列表
        - 新增分支剧情到分支列表
        返回应用摘要 {"plot_memory_saved": bool, "new_chars_added": int, "new_locs_added": int, "new_factions_added": int, "new_items_added": int, "new_branches_added": int, "faction_bindings": int}
        """
        chapter = project.chapters.get(chapter_id)
        if not chapter:
            raise ValueError(f"章节不存在: {chapter_id}")

        summary = {
            "plot_memory_saved": False,
            "new_chars_added": 0,
            "new_locs_added": 0,
            "new_factions_added": 0,
            "new_items_added": 0,
            "new_branches_added": 0,
            "faction_bindings": 0,
        }

        # 保存剧情记忆
        plot_memory = analysis.get("plot_memory", "")
        if plot_memory:
            chapter.plot_memory = plot_memory
            summary["plot_memory_saved"] = True

        # 建立名称到ID的映射
        faction_name_to_id = {f.name: fid for fid, f in project.factions.items()}

        # 添加新人物 + 势力绑定
        existing_names = {c.name for c in project.characters.values()}
        for char_data in analysis.get("new_characters", []):
            name = char_data.get("name", "").strip()
            if name and name not in existing_names:
                role_str = char_data.get("role", "supporting")
                try:
                    role = CharacterRole(role_str.lower())
                except ValueError:
                    role = CharacterRole.SUPPORTING
                char = Character(
                    name=name,
                    role=role,
                    personality=char_data.get("description", ""),
                    spells_skills=char_data.get("spells_skills", ""),
                )
                # 尝试绑定势力
                fac_name = char_data.get("faction_name", "").strip()
                fac_affinity = char_data.get("faction_affinity", "").strip()
                if fac_name and fac_name in faction_name_to_id:
                    char.faction_id = faction_name_to_id[fac_name]
                    summary["faction_bindings"] += 1
                if fac_affinity:
                    char.faction_notes = fac_affinity
                project.characters[char.id] = char
                existing_names.add(name)
                summary["new_chars_added"] += 1

        # 对已有人物也尝试更新势力绑定
        for char_data in analysis.get("new_characters", []):
            name = char_data.get("name", "").strip()
            fac_name = char_data.get("faction_name", "").strip()
            fac_affinity = char_data.get("faction_affinity", "").strip()
            if name and fac_name and fac_name in faction_name_to_id:
                for char in project.characters.values():
                    if char.name == name and not char.faction_id:
                        char.faction_id = faction_name_to_id[fac_name]
                        if fac_affinity:
                            char.faction_notes = fac_affinity
                        summary["faction_bindings"] += 1
                        break

        # 添加新地点
        existing_loc_names = {loc.name for loc in project.locations.values()}
        for loc_data in analysis.get("new_locations", []):
            name = loc_data.get("name", "").strip()
            if name and name not in existing_loc_names:
                loc = Location(
                    name=name,
                    description=loc_data.get("description", ""),
                    status=LocationStatus(loc_data.get("status", "active").lower()),
                    level=loc_data.get("level", "normal"),
                    hierarchy=loc_data.get("hierarchy", ""),
                    scale=loc_data.get("scale", ""),
                )
                project.locations[loc.id] = loc
                existing_loc_names.add(name)
                summary["new_locs_added"] += 1

        # 添加新势力
        existing_fac_names = {f.name for f in project.factions.values()}
        for fac_data in analysis.get("new_factions", []):
            name = fac_data.get("name", "").strip()
            if name and name not in existing_fac_names:
                fac = Faction(
                    name=name,
                    description=fac_data.get("description", ""),
                    status=FactionStatus(fac_data.get("status", "active").lower()),
                    level=fac_data.get("level", "normal"),
                )
                # 尝试绑定地点
                loc_name = fac_data.get("location_name", "").strip()
                if loc_name:
                    for loc in project.locations.values():
                        if loc.name == loc_name:
                            fac.location_id = loc.id
                            break
                project.factions[fac.id] = fac
                existing_fac_names.add(name)
                summary["new_factions_added"] += 1

        # 添加新物品
        existing_item_names = {i.name for i in project.items.values()}
        char_name_to_id = {c.name: cid for cid, c in project.characters.items()}
        for item_data in analysis.get("new_items", []):
            name = item_data.get("name", "").strip()
            if name and name not in existing_item_names:
                try:
                    status = ItemStatus(item_data.get("status", "active").lower())
                except ValueError:
                    status = ItemStatus.ACTIVE
                item = Item(
                    name=name,
                    description=item_data.get("description", ""),
                    item_type=item_data.get("item_type", "artifact"),
                    grade=item_data.get("grade", "normal"),
                    effects=item_data.get("effects", ""),
                    origin=item_data.get("origin", ""),
                    status=status,
                )
                # 尝试绑定持有者
                owner_name = item_data.get("owner_name", "").strip()
                if owner_name and owner_name in char_name_to_id:
                    item.owner_character_id = char_name_to_id[owner_name]
                project.items[item.id] = item
                existing_item_names.add(name)
                summary["new_items_added"] += 1

        # 添加新分支剧情
        existing_branch_titles = {b.title for b in project.branch_plots.values()}
        for branch_data in analysis.get("branch_plots", []):
            title = branch_data.get("title", "").strip()
            if title and title not in existing_branch_titles:
                branch = BranchPlot(
                    title=title,
                    description=branch_data.get("description", ""),
                    importance=branch_data.get("importance", "medium"),
                    origin_chapter_id=chapter_id,
                    status=BranchStatus.OPEN,
                )
                project.branch_plots[branch.id] = branch
                existing_branch_titles.add(title)
                summary["new_branches_added"] += 1

        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)
        return summary

    @staticmethod
    def _extract_json_from_text(text: str) -> Dict[str, Any]:
        """
        从文本中智能提取 JSON 对象，支持多种容错方式：
        1. 直接解析
        2. 去除 markdown 代码块后解析
        3. 用正则提取第一个 {} 块
        4. 用 _repair_truncated_json 修复截断后解析
        """
        import re

        if not text or not text.strip():
            return {}

        candidates = [text.strip()]

        # 去除 markdown 代码块
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
            candidates.append(cleaned)

        # 尝试直接解析所有候选
        for candidate in candidates:
            try:
                return json.loads(candidate)
            except (json.JSONDecodeError, ValueError):
                continue

        # 用正则提取第一个 JSON 对象
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                pass

        # 尝试修复截断的 JSON
        for candidate in candidates:
            repaired = CreationPipeline._repair_truncated_json(candidate)
            if repaired:
                try:
                    return json.loads(repaired)
                except (json.JSONDecodeError, ValueError):
                    continue

        return {}

    @staticmethod
    def _repair_truncated_json(text: str) -> Optional[str]:
        """
        修复被截断的 JSON 文本：
        1. 剥离末尾不完整的键值对（截断在字符串/数字/键名中间）
        2. 补全未闭合的 ] 和 }
        """
        if not text or not text.strip():
            return None

        # 剥离末尾不完整的内容：回退到最后一个完整的结构边界
        s = text.rstrip()
        # 去掉末尾可能的不完整 token
        # 先找到最后一个结构性字符（} ] , " 数字）的位置
        # 截断可能发生在字符串中间，回退到最后一个完整的 }, ] 或 "
        last_good = -1
        for i in range(len(s) - 1, -1, -1):
            if s[i] in ('}', ']', '"'):
                last_good = i
                break
            elif s[i] == ',':
                # 逗号后面被截断，去掉这个悬空逗号
                last_good = i - 1
                break
        if last_good < 0:
            return None

        s = s[:last_good + 1]

        # 去掉末尾悬空逗号
        s = s.rstrip().rstrip(',')

        # 统计未闭合的括号
        open_braces = 0
        open_brackets = 0
        in_string = False
        escape = False
        for ch in s:
            if escape:
                escape = False
                continue
            if ch == '\\':
                if in_string:
                    escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                open_braces += 1
            elif ch == '}':
                open_braces -= 1
            elif ch == '[':
                open_brackets += 1
            elif ch == ']':
                open_brackets -= 1

        # 如果在字符串中间被截断，先闭合字符串
        if in_string:
            s += '"'

        # 去掉末尾悬空逗号（闭合字符串后可能出现新的悬空）
        s = s.rstrip().rstrip(',')

        # 补全括号
        s += ']' * max(0, open_brackets)
        s += '}' * max(0, open_braces)

        return s if s else None

    def auto_generate_outline(
        self,
        project: NovelProject,
        num_volumes: int = 3,
        min_acts_per_volume: int = 5,
        min_chapters_per_act: int = 5,
        extra_guidance: str = "",
        volume_requirements: Optional[List[str]] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> OutlineNode:
        """
        全自动生成 总纲-卷-幕-章 四级大纲。
        基于项目的世界观设定、人物设定、描述等信息，
        让 AI 一次性生成完整的故事大纲结构。

        约束：
        - 每卷至少 min_acts_per_volume 幕
        - 每幕至少 min_chapters_per_act 章
        """
        if not self.generator:
            raise RuntimeError("未配置 AI 生成器，请先设置 generator")

        ctx = self._collect_project_context(project)
        world_info = ctx['world_info']
        char_info = ctx['char_info']
        loc_info = ctx['loc_info']
        fac_info = ctx['fac_info']

        # 构建阶段性要求文本
        vol_req_text = ""
        if volume_requirements:
            req_lines = []
            for i, req in enumerate(volume_requirements):
                if req and req.strip():
                    req_lines.append(f"  - 第{i+1}卷: {req.strip()}")
            if req_lines:
                vol_req_text = (
                    "\n## 📌 阶段性大纲要求（每卷边界约束，必须严格遵守）\n"
                    "以下是每卷的阶段性限制，每卷的内容（人物成长、实力进展、剧情推进）"
                    "**必须严格控制在指定范围内**，不得提前透支后续卷的内容：\n"
                    + "\n".join(req_lines)
                    + "\n\n⚠️ 每卷的剧情发展和人物成长必须恰好写到该卷要求的阶段为止，"
                    "不能超前也不能滞后。这是硬性约束，优先级高于其他内容要求。\n"
                )

        prompt = f"""你是一位资深的小说策划编辑，擅长构建宏大叙事结构。
请根据以下小说设定，生成一部完整的故事大纲。

## 小说信息
- 标题: {project.title}
- 简介: {project.description or '暂无'}

## 世界观设定
{world_info}
{loc_info}
{fac_info}

## 人物设定
{char_info}

## 结构要求
大纲必须严格遵守「总纲-卷-幕-章」四级结构：
1. 总纲（level=0）: 1个，包含全书的核心主线概述
2. 卷（level=1）: 恰好 {num_volumes} 卷，每卷有独立的主题和阶段性目标
3. 幕（level=2）: 每卷至少 {min_acts_per_volume} 幕，幕是卷内的叙事段落
4. 章（level=3）: 每幕至少 {min_chapters_per_act} 章，每章有具体的情节内容

## 内容要求
1. 总纲 summary: 概括全书主线、核心冲突与最终走向（200字以内）
2. 卷 summary: 概括本卷的阶段目标、主要冲突和关键转折（150字以内）
3. 幕 summary: 描述本幕的叙事功能（如开端、递进、高潮、收束），以及具体要完成的剧情任务（100字以内）
4. 章 summary: 具体描述本章要发生什么事件、哪些人物参与、情感走向（80字以内）
5. 章 emotional_tone: 每章标注情感基调（如：紧张、悲壮、温馨、压抑等）
6. 故事必须有完整的起承转合，伏笔要有回收，冲突要有解决
7. 每卷之间有递进关系，难度和冲突逐步升级
8. 严格遵守世界观中的设定，不能违背世界观设定
{vol_req_text}{f"""## ⚠️ 创作者核心指导（高优先级，必须严格遵守）
以下是创作者对本书的核心创作要求和方向要求，生成大纲时必须将其作为较高优先级的指导原则：

{extra_guidance}

请确保，不得偏离或忽视。""" if extra_guidance else ''}

## 输出格式
严格按以下 JSON 格式输出，不要任何额外解释或 markdown 代码块标记：
{{
  "title": "全书总纲",
  "level": 0,
  "summary": "全书主线概述",
  "children": [
    {{
      "title": "第一卷：卷名",
      "level": 1,
      "summary": "卷摘要",
      "children": [
        {{
          "title": "第一幕：幕名",
          "level": 2,
          "summary": "幕摘要",
          "children": [
            {{
              "title": "第一章 章名",
              "level": 3,
              "summary": "章节摘要",
              "emotional_tone": "情感基调"
            }}
          ]
        }}
      ]
    }}
  ]
}}"""

        request = create_request(
            prompt=prompt,
            system_message="你是一位专业的小说大纲策划师。请严格按JSON格式输出完整的四级大纲结构。",
            temperature=0.8,
            max_tokens=655360,
        )

        # 执行生成
        if stream_callback:
            full_text = ""
            for chunk in self.generator.generate_stream(request):
                full_text += chunk
                stream_callback(chunk)
            result_text = full_text
        else:
            result = self.generator.generate(request)
            if not result.success:
                raise RuntimeError(f"大纲生成失败: {result.error_message}")
            result_text = result.text

        # 解析 JSON
        text = result_text.strip()
        # 去除可能的 markdown 代码块标记
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            # 尝试截取第一个完整的JSON对象
            import re
            match = re.search(r'\{', text)
            if match:
                brace_count = 0
                start = match.start()
                found = False
                for i in range(start, len(text)):
                    if text[i] == '{':
                        brace_count += 1
                    elif text[i] == '}':
                        brace_count -= 1
                    if brace_count == 0:
                        try:
                            data = json.loads(text[start:i+1])
                            found = True
                            break
                        except json.JSONDecodeError:
                            continue
                if not found:
                    # JSON 被截断（token 不够），尝试自动补全闭合括号
                    truncated = text[start:]
                    repaired = self._repair_truncated_json(truncated)
                    if repaired:
                        try:
                            data = json.loads(repaired)
                        except json.JSONDecodeError:
                            raise RuntimeError(f"AI 返回的大纲 JSON 解析失败（可能因 token 不足被截断）: {e}\n原始文本前500字: {text[:500]}")
                    else:
                        raise RuntimeError(f"AI 返回的大纲 JSON 解析失败（可能因 token 不足被截断）: {e}\n原始文本前500字: {text[:500]}")
            else:
                raise RuntimeError(f"AI 返回的大纲 JSON 解析失败: {e}\n原始文本前500字: {text[:500]}")

        outline = OutlineNode.from_dict(data)

        # 兼容：如果根节点 level != 0，自动包装
        if outline.level != 0:
            outline = OutlineNode(
                title="全书总纲", level=0, summary="", children=[outline]
            )

        # 验证结构完整性
        volumes = [c for c in outline.children if c.level == 1]
        if len(volumes) < num_volumes:
            pass  # 允许AI返回略少的卷数，不强制报错

        # 设置大纲到项目（会自动同步章节）
        pipeline_self = self
        pipeline_self.set_outline(project, outline)

        return project.outline

    def _collect_project_context(self, project: NovelProject) -> dict:
        """收集项目的世界观、人物、地点、势力信息，供大纲生成/续写共用"""
        world_info = "未设定世界观"
        if project.world:
            w = project.world
            parts = []
            if w.name: parts.append(f"世界名称: {w.name}")
            if w.genre: parts.append(f"题材类型: {w.genre}")
            if w.era: parts.append(f"时代背景: {w.era}")
            if w.geography: parts.append(f"地理设定: {w.geography}")
            if w.history: parts.append(f"历史沿革: {w.history}")
            if w.power_system: parts.append(f"力量体系: {w.power_system}")
            if w.society: parts.append(f"社会结构: {w.society}")
            if w.rules: parts.append(f"核心规则: {'; '.join(w.rules)}")
            if w.customs: parts.append(f"风俗文化: {'; '.join(w.customs)}")
            world_info = "\n".join(parts)

        char_info = "暂无人物设定"
        if project.characters:
            char_lines = []
            for c in project.characters.values():
                line = f"- {c.name}（{c.role.value}）: {c.personality}"
                if c.motivation: line += f"，动机: {c.motivation}"
                char_lines.append(line)
            char_info = "\n".join(char_lines)

        loc_info = ""
        if project.locations:
            loc_lines = [f"- {loc.name}: {loc.description}" for loc in project.locations.values()]
            loc_info = "\n关键地点:\n" + "\n".join(loc_lines)

        fac_info = ""
        if project.factions:
            fac_lines = [f"- {fac.name}: {fac.description}" for fac in project.factions.values()]
            fac_info = "\n主要势力:\n" + "\n".join(fac_lines)

        return {"world_info": world_info, "char_info": char_info, "loc_info": loc_info, "fac_info": fac_info}

    def _build_existing_outline_context(self, project: NovelProject, max_acts: int = 10) -> str:
        """
        构建已有大纲的上下文摘要，用于续写。
        取最后 max_acts 幕，越靠后的幕提供越多细节（权重递增）。
        """
        if not project.outline:
            return ""

        # 收集所有 (卷, 幕) 对
        all_acts = []  # [(vol_node, act_node), ...]
        for vol in project.outline.children:
            if vol.level == 1:
                for act in vol.children:
                    if act.level == 2:
                        all_acts.append((vol, act))

        if not all_acts:
            return ""

        # 取最后 max_acts 幕
        recent_acts = all_acts[-max_acts:]
        total = len(recent_acts)

        lines = []
        # 先输出总纲摘要
        lines.append(f"【总纲】{project.outline.summary}")
        lines.append("")

        # 输出所有卷的摘要
        seen_vols = set()
        for vol in project.outline.children:
            if vol.level == 1:
                lines.append(f"【{vol.title}】{vol.summary}")
                seen_vols.add(vol.id)
        lines.append("")

        # 按权重输出幕详情
        lines.append("--- 最近的剧情进展（越靠后越重要） ---")
        for idx, (vol, act) in enumerate(recent_acts):
            # 权重比例: 前面的幕只输出标题+摘要，后面的幕展开章详情
            weight = (idx + 1) / total  # 0.1 ~ 1.0
            act_header = f"\n[{vol.title} / {act.title}] {act.summary}"
            lines.append(act_header)

            # 权重 >= 0.5 的幕展示章标题列表，权重 >= 0.8 的幕展示章详情
            chapters = [c for c in act.children if c.level == 3]
            if weight >= 0.8:
                # 高权重：展示完整章详情
                for ch in chapters:
                    tone = f" [{ch.emotional_tone}]" if ch.emotional_tone else ""
                    lines.append(f"  - {ch.title}{tone}: {ch.summary}")
            elif weight >= 0.5:
                # 中权重：只展示章标题
                ch_titles = ", ".join(ch.title for ch in chapters)
                if ch_titles:
                    lines.append(f"  章节: {ch_titles}")
            # 低权重：只有幕摘要，不展开章

        return "\n".join(lines)

    def continue_outline(
        self,
        project: NovelProject,
        num_new_volumes: int = 1,
        min_acts_per_volume: int = 5,
        min_chapters_per_act: int = 5,
        extra_guidance: str = "",
        volume_requirements: Optional[List[str]] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> OutlineNode:
        """
        续写大纲：基于已有大纲内容，生成新的卷/幕/章并追加到现有大纲中。
        将已有大纲的最近 10 幕作为上下文，越靠后的幕权重越高。
        """
        if not self.generator:
            raise RuntimeError("未配置 AI 生成器，请先设置 generator")
        if not project.outline or not project.outline.children:
            raise RuntimeError("当前没有大纲，请先使用【全自动生成】创建初始大纲")

        ctx = self._collect_project_context(project)
        existing_context = self._build_existing_outline_context(project, max_acts=10)

        # 统计当前大纲规模
        existing_vols = [v for v in project.outline.children if v.level == 1]
        next_vol_num = len(existing_vols) + 1

        # 构建阶段性要求文本
        vol_req_text = ""
        if volume_requirements:
            req_lines = []
            for i, req in enumerate(volume_requirements):
                if req and req.strip():
                    req_lines.append(f"  - 第{next_vol_num + i}卷: {req.strip()}")
            if req_lines:
                vol_req_text = (
                    "\n## 📌 阶段性大纲要求（每卷边界约束，必须严格遵守）\n"
                    "以下是续写各卷的阶段性限制，每卷的内容（人物成长、实力进展、剧情推进）"
                    "**必须严格控制在指定范围内**，不得提前透支后续卷的内容：\n"
                    + "\n".join(req_lines)
                    + "\n\n⚠️ 每卷的剧情发展和人物成长必须恰好写到该卷要求的阶段为止，"
                    "不能超前也不能滞后。这是硬性约束，优先级高于其他内容要求。\n"
                )

        prompt = f"""你是一位资深的小说策划编辑，擅长构建宏大叙事结构。
现在需要你**续写**一部小说的大纲。以下是小说的设定和已有的大纲内容。

## 小说信息
- 标题: {project.title}
- 简介: {project.description or '暂无'}

## 世界观设定
{ctx['world_info']}
{ctx['loc_info']}
{ctx['fac_info']}

## 人物设定
{ctx['char_info']}

## 已有大纲内容（请仔细阅读，续写必须与已有内容衔接）
{existing_context}

## 续写任务
请从第 {next_vol_num} 卷开始续写，生成 {num_new_volumes} 卷新内容。

## 结构要求
续写部分必须严格遵守「卷-幕-章」三级结构：
1. 卷（level=1）: 恰好 {num_new_volumes} 卷，从「第{next_vol_num}卷」开始编号
2. 幕（level=2）: 每卷至少 {min_acts_per_volume} 幕
3. 章（level=3）: 每幕至少 {min_chapters_per_act} 章

## 内容要求
1. 续写内容必须与已有大纲无缝衔接，承接前文的人物发展和剧情走向
2. 卷 summary: 概括本卷的阶段目标、主要冲突和关键转折（150字以内）
3. 幕 summary: 描述本幕的叙事功能及具体剧情任务（100字以内）
4. 章 summary: 具体描述本章事件、参与人物、情感走向（80字以内）
5. 章 emotional_tone: 标注情感基调
6. 故事发展要有递进，冲突逐步升级
7. 注意回收前文已埋设的伏笔，同时可以埋设新的伏笔
{vol_req_text}{f'''\n## ⚠️ 创作者核心指导（最高优先级，必须严格遵守）
{extra_guidance}

请确保续写内容充分体现上述创作指导，不得偏离或忽视。''' if extra_guidance else ''}

## 输出格式
严格按以下 JSON 格式输出续写的卷（注意：只输出新增的卷，不要重复已有内容）：
{{
  "new_volumes": [
    {{
      "title": "第{next_vol_num}卷：卷名",
      "level": 1,
      "summary": "卷摘要",
      "children": [
        {{
          "title": "第X幕：幕名",
          "level": 2,
          "summary": "幕摘要",
          "children": [
            {{
              "title": "第X章 章名",
              "level": 3,
              "summary": "章节摘要",
              "emotional_tone": "情感基调"
            }}
          ]
        }}
      ]
    }}
  ]
}}"""

        request = create_request(
            prompt=prompt,
            system_message="你是一位专业的小说大纲策划师。请严格按JSON格式输出续写的大纲结构，只输出新增的卷。",
            temperature=0.8,
            max_tokens=65536,
        )

        # 执行生成
        if stream_callback:
            full_text = ""
            for chunk in self.generator.generate_stream(request):
                full_text += chunk
                stream_callback(chunk)
            result_text = full_text
        else:
            result = self.generator.generate(request)
            if not result.success:
                raise RuntimeError(f"大纲续写失败: {result.error_message}")
            result_text = result.text

        # 解析 JSON
        text = result_text.strip()
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            import re
            match = re.search(r'\{', text)
            if match:
                brace_count = 0
                start = match.start()
                found = False
                for i in range(start, len(text)):
                    if text[i] == '{': brace_count += 1
                    elif text[i] == '}': brace_count -= 1
                    if brace_count == 0:
                        try:
                            data = json.loads(text[start:i+1])
                            found = True
                            break
                        except json.JSONDecodeError:
                            continue
                if not found:
                    truncated = text[start:]
                    repaired = self._repair_truncated_json(truncated)
                    if repaired:
                        try:
                            data = json.loads(repaired)
                        except json.JSONDecodeError:
                            raise RuntimeError(f"AI 返回的续写 JSON 解析失败（可能因 token 不足被截断）: {e}\n原始文本前500字: {text[:500]}")
                    else:
                        raise RuntimeError(f"AI 返回的续写 JSON 解析失败（可能因 token 不足被截断）: {e}\n原始文本前500字: {text[:500]}")
            else:
                raise RuntimeError(f"AI 返回的续写 JSON 解析失败: {e}\n原始文本前500字: {text[:500]}")

        # 提取新卷并追加到现有大纲
        new_volumes_data = data.get("new_volumes", [])
        if not new_volumes_data:
            # 兼容：AI 可能直接返回单个卷或卷数组
            if isinstance(data, list):
                new_volumes_data = data
            elif data.get("level") == 1:
                new_volumes_data = [data]
            elif data.get("children"):
                new_volumes_data = data["children"]
            else:
                raise RuntimeError("AI 返回的续写内容中未找到新卷数据")

        added_count = 0
        for vol_data in new_volumes_data:
            vol_node = OutlineNode.from_dict(vol_data)
            if vol_node.level != 1:
                vol_node.level = 1
            project.outline.children.append(vol_node)
            added_count += 1

        # 同步新增章节
        self._sync_chapters_from_outline(project)
        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)

        return added_count

    def approve_chapter(self, project: NovelProject, chapter_id: str) -> Chapter:
        """审校通过章节"""
        chapter = project.chapters.get(chapter_id)
        if not chapter:
            raise ValueError(f"章节不存在: {chapter_id}")
        chapter.status = ChapterStatus.COMPLETED
        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)
        return chapter

    def export_project(self, project: NovelProject, format: str = "txt") -> str:
        """导出完整小说"""
        return self.storage.export_full_novel(project, format=format)

    def get_project_stats(self, project: NovelProject) -> Dict[str, Any]:
        """获取项目统计信息"""
        total_chapters = len(project.chapters)
        completed = sum(1 for c in project.chapters.values() if c.status == ChapterStatus.COMPLETED)
        total_words = sum(c.word_count for c in project.chapters.values())
        return {
            "project_title": project.title,
            "total_chapters": total_chapters,
            "completed_chapters": completed,
            "total_words": total_words,
            "character_count": len(project.characters),
            "world_name": project.world.name if project.world else "未设定",
        }

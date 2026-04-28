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
    StyleReference
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
                ch.sequence_number = i
                ch.title = node.title
                ch.outline_summary = node.summary
                ch.characters_present = node.characters_involved
                ch.locations = node.locations
            elif node.title in existing_by_title:
                # 复用已有同名章节，避免重复创建
                ch = existing_by_title[node.title]
                node.chapter_id = ch.id
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
        node = OutlineNode(title=title, level=level, summary=summary)
        if parent_id is None or parent_id == project.outline.id:
            project.outline.children.append(node)
        else:
            parent = self._find_outline_node(project.outline, parent_id)
            if not parent:
                raise ValueError(f"父节点不存在: {parent_id}")
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
        max_tokens: int = 4000,
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
        使用AI分析章节正文，提取剧情记忆、新人物、新地点
        返回分析结果字典，不会自动保存到项目
        """
        if not self.generator:
            raise RuntimeError("未配置 AI 生成器")

        chapter = project.chapters.get(chapter_id)
        if not chapter:
            raise ValueError(f"章节不存在: {chapter_id}")

        existing_char_names = {c.name for c in project.characters.values()}
        existing_locations = set(project.world.locations.keys()) if project.world else set()

        prompt = (
            "请分析以下小说章节，提取结构化信息并以JSON格式返回。\n\n"
            f"章节标题：{chapter.title}\n"
            f"章节正文（前3000字）：\n{chapter.content[:3000]}\n\n"
            "请提取以下信息：\n"
            "1. plot_memory: 本章关键剧情摘要（200字以内），必须包含：\n"
            "   - 关键情节转折和重要事件结果\n"
            "   - 各主要人物在本章结束时的状态变化\n"
            "   - 新出现的重要物品或能力\n"
            "2. new_characters: 本章新出现的人物列表（已有同名人物不要重复），每人包含：\n"
            "   - name: 姓名\n"
            "   - role: 角色定位（protagonist主角/deuteragonist配角/antagonist反派/supporting次要角色/minor龙套）\n"
            "   - description: 简短描述（外貌、性格、与本章的关系）\n"
            "3. new_locations: 本章新出现的地点列表（已有同名地点不要重复），每个包含：\n"
            "   - name: 地名\n"
            "   - description: 简短描述\n\n"
            f"已知已有人物（不要重复提取）：{', '.join(existing_char_names) or '无'}\n"
            f"已知已有地点（不要重复提取）：{', '.join(existing_locations) or '无'}\n\n"
            "返回严格JSON格式，不要任何额外解释或markdown代码块标记：\n"
            '{\n  "plot_memory": "string",\n  "new_characters": [{"name": "...", "role": "...", "description": "..."}],\n  "new_locations": [{"name": "...", "description": "..."}]\n}'
        )

        request = create_request(
            prompt=prompt,
            system_message="你是一位专业的小说编辑，擅长提炼剧情要点和识别叙事要素。请严格按JSON格式输出。",
            temperature=0.3,
            max_tokens=2000,
        )

        result = self.generator.generate(request)
        if not result.success:
            raise RuntimeError(f"章节分析失败: {result.error_message}")

        # 尝试解析JSON
        text = result.text.strip()
        # 去除可能的markdown代码块标记
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()

        try:
            analysis = json.loads(text)
        except json.JSONDecodeError:
            # 如果解析失败，返回原始文本作为plot_memory
            analysis = {
                "plot_memory": text[:500],
                "new_characters": [],
                "new_locations": [],
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
        - 新增人物到人物设定
        - 新增地点到世界观
        返回应用摘要 {"plot_memory_saved": bool, "new_chars_added": int, "new_locs_added": int}
        """
        chapter = project.chapters.get(chapter_id)
        if not chapter:
            raise ValueError(f"章节不存在: {chapter_id}")

        summary = {"plot_memory_saved": False, "new_chars_added": 0, "new_locs_added": 0}

        # 保存剧情记忆
        plot_memory = analysis.get("plot_memory", "")
        if plot_memory:
            chapter.plot_memory = plot_memory
            summary["plot_memory_saved"] = True

        # 添加新人物
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
                )
                project.characters[char.id] = char
                existing_names.add(name)
                summary["new_chars_added"] += 1

        # 添加新地点
        if project.world:
            for loc_data in analysis.get("new_locations", []):
                name = loc_data.get("name", "").strip()
                desc = loc_data.get("description", "").strip()
                if name and name not in project.world.locations:
                    project.world.locations[name] = desc
                    summary["new_locs_added"] += 1

        project.updated_at = datetime.now().isoformat()
        self.storage.save(project)
        return summary

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

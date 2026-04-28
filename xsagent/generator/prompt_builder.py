"""
提示词构建器 — 将 GenerationContext 与各 Skill 模板组装为最终 LLM 提示词
"""

from typing import Dict, List, Optional, Any

from xsagent.core.models import GenerationContext, NovelProject
from xsagent.skills.skill_registry import SkillRegistry


class PromptBuilder:
    """
    提示词构建器
    负责将项目数据 + Skill 指令组装成结构化的 LLM 提示词
    """

    def __init__(self, skill_registry: Optional[SkillRegistry] = None):
        self.registry = skill_registry or SkillRegistry()

    def build_chapter_prompt(
        self,
        project: NovelProject,
        chapter_id: str,
        skill_bindings: Optional[Dict[str, str]] = None,
        extra_constraints: Optional[List[str]] = None,
    ) -> str:
        """
        构建完整的章节生成提示词
        这是系统的核心方法 — 将所有约束封装为单一提示词
        """
        ctx = project.build_generation_context(chapter_id)
        bindings = skill_bindings or project.skill_bindings

        sections: List[str] = []

        # === 1. 系统定位 ===
        sections.append(self._system_identity())

        # === 2. 世界观约束 (Skill: world_building) ===
        world_skill = self._get_skill(bindings, "world_building")
        if world_skill:
            w = project.world
            world_ctx = {
                "world_summary": ctx.world_summary,
                "world_name": w.name if w else "",
                "world_genre": w.genre if w else "",
                "world_era": w.era if w else "",
                "world_geography": w.geography if w else "",
                "world_history": w.history if w else "",
                "world_power_system": w.power_system if w else "",
                "world_society": w.society if w else "",
                "world_rules": "\n".join(f"- {r}" for r in (w.rules if w else [])),
                "world_locations": "\n".join(f"- {k}: {v}" for k, v in (w.locations.items() if w else {})),
                "world_factions": "\n".join(f"- {k}: {v}" for k, v in (w.factions.items() if w else {})),
                "world_customs": "\n".join(f"- {c}" for c in (w.customs if w else [])),
                "world_notes": w.notes if w else "",
            }
            sections.append(world_skill.render(world_ctx))
        else:
            sections.append(self._default_world_section(ctx.world_summary))

        # === 3. 大纲约束 (Skill: plot_generation) ===
        plot_skill = self._get_skill(bindings, "plot_generation")
        if plot_skill and ctx.current_node:
            plot_ctx = {
                "outline_path": " > ".join(ctx.outline_path),
                "chapter_title": ctx.current_node.title,
                "chapter_summary": ctx.current_node.summary,
                "plot_points": "\n".join(f"- {p}" for p in ctx.current_node.plot_points),
                "emotional_tone": ctx.current_node.emotional_tone,
                "previous_chapter_summary": ctx.previous_chapter_summary,
            }
            sections.append(plot_skill.render(plot_ctx))
        else:
            sections.append(self._default_plot_section(ctx))

        # === 4. 人物约束 (Skill: character_voice) ===
        char_skill = self._get_skill(bindings, "character_voice")
        if char_skill and ctx.relevant_characters:
            char_ctx = {
                "characters": self._format_characters(ctx.relevant_characters),
            }
            sections.append(char_skill.render(char_ctx))
        elif ctx.relevant_characters:
            sections.append(self._default_character_section(ctx.relevant_characters))

        # === 5. 风格约束 (Skill: style_guidance) ===
        style_skill = self._get_skill(bindings, "style_guidance")
        if style_skill:
            style_ctx = {
                "style_directives": "\n".join(ctx.style_directives),
                "sample_paragraph": project.style.sample_paragraph,
                "banned_words": ", ".join(project.style.banned_words),
            }
            sections.append(style_skill.render(style_ctx))
        else:
            sections.append(self._default_style_section(ctx.style_directives))

        # === 6. 伏笔约束 (Skill: foreshadowing) ===
        if ctx.foreshadowing_directives:
            fs_skill = self._get_skill(bindings, "foreshadowing")
            if fs_skill:
                fs_ctx = {
                    "foreshadowing_directives": "\n".join(ctx.foreshadowing_directives),
                }
                sections.append(fs_skill.render(fs_ctx))
            else:
                sections.append("## 伏笔约束\n" + "\n".join(ctx.foreshadowing_directives))

        # === 7. 文笔模仿约束 (Skill: style_mimicry) ===
        mimicry_skill = self._get_skill(bindings, "style_mimicry")
        if mimicry_skill and (ctx.mimicry_mode or ctx.style_references):
            mimicry_ctx = {
                "mimicry_mode": str(ctx.mimicry_mode),
                "reference_author": ctx.reference_author,
                "style_references": self._format_style_references(ctx.style_references),
            }
            sections.append(mimicry_skill.render(mimicry_ctx))
        elif ctx.mimicry_mode:
            sections.append(self._default_mimicry_section(ctx.reference_author, ctx.style_references))

        # === 8. 额外硬性约束 ===
        if extra_constraints:
            sections.append("## 额外约束\n")
            for c in extra_constraints:
                sections.append(f"- {c}")

        # === 9. 输出格式要求 (Skill: output_format) ===
        output_skill = self._get_skill(bindings, "output_format")
        if output_skill:
            sections.append(output_skill.render({}))
        else:
            sections.append(self._default_output_format())

        return "\n\n---\n\n".join(sections)

    def _get_skill(self, bindings: Dict[str, str], skill_type: str) -> Optional[Any]:
        """根据绑定获取 Skill"""
        name = bindings.get(skill_type)
        if name:
            return self.registry.get(name)
        return self.registry.get_default_for_type(skill_type)

    # --- 默认章节（无 Skill 时的回退） ---

    def _system_identity(self) -> str:
        return (
            "你是一位专业的小说创作 AI 助手。\n"
            "你的任务是根据用户提供的详细设定，生成高质量的小说章节内容。\n"
            "你必须严格遵守以下所有约束条件，确保输出贴合世界观、不偏离剧情主线。"
        )

    def _default_world_section(self, world_summary: str) -> str:
        return (
            "## 世界观设定\n"
            f"{world_summary}\n\n"
            "写作时必须遵守以上世界观规则，不得出现与设定矛盾的内容。"
        )

    def _default_plot_section(self, ctx: GenerationContext) -> str:
        parts = ["## 情节要求"]
        if ctx.outline_path:
            parts.append(f"当前位置: {' > '.join(ctx.outline_path)}")
        if ctx.current_node:
            parts.append(f"本章摘要: {ctx.current_node.summary}")
            if ctx.current_node.plot_points:
                parts.append("必须包含的情节点:")
                for p in ctx.current_node.plot_points:
                    parts.append(f"- {p}")
        if ctx.previous_chapter_summary:
            parts.append(f"衔接要求: 前一章 {ctx.previous_chapter_summary}")
        return "\n".join(parts)

    def _format_characters(self, characters: List[Dict]) -> str:
        lines = []
        for c in characters:
            lines.append(
                f"【{c.get('name', '未知')}】\n"
                f"  身份: {c.get('role', '')}\n"
                f"  性格: {c.get('personality', '')}\n"
                f"  动机: {c.get('motivation', '')}\n"
                f"  当前弧线: {c.get('current_arc', '')}"
            )
        return "\n\n".join(lines)

    def _default_character_section(self, characters: List[Dict]) -> str:
        return (
            "## 出场人物\n"
            f"{self._format_characters(characters)}\n\n"
            "请确保人物言行符合其性格设定和当前人物弧线。"
        )

    def _default_style_section(self, directives: List[str]) -> str:
        return (
            "## 写作风格\n"
            f"{'\n'.join(directives)}\n\n"
            "保持行文流畅，描写生动，对话自然。"
        )

    def _default_output_format(self) -> str:
        return (
            "## 输出格式\n"
            "1. 直接输出章节正文，不要添加额外解释或总结。\n"
            "2. 使用标准中文标点。\n"
            "3. 适当分段，保持阅读节奏。\n"
            "4. 章节开头用标题（如：第一章 xxx），正文紧随其后。"
        )

    def _format_style_references(self, refs: List[Dict[str, Any]]) -> str:
        if not refs:
            return "无"
        lines = []
        for r in refs:
            lines.append(f"【{r.get('name', '未命名')}】参考作者: {r.get('reference_author', '')}")
            if r.get("description"):
                lines.append(f"  风格描述: {r['description']}")
            if r.get("analyzed_traits"):
                lines.append(f"  特征标签: {', '.join(r['analyzed_traits'])}")
            if r.get("sample_texts"):
                lines.append(f"  参考片段: {r['sample_texts'][0][:100]}...")
        return "\n".join(lines)

    def _default_mimicry_section(self, author: str, refs: List[Dict[str, Any]]) -> str:
        parts = ["## 文笔模仿要求"]
        if author:
            parts.append(f"目标作者: {author}")
        if refs:
            parts.append("风格参考:")
            parts.append(self._format_style_references(refs))
        parts.append("要求：在词汇、句式、描写、对话、叙事节奏上贴合上述参考风格，但禁止直接抄袭原句。")
        return "\n".join(parts)

    def build_dialogue_prompt(
        self,
        project: NovelProject,
        characters: List[str],
        scene_context: str,
        dialogue_goal: str,
    ) -> str:
        """构建对话生成专用提示词"""
        char_infos = []
        for cid in characters:
            c = project.characters.get(cid)
            if c:
                char_infos.append(f"【{c.name}】{c.personality}")

        prompt = (
            "请为以下场景生成一段人物对话:\n\n"
            f"场景背景: {scene_context}\n\n"
            f"对话目的: {dialogue_goal}\n\n"
            "出场人物:\n" + "\n".join(char_infos) + "\n\n"
            "要求:\n"
            "- 对话符合各人物性格\n"
            "- 自然流畅，避免说教\n"
            "- 通过对话推进情节或揭示人物关系\n"
            "- 只输出对话内容，用 '人物名: 台词' 的格式"
        )
        return prompt

    def build_scene_prompt(
        self,
        project: NovelProject,
        location: str,
        atmosphere: str,
        key_elements: List[str],
    ) -> str:
        """构建场景描写专用提示词"""
        loc_desc = ""
        if project.world and location in project.world.locations:
            loc_desc = project.world.locations[location]

        prompt = (
            "请生成一段场景描写:\n\n"
            f"地点: {location}\n"
            f"地点设定: {loc_desc}\n"
            f"氛围: {atmosphere}\n"
            f"需提及的元素: {', '.join(key_elements)}\n\n"
            "要求:\n"
            "- 调动五感（视、听、嗅、触、味）\n"
            "- 氛围渲染到位\n"
            "- 为即将发生的情节做铺垫\n"
            "- 不超过 500 字"
        )
        return prompt

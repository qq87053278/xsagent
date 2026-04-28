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

    def _extract_chapter_notes(self, notes: str) -> Dict[str, str]:
        """从 chapter.notes 中解析情感基调和情节点"""
        result = {"emotional_tone": "", "plot_points": ""}
        if not notes:
            return result
        lines = notes.splitlines()
        in_plot_points = False
        plot_lines = []
        for line in lines:
            if line.startswith("情感基调:"):
                result["emotional_tone"] = line.split(":", 1)[1].strip()
            elif line.startswith("情节点:"):
                in_plot_points = True
            elif in_plot_points:
                plot_lines.append(line.strip())
        result["plot_points"] = "\n".join(plot_lines)
        return result

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
        chapter = project.chapters.get(chapter_id)
        # 优先使用用户在「情节流程」中输入的章节级数据
        chapter_notes = self._extract_chapter_notes(chapter.notes if chapter else "")
        chapter_summary = chapter.outline_summary if chapter and chapter.outline_summary else (ctx.current_node.summary if ctx.current_node else "")
        plot_points = chapter_notes["plot_points"] or ("\n".join(f"- {p}" for p in ctx.current_node.plot_points) if ctx.current_node else "")
        emotional_tone = chapter_notes["emotional_tone"] or (ctx.current_node.emotional_tone if ctx.current_node else "")

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
                "chapter_summary": chapter_summary,
                "plot_points": plot_points,
                "emotional_tone": emotional_tone,
                "previous_chapter_summary": ctx.previous_chapter_summary,
            }
            sections.append(plot_skill.render(plot_ctx))
        else:
            sections.append(self._default_plot_section(ctx, chapter_summary, plot_points, emotional_tone))

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

        # === 7. 逻辑一致性约束 (Skill: logic_consistency) ===
        logic_skill = self._get_skill(bindings, "logic_consistency")
        if logic_skill:
            logic_ctx = {
                "world_summary": ctx.world_summary,
                "previous_chapter_plot_memory": ctx.previous_chapter_plot_memory,
                "relevant_characters": self._format_characters(ctx.relevant_characters) if ctx.relevant_characters else "无",
            }
            sections.append(logic_skill.render(logic_ctx))
        else:
            sections.append(self._default_logic_section(ctx))

        # === 8. 文笔模仿约束 (Skill: style_mimicry) ===
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

        # === 9. 额外硬性约束 ===
        if extra_constraints:
            sections.append("## 额外约束\n")
            for c in extra_constraints:
                sections.append(f"- {c}")

        # === 10. 输出格式要求 (Skill: output_format) ===
        output_skill = self._get_skill(bindings, "output_format")
        if output_skill:
            sections.append(output_skill.render({}))
        else:
            sections.append(self._default_output_format())

        return "\n\n---\n\n".join(sections)

    def get_chapter_prompt_info(
        self,
        project: NovelProject,
        chapter_id: str,
        skill_bindings: Optional[Dict[str, str]] = None,
        extra_constraints: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        获取章节生成的完整提示词以及实际使用的 Skill 信息
        返回 {"prompt": str, "skills": List[Dict]}
        """
        ctx = project.build_generation_context(chapter_id)
        bindings = skill_bindings or project.skill_bindings
        chapter = project.chapters.get(chapter_id)
        chapter_notes = self._extract_chapter_notes(chapter.notes if chapter else "")

        skills_used: List[Dict[str, Any]] = []

        # === 1. 系统定位 ===
        skills_used.append({
            "type": "system_identity",
            "label": "系统定位",
            "name": "默认系统定位",
            "description": "定义 AI 助手身份与核心任务",
        })

        # === 2. 世界观约束 ===
        world_skill = self._get_skill(bindings, "world_building")
        if world_skill:
            skills_used.append({
                "type": world_skill.skill_type or "world_building",
                "label": "世界观约束",
                "name": world_skill.name,
                "description": world_skill.description or "",
            })
        else:
            skills_used.append({
                "type": "world_building",
                "label": "世界观约束",
                "name": "默认世界观",
                "description": "使用项目世界观摘要作为约束",
            })

        # === 3. 大纲约束 ===
        plot_skill = self._get_skill(bindings, "plot_generation")
        if plot_skill and ctx.current_node:
            skills_used.append({
                "type": plot_skill.skill_type or "plot_generation",
                "label": "大纲约束",
                "name": plot_skill.name,
                "description": plot_skill.description or "",
            })
        elif ctx.current_node:
            skills_used.append({
                "type": "plot_generation",
                "label": "大纲约束",
                "name": "默认大纲",
                "description": "使用当前章节大纲节点信息",
            })

        # === 4. 人物约束 ===
        char_skill = self._get_skill(bindings, "character_voice")
        if char_skill and ctx.relevant_characters:
            skills_used.append({
                "type": char_skill.skill_type or "character_voice",
                "label": "人物约束",
                "name": char_skill.name,
                "description": char_skill.description or "",
            })
        elif ctx.relevant_characters:
            skills_used.append({
                "type": "character_voice",
                "label": "人物约束",
                "name": "默认人物",
                "description": "使用出场人物设定作为约束",
            })

        # === 5. 风格约束 ===
        style_skill = self._get_skill(bindings, "style_guidance")
        if style_skill:
            skills_used.append({
                "type": style_skill.skill_type or "style_guidance",
                "label": "风格约束",
                "name": style_skill.name,
                "description": style_skill.description or "",
            })
        else:
            skills_used.append({
                "type": "style_guidance",
                "label": "风格约束",
                "name": "默认风格",
                "description": "使用项目风格设定作为约束",
            })

        # === 6. 伏笔约束 ===
        if ctx.foreshadowing_directives:
            fs_skill = self._get_skill(bindings, "foreshadowing")
            if fs_skill:
                skills_used.append({
                    "type": fs_skill.skill_type or "foreshadowing",
                    "label": "伏笔约束",
                    "name": fs_skill.name,
                    "description": fs_skill.description or "",
                })
            else:
                skills_used.append({
                    "type": "foreshadowing",
                    "label": "伏笔约束",
                    "name": "默认伏笔",
                    "description": "使用本章绑定的伏笔信息",
                })

        # === 7. 逻辑一致性约束 ===
        logic_skill = self._get_skill(bindings, "logic_consistency")
        if logic_skill:
            skills_used.append({
                "type": logic_skill.skill_type or "logic_consistency",
                "label": "逻辑一致性约束",
                "name": logic_skill.name,
                "description": logic_skill.description or "",
            })
        else:
            skills_used.append({
                "type": "logic_consistency",
                "label": "逻辑一致性约束",
                "name": "默认逻辑约束",
                "description": "使用默认因果逻辑、时空连贯与常识约束",
            })

        # === 8. 文笔模仿约束 ===
        mimicry_skill = self._get_skill(bindings, "style_mimicry")
        if mimicry_skill and (ctx.mimicry_mode or ctx.style_references):
            skills_used.append({
                "type": mimicry_skill.skill_type or "style_mimicry",
                "label": "文笔模仿约束",
                "name": mimicry_skill.name,
                "description": mimicry_skill.description or "",
            })
        elif ctx.mimicry_mode:
            skills_used.append({
                "type": "style_mimicry",
                "label": "文笔模仿约束",
                "name": "默认文笔模仿",
                "description": "使用设定的模仿作者与风格参考",
            })

        # === 9. 额外约束 ===
        if extra_constraints:
            skills_used.append({
                "type": "extra_constraints",
                "label": "额外约束",
                "name": "用户额外约束",
                "description": "用户本次生成时附加的硬性约束",
            })

        # === 10. 输出格式要求 ===
        output_skill = self._get_skill(bindings, "output_format")
        if output_skill:
            skills_used.append({
                "type": output_skill.skill_type or "output_format",
                "label": "输出格式要求",
                "name": output_skill.name,
                "description": output_skill.description or "",
            })
        else:
            skills_used.append({
                "type": "output_format",
                "label": "输出格式要求",
                "name": "默认输出格式",
                "description": "规定章节正文的输出格式规范",
            })

        prompt = self.build_chapter_prompt(
            project=project,
            chapter_id=chapter_id,
            skill_bindings=skill_bindings,
            extra_constraints=extra_constraints,
        )
        return {"prompt": prompt, "skills": skills_used}

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
            "你必须严格遵守以下所有约束条件，确保输出贴合世界观、不偏离剧情主线。\n"
            "在创作过程中，你须以严密的逻辑推演情节：因果链条必须完整，时间空间必须连贯，"
            "人物行为必须基于其动机与已知信息，任何事件都不能违背基本常识与世界观设定。"
        )

    def _default_world_section(self, world_summary: str) -> str:
        return (
            "## 世界观设定\n"
            f"{world_summary}\n\n"
            "写作时必须遵守以上世界观规则，不得出现与设定矛盾的内容。"
        )

    def _default_plot_section(
        self,
        ctx: GenerationContext,
        chapter_summary: str = "",
        plot_points: str = "",
        emotional_tone: str = "",
    ) -> str:
        parts = ["## 情节要求"]
        if ctx.outline_path:
            parts.append(f"当前位置: {' > '.join(ctx.outline_path)}")
        if chapter_summary:
            parts.append(f"本章摘要: {chapter_summary}")
        if plot_points:
            parts.append("必须包含的情节点:")
            for line in plot_points.splitlines():
                if line.strip():
                    parts.append(f"- {line.strip()}")
        if emotional_tone:
            parts.append(f"情感基调: {emotional_tone}")
        if ctx.previous_chapter_summary:
            parts.append(f"衔接要求: 前一章 {ctx.previous_chapter_summary}")
        if ctx.previous_chapter_plot_memory:
            parts.append("\n【前一章剧情记忆 — 情节提要】")
            parts.append("上一章的关键剧情与人物状态摘要，新章节必须在此基础上推进：")
            parts.append(ctx.previous_chapter_plot_memory)
        if ctx.previous_chapter_content:
            parts.append("\n【前一章结尾片段 — 衔接锚点】")
            parts.append("以下是上一章的最后部分，仅作为续写起点。你严禁复述或重写上一章已发生的情节，必须直接续写新篇章内容，从上一章结束的地方自然推进：")
            parts.append(ctx.previous_chapter_content)
        if ctx.previous_plot_memories:
            parts.append("\n【更早章节剧情记忆 — 参考约束】")
            parts.append("以下是你之前章节的关键剧情摘要，作为背景参考，必须遵循不能矛盾：")
            for mem in ctx.previous_plot_memories:
                parts.append(f"- {mem}")
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

    def _default_logic_section(self, ctx: GenerationContext) -> str:
        parts = [
            "## 逻辑一致性与常识约束",
            "",
            "你创作的内容必须严格遵守以下逻辑原则：",
            "",
            "### 因果逻辑",
            "1. 凡事有因：任何事件的发生必须有明确、合理的前置原因。",
            "2. 结果合理：角色的行动必须产生符合情境的结果，小因不能引发大果。",
            "3. 连锁反应：重大事件发生后，必须考虑其对后续情节的合理影响。",
            "",
            "### 时间空间逻辑",
            "1. 时间连贯：事件顺序清晰，禁止无法解释的时间跳跃。",
            "2. 行动耗时：移动、任务、学习都必须消耗合理时间，禁止瞬移或速成。",
            "3. 移动合理：地理位置变化必须符合交通方式和世界设定。",
            "",
            "### 人物行为逻辑",
            "1. 动机驱动：角色的决策必须基于其性格、动机和已知信息。",
            "2. 能力边界：角色解决问题的方式不能超出其能力范围。",
            "3. 信息差尊重：角色只能基于自己已知的信息做出判断。",
            "4. 情绪连贯：情绪变化必须有铺垫和过渡。",
            "",
            "### 社会与常识逻辑",
            "1. 社会规则：角色行为必须符合世界设定的社会结构和权力关系。",
            "2. 经济常识：金钱、资源、权力的获取和消耗必须合理。",
            "3. 生存常识：受伤需要恢复、疲劳需要休息，禁止'永动机'角色。",
        ]
        if ctx.previous_chapter_plot_memory:
            parts.append("")
            parts.append("### 衔接一致性")
            parts.append("本章必须与前一章的剧情记忆保持严格一致，不得矛盾或忽略已发生的事件。")
        return "\n".join(parts)

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

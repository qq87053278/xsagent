"""
Skill 注册表 — 管理所有 Skill 文件的加载、查询与绑定
"""

import os
from pathlib import Path
from typing import Dict, List, Optional

from .skill_parser import SkillParser, SkillFile


class SkillRegistry:
    """Skill 注册表"""

    BUILTIN_SKILL_DIR = Path(__file__).parent / "builtin"

    def __init__(self):
        self._skills: Dict[str, SkillFile] = {}  # {name: SkillFile}
        self._type_index: Dict[str, List[str]] = {}  # {skill_type: [name1, name2]}

    def load_builtin_skills(self) -> int:
        """加载内置 Skill 文件，返回加载数量"""
        count = 0
        if not self.BUILTIN_SKILL_DIR.exists():
            return count
        for file_path in self.BUILTIN_SKILL_DIR.glob("*.md"):
            try:
                skill = SkillParser.parse_file(str(file_path))
                self.register(skill)
                count += 1
            except Exception as e:
                print(f"[SkillRegistry] 加载失败 {file_path}: {e}")
        return count

    def load_from_directory(self, directory: str) -> int:
        """从指定目录加载所有 .md Skill 文件"""
        count = 0
        dir_path = Path(directory)
        if not dir_path.exists():
            return count
        for file_path in dir_path.rglob("*.md"):
            try:
                skill = SkillParser.parse_file(str(file_path))
                self.register(skill)
                count += 1
            except Exception as e:
                print(f"[SkillRegistry] 加载失败 {file_path}: {e}")
        return count

    def register(self, skill: SkillFile) -> None:
        """注册一个 Skill"""
        self._skills[skill.name] = skill
        skill_type = skill.skill_type or "misc"
        if skill_type not in self._type_index:
            self._type_index[skill_type] = []
        if skill.name not in self._type_index[skill_type]:
            self._type_index[skill_type].append(skill.name)

    def get(self, name: str) -> Optional[SkillFile]:
        """按名称获取 Skill"""
        return self._skills.get(name)

    def list_all(self) -> List[str]:
        """列出所有已注册 Skill 名称"""
        return list(self._skills.keys())

    def list_by_type(self, skill_type: str) -> List[SkillFile]:
        """按类型获取 Skill 列表"""
        names = self._type_index.get(skill_type, [])
        return [self._skills[n] for n in names if n in self._skills]

    def get_default_for_type(self, skill_type: str) -> Optional[SkillFile]:
        """获取某类型的默认 Skill（该类型第一个）"""
        skills = self.list_by_type(skill_type)
        return skills[0] if skills else None

    def build_context_with_skill(
        self,
        skill_name: str,
        base_context: Dict,
        skill_directive_key: str = "skill_directive"
    ) -> Dict:
        """
        将 Skill 模板渲染后注入到上下文中
        返回新的上下文副本
        """
        skill = self.get(skill_name)
        if not skill:
            return dict(base_context)

        ctx = dict(base_context)
        rendered = skill.render(ctx)
        ctx[skill_directive_key] = rendered
        return ctx

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __len__(self) -> int:
        return len(self._skills)

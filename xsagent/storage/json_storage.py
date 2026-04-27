"""
JSON 文件存储系统 — 负责 NovelProject 的持久化读写
"""

import json
import os
from pathlib import Path
from typing import Optional, Any

from xsagent.core.models import NovelProject


class JSONStorage:
    """JSON 存储引擎"""

    DEFAULT_PROJECTS_DIR = Path("projects")

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir) if base_dir else self.DEFAULT_PROJECTS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _project_path(self, project_id: str) -> Path:
        return self.base_dir / project_id / "project.json"

    def _project_dir(self, project_id: str) -> Path:
        path = self.base_dir / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, project: NovelProject, pretty: bool = True) -> str:
        """
        保存项目到 JSON 文件
        返回保存的文件路径
        """
        self._project_dir(project.id)
        file_path = self._project_path(project.id)

        data = project.to_dict()
        kwargs = {"ensure_ascii": False}
        if pretty:
            kwargs["indent"] = 2

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, **kwargs)

        # 同时保存一个独立的人物设定文件便于人工查阅
        self._save_characters_sheet(project)
        self._save_outline_sheet(project)

        return str(file_path)

    def load(self, project_id: str) -> Optional[NovelProject]:
        """从 JSON 文件加载项目"""
        file_path = self._project_path(project_id)
        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return NovelProject.from_dict(data)

    def delete(self, project_id: str) -> bool:
        """删除项目"""
        import shutil
        dir_path = self.base_dir / project_id
        if dir_path.exists():
            shutil.rmtree(dir_path)
            return True
        return False

    def list_projects(self) -> list:
        """列出所有项目ID"""
        if not self.base_dir.exists():
            return []
        return [d.name for d in self.base_dir.iterdir() if d.is_dir()]

    def export_chapter(self, project: NovelProject, chapter_id: str, format: str = "txt") -> str:
        """
        导出单个章节为文本文件
        返回导出文件路径
        """
        chapter = project.chapters.get(chapter_id)
        if not chapter:
            raise ValueError(f"章节不存在: {chapter_id}")

        out_dir = self._project_dir(project.id) / "exports"
        out_dir.mkdir(exist_ok=True)

        if format == "txt":
            file_path = out_dir / f"{chapter.sequence_number:03d}_{chapter.title}.txt"
            content = (
                f"第{chapter.sequence_number}章 {chapter.title}\n"
                f"{'=' * 40}\n\n"
                f"{chapter.content}\n"
            )
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        elif format == "md":
            file_path = out_dir / f"{chapter.sequence_number:03d}_{chapter.title}.md"
            content = (
                f"# 第{chapter.sequence_number}章 {chapter.title}\n\n"
                f"> 状态: {chapter.status.value}\n\n"
                f"{chapter.content}\n"
            )
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            raise ValueError(f"不支持的导出格式: {format}")

        return str(file_path)

    def export_full_novel(self, project: NovelProject, format: str = "txt") -> str:
        """导出完整小说"""
        out_dir = self._project_dir(project.id) / "exports"
        out_dir.mkdir(exist_ok=True)

        safe_title = "".join(c for c in project.title if c.isalnum() or c in "_ -").strip()
        file_path = out_dir / f"{safe_title}_全文.{format}"

        chapters = sorted(project.chapters.values(), key=lambda c: c.sequence_number)

        lines = []
        if format == "md":
            lines.append(f"# {project.title}\n")
            if project.author:
                lines.append(f"**作者: {project.author}**\n")
            lines.append("\n---\n")
        else:
            lines.append(f"{project.title}\n")
            if project.author:
                lines.append(f"作者: {project.author}\n")
            lines.append("=" * 40 + "\n")

        for ch in chapters:
            if format == "md":
                lines.append(f"\n## 第{ch.sequence_number}章 {ch.title}\n")
                lines.append(f"\n{ch.content}\n")
            else:
                lines.append(f"\n第{ch.sequence_number}章 {ch.title}\n")
                lines.append("-" * 20 + "\n")
                lines.append(f"{ch.content}\n")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return str(file_path)

    def _save_characters_sheet(self, project: NovelProject) -> None:
        """保存人物设定表（便于人工查阅）"""
        if not project.characters:
            return
        file_path = self._project_dir(project.id) / "characters.md"
        lines = [f"# 《{project.title}》人物设定表\n\n"]
        for char in project.characters.values():
            lines.append(f"## {char.name}")
            if char.alias:
                lines.append(f"- 别名: {', '.join(char.alias)}")
            lines.append(f"- 角色定位: {char.role.value}")
            lines.append(f"- 性格: {char.personality}")
            lines.append(f"- 动机: {char.motivation}")
            lines.append(f"- 人物弧线: {char.arc}")
            if char.relationships:
                lines.append("- 关系网:")
                for name, rel in char.relationships.items():
                    lines.append(f"  - {name}: {rel}")
            lines.append(f"- 备注: {char.notes}\n")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _save_outline_sheet(self, project: NovelProject) -> None:
        """保存大纲表"""
        if not project.outline:
            return
        file_path = self._project_dir(project.id) / "outline.md"
        lines = [f"# 《{project.title}》故事大纲\n\n"]

        def walk(node: Any, depth: int = 0) -> None:
            prefix = "  " * depth
            lines.append(f"{prefix}- **{node.title}**")
            if node.summary:
                lines.append(f"{prefix}  - 摘要: {node.summary}")
            if node.plot_points:
                lines.append(f"{prefix}  - 情节点: {', '.join(node.plot_points)}")
            for child in node.children:
                walk(child, depth + 1)

        walk(project.outline)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

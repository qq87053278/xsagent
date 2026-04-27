"""
Skill 文件解析器
Skill 文件采用 Markdown + YAML Frontmatter 格式，封装 AI 生成约束与指令模板
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Any

import yaml


@dataclass
class SkillFile:
    """解析后的 Skill 文件对象"""
    name: str = ""
    version: str = "1.0"
    description: str = ""
    skill_type: str = ""                    # world_building / plot_generation / dialogue / scene / style / consistency
    variables: List[str] = field(default_factory=list)  # 模板变量列表
    template: str = ""                      # 提示词模板正文
    meta: Dict[str, Any] = field(default_factory=dict)  # 扩展元数据
    source_path: Optional[str] = None

    def render(self, context: Dict[str, Any]) -> str:
        """
        使用上下文变量渲染模板
        支持 {{variable}} 和 {variable} 两种占位符
        """
        result = self.template
        for key, value in context.items():
            placeholder1 = f"{{{{{key}}}}}"
            placeholder2 = f"{{{key}}}"
            str_value = str(value) if value is not None else ""
            result = result.replace(placeholder1, str_value)
            result = result.replace(placeholder2, str_value)
        return result

    def validate_context(self, context: Dict[str, Any]) -> List[str]:
        """检查上下文是否包含所有必需变量，返回缺失变量列表"""
        missing = []
        for var in self.variables:
            if var not in context or context[var] is None or context[var] == "":
                missing.append(var)
        return missing


class SkillParser:
    """Skill 文件解析器"""

    FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

    @classmethod
    def parse(cls, content: str, source_path: Optional[str] = None) -> SkillFile:
        """解析 Skill 文件内容"""
        match = cls.FRONTMATTER_PATTERN.match(content.strip())
        if not match:
            # 无 frontmatter，全文作为模板
            return SkillFile(
                name="unnamed",
                template=content.strip(),
                source_path=source_path,
            )

        frontmatter_text, template = match.groups()
        try:
            meta = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"YAML Frontmatter 解析失败: {e}")

        return SkillFile(
            name=meta.get("name", "unnamed"),
            version=str(meta.get("version", "1.0")),
            description=meta.get("description", ""),
            skill_type=meta.get("skill_type", meta.get("type", "")),
            variables=meta.get("variables", []),
            template=template.strip(),
            meta={k: v for k, v in meta.items() if k not in {
                "name", "version", "description", "skill_type", "type", "variables"
            }},
            source_path=source_path,
        )

    @classmethod
    def parse_file(cls, file_path: str) -> SkillFile:
        """从文件路径解析 Skill"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Skill 文件不存在: {file_path}")
        content = path.read_text(encoding="utf-8")
        return cls.parse(content, source_path=str(path.resolve()))

    @classmethod
    def auto_extract_variables(cls, template: str) -> List[str]:
        """自动从模板中提取 {{variable}} 或 {variable} 变量名"""
        pattern = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}")
        return list(set(pattern.findall(template)))

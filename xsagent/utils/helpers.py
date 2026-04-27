"""
通用工具函数
"""

import re
from typing import List, Optional


def count_chinese_words(text: str) -> int:
    """统计中文字符数量（作为中文字数估算）"""
    if not text:
        return 0
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def count_total_words(text: str) -> int:
    """统计总字数（中文字符 + 英文单词）"""
    if not text:
        return 0
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    english = len(re.findall(r"[a-zA-Z]+", text))
    return chinese + english


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """截断文本到指定长度"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def split_into_scenes(text: str) -> List[str]:
    """
    将章节正文按场景切分
    以换行分段或明显的场景转换词作为分界
    """
    # 以两个及以上换行作为场景分隔
    scenes = re.split(r"\n\s*\n", text.strip())
    return [s.strip() for s in scenes if s.strip()]


def extract_dialogue(text: str) -> List[dict]:
    """从文本中提取对话片段 {speaker, content}"""
    # 匹配 "某某: ..." 或 "某某说: ..." 格式
    pattern = re.compile(r"[\"\"]([^\"\"]+)[\"\"]|([\u4e00-\u9fff\w]+)[：:]\s*([\"\"]?[^\"\"\n]+[\"\"]?)")
    dialogues = []
    for match in pattern.finditer(text):
        speaker = match.group(2) or "未知"
        content = match.group(3) or match.group(1) or ""
        dialogues.append({"speaker": speaker.strip(), "content": content.strip().strip('""')})
    return dialogues


def sanitize_filename(name: str) -> str:
    """清理字符串，使其适合作为文件名"""
    return "".join(c for c in name if c.isalnum() or c in "_ -").strip()


def format_numbered_list(items: List[str], start: int = 1) -> str:
    """格式化为编号列表"""
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, start))


def format_bullet_list(items: List[str]) -> str:
    """格式化为项目符号列表"""
    return "\n".join(f"- {item}" for item in items)

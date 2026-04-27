"""
配置加载器 — 加载 YAML 配置文件并解析为字典
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


DEFAULT_CONFIG_PATH = Path("config.yaml")


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    """加载配置文件"""
    if not HAS_YAML:
        raise ImportError("请安装 pyyaml: pip install pyyaml")

    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # 环境变量覆写
    if os.getenv("OPENAI_API_KEY"):
        config.setdefault("model", {})
        config["model"]["api_key"] = os.getenv("OPENAI_API_KEY")

    return config


def get_model_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """提取模型配置"""
    return config.get("model", {})


def get_storage_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """提取存储配置"""
    return config.get("storage", {})


def get_skills_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """提取 Skill 配置"""
    return config.get("skills", {})

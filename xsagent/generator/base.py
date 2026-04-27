"""
AI 生成器基类与统一接口
支持多模型后端扩展（OpenAI, Claude, 本地模型等）
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Generator as TypingGenerator
from enum import Enum


class ModelBackend(str, Enum):
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    CUSTOM = "custom"


@dataclass
class GenerationRequest:
    """生成请求"""
    prompt: str = ""
    system_message: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0
    stop_sequences: List[str] = field(default_factory=list)
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    """生成结果"""
    text: str = ""
    model: str = ""
    usage: Dict[str, int] = field(default_factory=dict)  # {prompt_tokens, completion_tokens, total_tokens}
    finish_reason: str = ""
    raw_response: Any = None
    success: bool = True
    error_message: str = ""


class BaseGenerator(ABC):
    """生成器抽象基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_name = config.get("model", "gpt-4")
        self.default_temperature = config.get("temperature", 0.7)
        self.default_max_tokens = config.get("max_tokens", 4000)

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """同步生成文本"""
        pass

    @abstractmethod
    def generate_stream(self, request: GenerationRequest) -> TypingGenerator[str, None, None]:
        """流式生成文本，逐字/逐段返回"""
        pass

    def health_check(self) -> bool:
        """检查服务可用性"""
        return True

    def get_name(self) -> str:
        return f"{self.__class__.__name__}({self.model_name})"


class GeneratorFactory:
    """生成器工厂"""

    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, backend: str, generator_class: type):
        cls._registry[backend] = generator_class

    @classmethod
    def create(cls, backend: str, config: Dict[str, Any]) -> BaseGenerator:
        if backend not in cls._registry:
            raise ValueError(f"未知的模型后端: {backend}，已注册: {list(cls._registry.keys())}")
        return cls._registry[backend](config)

    @classmethod
    def list_backends(cls) -> List[str]:
        return list(cls._registry.keys())


def create_request(
    prompt: str,
    system_message: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    **kwargs
) -> GenerationRequest:
    """快捷创建生成请求"""
    return GenerationRequest(
        prompt=prompt,
        system_message=system_message,
        temperature=temperature,
        max_tokens=max_tokens,
        extra_params=kwargs,
    )

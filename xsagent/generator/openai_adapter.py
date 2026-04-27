"""
OpenAI / Azure OpenAI 适配器
"""

import os
from typing import Generator as TypingGenerator, Any, Dict

try:
    import openai
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

from .base import BaseGenerator, GenerationRequest, GenerationResult, GeneratorFactory


class OpenAIGenerator(BaseGenerator):
    """OpenAI API 适配器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if not HAS_OPENAI:
            raise ImportError("请安装 openai 包: pip install openai")

        api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY")
        base_url = config.get("base_url")
        timeout = config.get("timeout", 120)

        client_kwargs = {"api_key": api_key, "timeout": timeout}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = OpenAI(**client_kwargs)
        self.model = config.get("model", "gpt-4o")

    def generate(self, request: GenerationRequest) -> GenerationResult:
        messages = []
        if request.system_message:
            messages.append({"role": "system", "content": request.system_message})
        messages.append({"role": "user", "content": request.prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens or self.default_max_tokens,
                top_p=request.top_p,
                stop=request.stop_sequences or None,
                **request.extra_params
            )
            choice = response.choices[0]
            return GenerationResult(
                text=choice.message.content or "",
                model=self.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                } if response.usage else {},
                finish_reason=choice.finish_reason or "",
                raw_response=response,
            )
        except Exception as e:
            return GenerationResult(
                text="",
                model=self.model,
                success=False,
                error_message=str(e),
            )

    def generate_stream(self, request: GenerationRequest) -> TypingGenerator[str, None, None]:
        messages = []
        if request.system_message:
            messages.append({"role": "system", "content": request.system_message})
        messages.append({"role": "user", "content": request.prompt})

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens or self.default_max_tokens,
                top_p=request.top_p,
                stop=request.stop_sequences or None,
                stream=True,
                **request.extra_params
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            yield f"\n[生成错误: {e}]"

    def health_check(self) -> bool:
        try:
            self.client.models.list()
            return True
        except Exception:
            return False


class AzureOpenAIGenerator(OpenAIGenerator):
    """Azure OpenAI 适配器"""

    def __init__(self, config: Dict[str, Any]):
        # 强制使用 Azure 参数
        config["base_url"] = config.get("azure_endpoint") or config.get("base_url")
        api_key = config.get("api_key") or os.getenv("AZURE_OPENAI_API_KEY")
        config["api_key"] = api_key
        super().__init__(config)


# 注册到工厂
GeneratorFactory.register("openai", OpenAIGenerator)
GeneratorFactory.register("azure_openai", AzureOpenAIGenerator)

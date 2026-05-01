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
        self.thinking = config.get("thinking", False)
        self.thinking_budget = config.get("thinking_budget_tokens", 0)

    def _build_thinking_params(self, extra_params: Dict[str, Any]) -> Dict[str, Any]:
        """构建思考模式参数，通过 extra_body 传递给 API"""
        params = dict(extra_params)
        extra_body = dict(params.pop("extra_body", {}) or {})

        # 如果请求中明确禁用思考模式，尊重请求级配置
        if extra_body.get("enable_thinking") is False:
            params["extra_body"] = extra_body
            return params

        if not self.thinking:
            return extra_params

        # 思考模式参数需通过 extra_body 传递（OpenAI SDK 不接受未知顶层参数）
        extra_body.setdefault("enable_thinking", True)
        if self.thinking_budget > 0:
            extra_body.setdefault("thinking_budget", self.thinking_budget)
        params["extra_body"] = extra_body
        return params

    def _use_thinking(self, extra_params: Dict[str, Any]) -> bool:
        """判断本次请求是否实际启用思考模式"""
        extra_body = extra_params.get("extra_body", {}) or {}
        if extra_body.get("enable_thinking") is False:
            return False
        return self.thinking

    @staticmethod
    def _extract_reasoning(choice) -> str:
        """从响应中提取思考过程文本"""
        msg = choice.message
        # DeepSeek: reasoning_content
        if hasattr(msg, "reasoning_content") and msg.reasoning_content:
            return msg.reasoning_content
        # 兼容其他提供商可能的字段名
        if hasattr(msg, "thinking") and msg.thinking:
            return msg.thinking
        return ""

    def generate(self, request: GenerationRequest) -> GenerationResult:
        messages = []
        if request.system_message:
            messages.append({"role": "system", "content": request.system_message})
        messages.append({"role": "user", "content": request.prompt})

        extra = self._build_thinking_params(request.extra_params)
        resolved_max = request.max_tokens or self.default_max_tokens

        try:
            call_kwargs = dict(
                model=self.model,
                messages=messages,
                temperature=request.temperature,
                top_p=request.top_p,
                stop=request.stop_sequences or None,
                **extra,
            )
            # 思考模式下 DeepSeek 不接受 max_tokens，需改用 max_completion_tokens
            if self._use_thinking(extra):
                call_kwargs["max_completion_tokens"] = resolved_max
            else:
                call_kwargs["max_tokens"] = resolved_max

            response = self.client.chat.completions.create(**call_kwargs)
            choice = response.choices[0]
            reasoning = self._extract_reasoning(choice)
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
                reasoning_content=reasoning,
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

        extra = self._build_thinking_params(request.extra_params)
        resolved_max = request.max_tokens or self.default_max_tokens

        try:
            call_kwargs = dict(
                model=self.model,
                messages=messages,
                temperature=request.temperature,
                top_p=request.top_p,
                stop=request.stop_sequences or None,
                stream=True,
                **extra,
            )
            if self._use_thinking(extra):
                call_kwargs["max_completion_tokens"] = resolved_max
            else:
                call_kwargs["max_tokens"] = resolved_max

            stream = self.client.chat.completions.create(**call_kwargs)
            for chunk in stream:
                delta = chunk.choices[0].delta
                # 跳过思考过程的流式输出，只输出最终内容
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    continue
                if delta.content:
                    yield delta.content
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

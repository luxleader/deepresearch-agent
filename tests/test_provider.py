import json

import httpx

from deepresearch_app.models import ResearchPlan
from deepresearch_app.providers import JSONModel
from deepresearch_app.settings import Settings


async def test_qwen_non_thinking_json_request_and_token_accounting():
    def handler(request):
        body = json.loads(request.content)
        assert str(request.url) == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        assert body["enable_thinking"] is False
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "questions": ["研究成本"], "required_dimensions": ["成本"]})}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 4}})

    model = JSONModel(Settings(model="qwen-plus", api_key="fixture", provider="qwen",
                               api_base="https://dashscope.aliyuncs.com/compatible-mode/v1"),
                      transport=httpx.MockTransport(handler))
    plan = await model.generate("test", ResearchPlan)
    assert plan.required_dimensions == ["成本"]
    assert model.usage == {"prompt_tokens": 10, "completion_tokens": 4}

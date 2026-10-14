import json


def encode_prompt(stage, payload):
    return stage + "\n" + json.dumps(payload, ensure_ascii=False)


def plan_prompt(request):
    return encode_prompt("PLAN：按使用约束拆解最多3个子问题，列必须回答的维度；优先官方文档与论文。",
                         {"request": request.model_dump(mode="json")})


def gaps_prompt(state):
    return encode_prompt("GAPS：基于已支持证据逐项判断维度覆盖，只对缺失或冲突项补搜；足够时结束。",
                         {"state": state.model_dump(mode="json")})


def report_prompt(state, errors=None):
    return encode_prompt("REPORT：中文报告，所有段落引用claims账本。fact.text逐字复用supported evidence.claim。"
                         "建议标recommendation，缺证据/冲突/过期标uncertainty。不要生成URL。摘要和表格只用claim ID，"
                         "comparison.label和aspects的键也必须是名称/维度对应的claim ID，不允许自由文本。",
                         {"state": state.model_dump(mode="json"), "repair_errors": errors})

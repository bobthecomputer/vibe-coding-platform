from __future__ import annotations

from dataclasses import asdict, dataclass

from .skills import Skill


@dataclass
class OpenAIRequestPlan:
    model: str
    input: list[dict]
    tools: list[dict]
    previous_response_id: str | None = None
    conversation: str | None = None
    store: bool = False

    def as_dict(self) -> dict:
        payload = asdict(self)
        if self.previous_response_id is None:
            payload.pop("previous_response_id")
        if self.conversation is None:
            payload.pop("conversation")
        return payload


def tools_from_skills(skills: list[Skill]) -> list[dict]:
    tools: list[dict] = []
    for skill in skills:
        tools.append(
            {
                "type": "function",
                "name": skill.name,
                "description": skill.description,
                "parameters": skill.schema or {"type": "object", "properties": {}},
                "strict": True,
            }
        )
    return tools


def build_responses_request(
    objective: str,
    model: str,
    tools: list[dict],
    previous_response_id: str | None = None,
    conversation: str | None = None,
) -> OpenAIRequestPlan:
    return OpenAIRequestPlan(
        model=model,
        input=[{"role": "user", "content": objective}],
        tools=tools,
        previous_response_id=previous_response_id,
        conversation=conversation,
        store=False,
    )


def build_compaction_request(model: str, items: list[dict], instructions: str | None = None) -> dict:
    payload: dict = {
        "model": model,
        "input": items,
    }
    if instructions:
        payload["instructions"] = instructions
    return payload

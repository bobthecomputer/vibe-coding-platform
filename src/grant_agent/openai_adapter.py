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
    instructions: str | None = None
    tool_choice: str | None = None
    store: bool = False

    def as_dict(self) -> dict:
        payload = asdict(self)
        if self.previous_response_id is None:
            payload.pop("previous_response_id")
        if self.conversation is None:
            payload.pop("conversation")
        if self.instructions is None:
            payload.pop("instructions")
        if self.tool_choice is None:
            payload.pop("tool_choice")
        return payload


@dataclass
class CodeExecutionConfig:
    enabled: bool = False
    memory_limit: str = "4g"
    container_id: str | None = None
    file_ids: list[str] | None = None
    required: bool = False

    def tool_payload(self) -> dict:
        if self.container_id:
            return {
                "type": "code_interpreter",
                "container": self.container_id,
            }
        container: dict[str, object] = {
            "type": "auto",
            "memory_limit": self.memory_limit or "4g",
        }
        if self.file_ids:
            container["file_ids"] = list(self.file_ids)
        return {
            "type": "code_interpreter",
            "container": container,
        }


def tools_from_skills(
    skills: list[Skill],
    *,
    code_execution: CodeExecutionConfig | None = None,
) -> list[dict]:
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
    if code_execution and code_execution.enabled:
        tools.append(code_execution.tool_payload())
    return tools


def build_responses_request(
    objective: str,
    model: str,
    tools: list[dict],
    previous_response_id: str | None = None,
    conversation: str | None = None,
    instructions: str | None = None,
    tool_choice: str | None = None,
) -> OpenAIRequestPlan:
    return OpenAIRequestPlan(
        model=model,
        input=[{"role": "user", "content": objective}],
        tools=tools,
        previous_response_id=previous_response_id,
        conversation=conversation,
        instructions=instructions,
        tool_choice=tool_choice,
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

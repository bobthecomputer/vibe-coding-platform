from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.openai_adapter import CodeExecutionConfig, build_responses_request, tools_from_skills
from grant_agent.skills import SkillRegistry


class OpenAIAdapterTests(unittest.TestCase):
    def test_build_request_contains_tools(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = SkillRegistry(root / "config" / "skills.json")
        skills = registry.retrieve("verification and tests", top_k=2)
        tools = tools_from_skills(skills)
        request = build_responses_request("Do the work", model="gpt-5", tools=tools)
        payload = request.as_dict()

        self.assertEqual(payload["model"], "gpt-5")
        self.assertGreaterEqual(len(payload["tools"]), 1)

    def test_build_request_can_include_code_execution_tool(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        registry = SkillRegistry(root / "config" / "skills.json")
        skills = registry.retrieve("verification and tests", top_k=1)
        tools = tools_from_skills(
            skills,
            code_execution=CodeExecutionConfig(
                enabled=True,
                memory_limit="4g",
                required=True,
            ),
        )
        request = build_responses_request(
            "Do the work",
            model="gpt-5",
            tools=tools,
            tool_choice="required",
        )
        payload = request.as_dict()

        code_tool = next(item for item in payload["tools"] if item["type"] == "code_interpreter")
        self.assertEqual(code_tool["container"]["type"], "auto")
        self.assertEqual(code_tool["container"]["memory_limit"], "4g")
        self.assertEqual(payload["tool_choice"], "required")


if __name__ == "__main__":
    unittest.main()

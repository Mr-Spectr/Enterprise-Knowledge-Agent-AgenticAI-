import asyncio
import unittest

from agentic_workflow import run_agentic_workflow
from supervisor_agent import verify_academic_evidence


async def _classifier(_: str):
    return {"query_type": "organizational_query", "intent": "course_enrollment", "entity": "general"}


async def _llm(_: str, __: str, model: str) -> str:
    if model == "planner":
        return '{"route":"academic_data","reason":"academic records requested"}'
    return '{"focus":"scope","next_action":"use approved tool","risk":"none"}'


class AgenticWorkflowTest(unittest.TestCase):
    def test_academic_flow_has_supervisor_and_llm_thinking(self):
        result = asyncio.run(run_agentic_workflow(
            user_id="1NT23IS015",
            query="Show my enrolled courses",
            classify_query=_classifier,
            ask_groq=_llm,
        ))
        agents = [step["agent"] for step in result.trace]
        thoughts = [step for step in result.trace if step["action"] == "llm_reasoning"]
        self.assertTrue(result.answer)
        self.assertIn("supervisor-agent", agents)
        self.assertIn("evidence-verifier-agent", agents)
        self.assertGreaterEqual(len(thoughts), 8)

    def test_verifier_rejects_another_students_record(self):
        result = verify_academic_evidence(
            {"summary": {"attendance_percent": 90}, "records": [{"usn": "1NT23IS999"}]},
            requester_id="1NT23IS015",
            role="student",
        )
        self.assertFalse(result.accepted)


if __name__ == "__main__":
    unittest.main()

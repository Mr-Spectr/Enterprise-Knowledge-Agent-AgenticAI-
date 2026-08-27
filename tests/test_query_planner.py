import asyncio
import unittest

from query_planner import plan_query


async def _unsafe_planner(*_):
    return '{"route":"general","reason":"incorrect downgrade"}'


class QueryPlannerGuardrailTest(unittest.TestCase):
    def test_institutional_request_cannot_be_downgraded_to_general(self):
        plan = asyncio.run(plan_query("What is my attendance?", "student", _unsafe_planner))
        self.assertEqual(plan["route"], "academic_data")
        self.assertEqual(plan["source"], "guardrail")


if __name__ == "__main__":
    unittest.main()

import asyncio
import unittest

from classifier import classify_query
from intent_agent import run_intent_agent


class IntentRoutingTest(unittest.TestCase):
    def test_conceptual_question_does_not_become_student_profile(self):
        result, _ = asyncio.run(
            run_intent_agent("Explain neural networks", classify_query, user_id="1NT23IS015")
        )
        self.assertEqual(result["query_type"], "general_query")
        self.assertEqual(result["intent"], "general")


if __name__ == "__main__":
    unittest.main()

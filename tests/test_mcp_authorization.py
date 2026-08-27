import unittest

from knowledge_base import bootstrap_packaged_knowledge
from mcp_csv_server import call_tool


class McpAuthorizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bootstrap_packaged_knowledge()

    def test_tool_derives_identity_from_requester(self):
        result = call_tool("search_project_knowledge", {"query": "RAG MCP"}, "1NT23IS015")
        self.assertGreater(result["result_count"], 0)

    def test_unknown_user_is_denied(self):
        with self.assertRaises(PermissionError):
            call_tool("search_project_knowledge", {"query": "RAG MCP"}, "not-a-user")


if __name__ == "__main__":
    unittest.main()

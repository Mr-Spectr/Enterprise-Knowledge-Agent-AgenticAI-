"""
mcp_csv_server.py

MCP-style tool layer for the CSV student database.
The app can call these named tools internally, and FastAPI exposes them via
/mcp/tools and /mcp/call for inspection/testing.
"""

from __future__ import annotations

from typing import Any, Dict

from data_retriever import get_user_context, retrieve_data
from knowledge_base import search_knowledge
from rbac import resolve_identity


TOOLS = [
    {
        "name": "get_user_context",
        "description": "Load student/faculty context from students_500.csv.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "role": {"type": "string"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "retrieve_data",
        "description": "Retrieve CSV data for a classified academic intent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "intent": {"type": "string"},
                "entity": {"type": "string"},
                "role": {"type": "string"},
                "user_id": {"type": "string"},
            },
            "required": ["intent", "user_id"],
        },
    },
    {
        "name": "search_project_knowledge",
        "description": "Search approved documents visible to the caller and return cited excerpts.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]},
    },
]


def list_tools() -> list[Dict[str, Any]]:
    return TOOLS


def call_tool(name: str, arguments: Dict[str, Any], requester_user_id: str) -> Dict[str, Any]:
    """Resolve identity server-side so client-provided roles cannot escalate access."""
    identity = resolve_identity(requester_user_id)
    if identity.role == "unknown":
        raise PermissionError("Unknown users cannot access organizational tools.")

    if name == "get_user_context":
        return get_user_context(
            user_id=identity.user_id,
            role=identity.role,
        )

    if name == "retrieve_data":
        return retrieve_data(
            intent=arguments.get("intent", "general"),
            entity=arguments.get("entity", "general"),
            role=identity.role,
            user_id=identity.user_id,
            assignments_path=arguments.get("assignments_path", ""),
        )

    if name == "search_project_knowledge":
        return search_knowledge(arguments.get("query", ""), identity.role, arguments.get("limit", 5))

    raise ValueError(f"Unknown MCP tool: {name}")

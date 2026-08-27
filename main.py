"""
main.py — Moodle AI Assistant Backend (CSV Edition)
===================================================
Uses students_500.csv as the only student database.
Conversation memory and multi-format export are preserved.
"""

import asyncio
import json
import logging
import os
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from groq import Groq
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from agentic_workflow import run_agentic_workflow
from classifier import classify_query
from csv_db import student_count
from data_retriever import assign_mentor, get_user_context, retrieve_data
from mcp_csv_server import call_tool, list_tools
from knowledge_base import bootstrap_packaged_knowledge, search_knowledge
from rbac import resolve_identity
from response_formatter import (
    create_excel,
    create_pdf,
    create_text_file,
    create_word,
    format_text_response,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("moodle-ai-assistant")

BASE_DIR = Path(__file__).resolve().parent
MENTOR_ASSIGNMENTS_PATH = BASE_DIR / "data" / "mentor_assignments.json"
STATIC_DIR = BASE_DIR / "static"


# ── JSON serializer that handles Decimal ─────────────────────────────────────

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def _json_dumps(obj, **kwargs):
    """json.dumps that handles Decimal values if any exporter returns them."""
    return json.dumps(obj, cls=DecimalEncoder, **kwargs)


# ── In-memory conversation store ─────────────────────────────────────────────
MAX_HISTORY = 6
_chat_history: dict[str, list[dict]] = defaultdict(list)


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Moodle AI Assistant", version="3.0.0-db")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
async def index_packaged_knowledge() -> None:
    """Populate the local RAG store from documents shipped with the service."""
    indexed = bootstrap_packaged_knowledge()
    logger.info("Indexed %s packaged knowledge documents", len(indexed))


# ── Request models ────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    format: Literal["text", "txt", "pdf", "excel", "word"] = "text"

class MentorAssignmentRequest(BaseModel):
    actor_user_id: str = Field(..., min_length=1)
    student_id: str = Field(..., min_length=1)
    mentor_name: str = Field(..., min_length=1)
    mentor_email: str = ""
    mentor_phone: str = ""

class ClearHistoryRequest(BaseModel):
    user_id: str = Field(..., min_length=1)

class LoginRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)

class McpCallRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    arguments: dict = Field(default_factory=dict)

class KnowledgeSearchRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=2)
    limit: int = Field(default=5, ge=1, le=10)


# ── Groq helpers ──────────────────────────────────────────────────────────────

def _get_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError("GROQ_API_KEY is missing or still the placeholder value in .env")
    return Groq(api_key=api_key)


def _chat_with_history(
    system_prompt: str,
    history: list[dict],
    new_user_message: str,
    model: str,
) -> str:
    client = _get_client()
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": new_user_message})

    completion = client.chat.completions.create(
        model=model,
        temperature=0.3,
        messages=messages,
    )
    return (completion.choices[0].message.content or "").strip()


async def ask_groq_with_history(
    system_prompt: str,
    history: list[dict],
    new_user_message: str,
    model: str,
) -> str:
    return await asyncio.to_thread(
        _chat_with_history, system_prompt, history, new_user_message, model
    )


# ── Data payload builder ─────────────────────────────────────────────────────

_MAX_DATA_CHARS = 8_000

def _build_retrieval_payload(retrieved: dict) -> dict:
    """
    Build a token-safe payload for the LLM.
    The CSV data_retriever returns summary dicts directly, so we pass the
    summary through and trim records if present.
    """
    records = retrieved.get("records", [])
    summary = retrieved.get("summary", {})

    # Serialize summary safely (handles Decimals)
    summary_str = _json_dumps(summary)

    # Fit records within budget
    included: list[dict] = []
    char_budget = _MAX_DATA_CHARS - len(summary_str)
    for rec in records:
        serialised = _json_dumps(rec)
        if char_budget - len(serialised) < 0:
            break
        included.append(rec)
        char_budget -= len(serialised)

    total = len(records)
    truncated = len(included) < total

    return {
        "intent": retrieved.get("intent"),
        "entity": retrieved.get("entity"),
        "summary": summary,
        "record_count": total,
        "records_shown": len(included),
        "records": included,
        "truncated": truncated,
        "truncation_note": (
            f"Only {len(included)} of {total} records shown. "
            "Use the summary for accurate totals."
        ) if truncated else None,
    }


def _cleanup_temp_file(path: Path) -> None:
    path.unlink(missing_ok=True)


def _build_download_response(file_path: Path, media_type: str, filename: str) -> FileResponse:
    return FileResponse(
        str(file_path),
        media_type=media_type,
        filename=filename,
        background=BackgroundTask(_cleanup_temp_file, file_path),
    )


# ── System prompts ────────────────────────────────────────────────────────────

def _build_system_prompt(role: str) -> str:
    base = (
        "You are Moodle AI, the academic assistant for NMIT (Nitte Meenakshi Institute of Technology). "
        "You have access to real student data from students_500.csv. "
        "Always answer using the data provided in the user message — never say 'navigate to Moodle'. "
        "Keep responses clear, specific, and professional. "
        "You remember the full conversation history and can refer back to earlier messages.\n\n"
    )

    if role == "student":
        return base + (
            "The user is a STUDENT. Rules:\n"
            "- You MUST answer questions about their own data — grades, attendance, "
            "enrolled courses, profile. This is always allowed.\n"
            "- The data payload contains this student's own records from students_500.csv.\n"
            "- If asked about their grades, attendance, or profile, present the data clearly.\n"
            "- Only refuse if they explicitly ask about a DIFFERENT student.\n"
            "- Be friendly and personal — use their name.\n"
        )

    if role == "faculty":
        return base + (
            "The user is a FACULTY MEMBER. Rules:\n"
            "- Show data for courses they teach and their enrolled students.\n"
            "- For aggregate queries: use the summary for stats.\n"
            "- For student lists: format as a clean numbered list with relevant details.\n"
            "- Never show data from courses the faculty does not teach.\n"
        )

    if role == "admin":
        return base + (
            "The user is an ADMINISTRATOR. Rules:\n"
            "- Provide full campus-wide data, all courses, all students.\n"
            "- Format large lists cleanly with counts and summaries.\n"
            "- Include actionable details for administrative decisions.\n"
        )

    return base + "Answer general academic questions helpfully."


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "version": "4.0.0-csv",
        "database": "students_500.csv",
        "students": student_count(),
        "knowledge_base": "ready",
    }


@app.post("/login")
async def login(payload: LoginRequest):
    identity = resolve_identity(payload.user_id)
    if identity.role == "unknown":
        raise HTTPException(status_code=401, detail="Invalid user ID")
    context = get_user_context(
        user_id=payload.user_id,
        role=identity.role,
        assignments_path=str(MENTOR_ASSIGNMENTS_PATH),
    )
    return JSONResponse(json.loads(_json_dumps({
        "message": "Login successful",
        "role": identity.role,
        "user_id": identity.user_id or payload.user_id,
        "user_context": context,
    })))


@app.get("/mcp/tools")
async def mcp_tools():
    return JSONResponse({"tools": list_tools()})


@app.post("/mcp/call")
async def mcp_call(payload: McpCallRequest):
    try:
        result = call_tool(payload.name, payload.arguments, payload.user_id)
        return JSONResponse(json.loads(_json_dumps({"result": result})))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@app.post("/knowledge/search")
async def knowledge_search(payload: KnowledgeSearchRequest):
    """Search documents with a server-resolved identity, not a client-supplied role."""
    identity = resolve_identity(payload.user_id)
    if identity.role == "unknown":
        raise HTTPException(status_code=401, detail="Invalid user ID")
    try:
        return JSONResponse(search_knowledge(payload.query, identity.role, payload.limit))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/user-context/{user_id}")
async def user_context(user_id: str):
    try:
        identity = resolve_identity(user_id)
        role = identity.role
    except Exception:
        role = "unknown"
    context = get_user_context(
        user_id=user_id,
        role=role,
        assignments_path=str(MENTOR_ASSIGNMENTS_PATH),
    )
    return JSONResponse(json.loads(_json_dumps(context)))


@app.get("/")
async def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/chat/clear")
async def clear_history(payload: ClearHistoryRequest):
    _chat_history.pop(payload.user_id, None)
    return JSONResponse({"message": f"History cleared for {payload.user_id}"})


@app.post("/mentor/assign")
async def mentor_assignment(payload: MentorAssignmentRequest):
    try:
        identity = resolve_identity(payload.actor_user_id)
        result = assign_mentor(
            assignments_path=str(MENTOR_ASSIGNMENTS_PATH),
            actor_role=identity.role,
            actor_user_id=payload.actor_user_id,
            student_id=payload.student_id,
            mentor_name=payload.mentor_name,
            mentor_email=payload.mentor_email,
            mentor_phone=payload.mentor_phone,
        )
        return JSONResponse(json.loads(_json_dumps({"role": identity.role, **result})))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/ask")
async def ask(payload: AskRequest):
    try:
        identity = resolve_identity(payload.user_id)
        if identity.role == "unknown":
            raise HTTPException(status_code=401, detail="Invalid user ID")
        document_terms = {"policy", "policies", "document", "documents", "handbook", "notice", "notices", "syllabus", "rag", "mcp"}
        if document_terms.intersection(set(payload.query.lower().split())):
            evidence = search_knowledge(payload.query, identity.role)
            if evidence["result_count"]:
                citations = "\n".join(
                    f"- {item['source']}{f', page {item['page']}' if item['page'] else ''}: {item['excerpt']}"
                    for item in evidence["results"]
                )
                return JSONResponse({
                    "answer": "Here is the approved-source information I found:\n" + citations,
                    "role": identity.role,
                    "classification": {"query_type": "knowledge_query", "intent": "search_project_knowledge"},
                    "sources": evidence["results"],
                    "trace": [{"agent": "knowledge-agent", "action": "search_project_knowledge", "status": "completed", "detail": "Returned role-filtered, source-attributed document excerpts."}],
                })

        # ── 1. Retrieve conversation history ──────────────────────────────
        history = _chat_history[payload.user_id]

        async def ask_groq(system_prompt: str, user_message: str, model: str) -> str:
            return await ask_groq_with_history(
                system_prompt=system_prompt,
                history=history,
                new_user_message=user_message,
                model=model,
            )

        # ── 2. Agentic workflow: role → context → intent → data → answer ──
        result = await run_agentic_workflow(
            user_id=payload.user_id,
            query=payload.query,
            assignments_path=str(MENTOR_ASSIGNMENTS_PATH),
            classify_query=classify_query,
            ask_groq=ask_groq,
        )

        answer = result.answer
        role = result.role
        classification = result.classification
        logger.info("User=%s Role=%s Classification=%s",
                    payload.user_id, role, _json_dumps(classification))

        # ── 3. Append to history (trimmed) ────────────────────────────────
        history_answer = answer[:400] + "…" if len(answer) > 400 else answer
        history.append({"role": "user", "content": payload.query})
        history.append({"role": "assistant", "content": history_answer})
        if len(history) > MAX_HISTORY * 2:
            _chat_history[payload.user_id] = history[-(MAX_HISTORY * 2):]

        # ── 4. Return response ────────────────────────────────────────────
        if payload.format == "text":
            response_data = {
                "answer": format_text_response(answer),
                "role": role,
                "classification": classification,
                "user_context": result.user_context,
                "trace": result.trace,
            }
            return JSONResponse(json.loads(_json_dumps(response_data)))

        if payload.format == "txt":
            return _build_download_response(
                create_text_file(answer), "text/plain; charset=utf-8",
                "moodle_ai_response.txt",
            )
        if payload.format == "pdf":
            return _build_download_response(
                create_pdf(answer), "application/pdf",
                "moodle_ai_response.pdf",
            )
        if payload.format == "excel":
            return _build_download_response(
                create_excel(answer),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "moodle_ai_response.xlsx",
            )
        if payload.format == "word":
            return _build_download_response(
                create_word(answer),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "moodle_ai_response.docx",
            )

        raise HTTPException(status_code=400, detail="Invalid format")

    except HTTPException:
        raise
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Unhandled error in /ask")
        raise HTTPException(status_code=500, detail=f"Server error: {exc}")

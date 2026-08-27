# RAG and MCP design

Retrieval-augmented generation (RAG) grounds document answers in approved source material. The ingestion flow extracts text from an approved document, chunks it, attaches access metadata, and stores it in the local knowledge index. At query time, role filtering happens before ranking; only then are matching excerpts returned with source metadata.

The Model Context Protocol (MCP) exposes narrow, typed capabilities such as academic data retrieval and project knowledge search. An MCP tool must receive identity-derived authorization from the application, not a role claimed by an untrusted client. The model is responsible for reasoning and answer composition; it is not the authorization boundary and must not receive unrestricted database or file-system access.

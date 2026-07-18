# Project documentation

This directory is the long-term home for project material that supports the Enterprise Knowledge Agent. Keeping reports under `docs/` prevents the repository root from becoming a mixed collection of source code and academic files.

## Structure

```text
docs/
├── README.md
├── assets/
│   └── system-architecture.png
└── academic/
    ├── phase-1-synopsis.pdf
    └── research-paper.pdf
```

## Academic reports

| File | Purpose |
| --- | --- |
| [`academic/phase-1-synopsis.pdf`](academic/phase-1-synopsis.pdf) | Original Phase 1 synopsis with objectives, requirements, methodology, and system architecture. |
| [`academic/research-paper.pdf`](academic/research-paper.pdf) | Research paper covering the OrganicMind implementation, evaluation, and future work. |
| [`assets/system-architecture.png`](assets/system-architecture.png) | Project-owned Phase 1 architecture diagram used in the root README. |

## Naming convention

Use lowercase, hyphen-separated filenames. Add future material to a topic-specific folder (for example, `docs/design/`, `docs/api/`, or `docs/deployment/`) and link it from the root README when it is useful to project visitors. Check [NOTICE.md](../NOTICE.md) before reusing project-owned documents or design assets.

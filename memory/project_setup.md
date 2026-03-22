---
name: project_setup
description: Graduate student personal assistant — scope, workflows A–I, folder structure, Notion sync, Google Calendar MCP, skills architecture
type: project
---

User is a graduate student. This workspace is a full personal assistant covering 9 workflow types (A–I), not just a note generator.

**Courses:** 嵌入式即時系統, 演算法, 作業系統, 記憶體與儲存系統 — all dual-purpose: exam prep + IC design house career prep.

**Research direction:** LLM (Master's). Career target: IC design house.

**Workflows (each is a separate `.claude/skills/` file):**
- A `/note-lecture` — course PPT/PDF + optional recording → structured Markdown note
- B `/note-video` — YouTube/Bilibili → download audio → transcribe → note
- C `/homework` — assignment/project: gap-fill reference notes → solution
- D `/exam-prep` — generate Q&A weighted toward weak areas + 重點整理
- E `/progress-report` — advisor meeting recording → transcript → summary → formal report
- F `/paper-reading` — PDF → deep notes + PPT outline for advisor
- G `/note-article` — technical article (URL or PDF) → note
- H `/deep-research` — Gemini Deep Research report → propose/apply CLAUDE.md updates
- I `/suggest` — "what should I do now?" → check calendar + skill gaps → recommend

**Skills architecture:** CLAUDE.md is minimal (always-loaded constants). Each workflow lives in `.claude/skills/<name>.md`, loaded on demand via `/skill-name`.

**Personalization:**
- `memory/skills_inventory.md` — living skills matrix (熟悉/薄弱/學習中/建議補充); read before every task, update after every task.
- `memory/user_profile.md` — background, research direction, career target.

**Notion sync (2-layer):**
- Layer 1: `.md` files in workspace = full content mirror
- Layer 2: `NOTION_INDEX.md` = queryable master index (updated by `scripts/push_to_notion.py`)
- Push command: `conda run -n notes-ai python scripts/push_to_notion.py --file <path> --type <lecture|assignment|paper|progress|resource>`
- Requires `NOTION_API_TOKEN` + database IDs in `.env`

**Google Calendar + Gmail (MCP):**
- Package: `@dguido/google-workspace-mcp` v3.4.4 at `C:\Users\Administrator\AppData\Roaming\npm\node_modules\@dguido\google-workspace-mcp\dist\index.js`
- Config: `C:\Users\Administrator\.claude\mcp.json` (mcpServers: google-workspace)
- OAuth credentials: `C:\Users\Administrator\.google\gcp-oauth.keys.json` (user must create GCP project + enable Gmail + Calendar APIs)
- Usage: at conversation start, check Calendar (next 7 days) + Gmail (unread from advisor). When deadlines found, call `calendar.create_event()`.

**Tools:**
- conda env `notes-ai` (Python 3.11) at `C:\ProgramData\miniconda3`
- GPU: RTX 5070 Ti (16GB VRAM, CUDA 12.9) — `device="cuda"` for Whisper
- faster-whisper (medium model) for transcription
- PowerPoint COM (pywin32) for PPTX → PNG
- pymupdf (fitz) for PDF → PNG
- notion-client (Python) for Notion API push

**Folder structure:**
```
課程/<course>/{教材,錄音,投影片,逐字稿,筆記,作業/<hw>,專題/<proj>,考試準備/<exam>}/
進度報告/<YYYY-MM-DD_meeting>/{錄音,逐字稿,摘要,報告}/
論文/<paper_key>/{PDF,筆記,簡報大綱}/
網路資源/<LLM_AI|嵌入式|演算法|其他>/<topic>/{逐字稿,原文,筆記}/
深度研究/<topic>/
scripts/, memory/, .claude/skills/
CLAUDE.md, NOTES_STATUS.md, PROGRESS_STATUS.md, PAPERS_STATUS.md, NOTION_INDEX.md, .env
```

**Why:** Expanded from narrow note generator to full personal assistant after planning session 2026-03-21.
**How to apply:** Always read skills_inventory.md before tasks. Use skills architecture — don't inline workflow steps in chat. Update status files after every task.

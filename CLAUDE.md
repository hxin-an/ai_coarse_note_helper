# Graduate Student Personal Assistant

This workspace is a personal assistant for a graduate student. It stores course notes, assignments, research, and progress reports — all in Markdown, synced to Notion.

---

## At Conversation Start

1. **Read** `memory/user_profile.md` and `memory/skills_inventory.md` — load context before any task.
2. **Check Google Calendar** (MCP: `google-workspace`) for events/deadlines in the next 7 days. If found, proactively mention them.
3. **Check Gmail** (MCP: `google-workspace`) for unread emails from advisor. If any contain deadlines or tasks, add to Google Calendar and alert user.

---

## Active Courses (This Semester)

- 嵌入式即時系統 — IC career prep
- 演算法 — IC career prep
- 作業系統 — IC career prep
- 記憶體與儲存系統 — IC career prep

---

## Available Skills

Invoke with `/skill-name` when the task matches:

| Skill | When to Use |
|-------|-------------|
| `/note-lecture` | New course material (PPT/PDF) + optional recording |
| `/note-resource` | YouTube / Bilibili video, web article, or saved PDF |
| `/homework` | New assignment or project |
| `/exam-prep` | Upcoming exam — generate Q&A and summaries |
| `/progress-report` | Advisor meeting recording → summary → report |
| `/paper-reading` | Academic paper → reading notes + PPT outline |
| `/deep-research` | Gemini Deep Research report brought back → update CLAUDE.md |
| `/suggest` | "What should I do now?" — recommend based on deadlines + skill gaps |

---

## Key Files

| File | Purpose |
|------|---------|
| `memory/user_profile.md` | Background, research direction, career target |
| `memory/skills_inventory.md` | Living skills matrix — always read before tasks |
| `NOTES_STATUS.md` | Lecture notes + assignments + online resources progress |
| `PROGRESS_STATUS.md` | Advisor meeting → report progress |
| `PAPERS_STATUS.md` | Paper reading progress |
| `NOTION_INDEX.md` | All pages pushed to Notion (local index) |
| `scripts/process_notes.py` | PPT/PDF → PNG slides; audio → transcript (Whisper) |
| `scripts/push_to_notion.py` | Push .md to Notion + update NOTION_INDEX.md |

---

## Folder Structure

```
課程/<course>/
  教材/          ← .pptx / .pdf
  錄音/          ← lecture audio
  投影片/        ← exported PNGs
  逐字稿/        ← Whisper transcripts
  筆記/          ← lecture notes .md
  作業/<hw>/     ← 題目/ 參考筆記/ 作答/
  專題/<proj>/   ← 題目/ 參考筆記/ 草稿/
  考試準備/<exam>/ ← 練習題/ 重點整理/
進度報告/<YYYY-MM-DD_meeting>/
  錄音/ 逐字稿/ 摘要/ 報告/
論文/<paper_key>/
  PDF/ 筆記/ 簡報大綱/
網路資源/<LLM_AI|嵌入式|演算法|其他>/
  <topic>/ ← 逐字稿/(影片用)/ 原文/(文章PDF)/ 筆記/
深度研究/<topic>/
  Gemini_報告_<date>.md
  更新摘要_<date>.md
```

---

## Note Format

Every note must follow this structure:

**Header**
```
# [課程/主題] — [教材名稱或影片標題]
> 來源：`<filename or URL>` | 產生日期：YYYY-MM-DD
```

**Body** (in order):
1. **前言** — 2–4 sentences on what this covers and why it matters (Traditional Chinese)
2. **大綱** — nested bullet list mirroring H2/H3 structure
3. **Sections** — `##` major topics, `###` sub-topics
   - **Bold** key terms on first use; add English/Chinese gloss
   - Explain the *why*, not just the what
   - LaTeX for math (`$...$` inline, `$$...$$` block)
   - Tables for comparisons; `→` for logical conclusions

**Language**: Traditional Chinese + English mix is correct and expected.

**Completeness Check** (required before saving every note):
- [ ] 前言 is present and meaningful
- [ ] 大綱 matches actual H2/H3 sections
- [ ] Every major topic is covered
- [ ] No section is empty or heading-only
- [ ] Key terms bolded on first use
- [ ] All math uses LaTeX

---

## Rules

- **Python**: always use `conda run -n notes-ai python`. Never pip-install into local Python.
- **Conda**: `C:\ProgramData\miniconda3\Scripts\conda.exe`
- **GPU**: RTX 5070 Ti (16GB VRAM, CUDA 12.9) — use `device="cuda"` for Whisper
- **Slide images are source of truth** for course notes — read PNGs directly, do not rely on text extraction
- After any task, **update** `memory/skills_inventory.md` with new gaps or learnings found

---
name: project_setup
description: Course notes assistant setup — courses, tools, folder structure, workflow, and note format preferences
type: project
---

User is a student processing lecture recordings + PPT/PDF into Notion-ready Markdown notes.

**Courses:** 嵌入式即時系統, 演算法, 作業系統, 記憶體與儲存系統

**Folder structure per course:**
```
c:\assistant\<course>\
    教材\     ← .pptx / .pdf (not synced to git, copyright)
    錄音\     ← .mp3 / .mp4 (not synced, large files)
    投影片\   ← per-slide PNG exports (one subfolder per stem)
    逐字稿\   ← Whisper transcript .txt (kept for reference)
    筆記\     ← output .md files (synced to git)
```

**Workflow:**
1. Run `scripts/process_notes.py` → exports slides to `投影片/<stem>/` PNGs + transcript to `逐字稿/`
2. Claude reads slide images directly (vision) + transcript → writes note
3. No text extraction from PPTX anymore — images are the source of truth

**Tools:**
- conda env `notes-ai` (Python 3.11), GTX 1650 4GB VRAM
- PowerPoint COM (pywin32) for PPTX → PNG export
- pymupdf (fitz) for PDF → PNG
- faster-whisper medium on CUDA for transcription
- cjk-token-reducer at `C:\Users\hxin\.cargo\bin\cjk-token-reducer.exe`, hooked as UserPromptSubmit
- conda at `C:\Users\hxin\anaconda3\Scripts\conda.exe`
- Git repo: https://github.com/hxin-an/ai_coarse_note_helper.git

**Note format preferences:**
- Topic-based sections (## major, ### sub-topics), NOT slide-by-slide
- Bold key terms on first use with English/Chinese gloss
- Nested bullets with "why" reasoning
- LaTeX for all math, Markdown tables for comparisons, `→` for logic flow
- Mix of Traditional Chinese + English
- Must include 前言 (intro) and 大綱 (outline) at top
- Completeness check required before saving (see CLAUDE.md)

**Progress tracking:** Check `c:\assistant\NOTES_STATUS.md` before starting any note.

**Why:** User manages notes in Notion, wants clean structured Markdown to paste directly.
**How to apply:** Always check NOTES_STATUS.md first. Generate topic-based notes from slide images. Run completeness checklist before delivering.

# Course Notes Assistant

This workspace converts course materials (PPT/PDF) and lecture recordings into structured Markdown notes for Notion.

## Folder Structure

```
c:\assistant\
├── <course_name>\
│   ├── 教材\        ← .pptx or .pdf (one note per file)
│   ├── 錄音\        ← .mp3 / .mp4 (optional; matched by stem name)
│   ├── 投影片\      ← per-slide PNG images (one subfolder per material stem)
│   ├── 逐字稿\      ← .txt transcript output (kept for reference/comparison)
│   └── 筆記\        ← output .md files
├── scripts\
│   └── process_notes.py
└── CLAUDE.md
```

## Courses

- 嵌入式即時系統
- 演算法
- 作業系統
- 記憶體與儲存系統

## Notes Progress Tracking

Before processing any material, check `c:\assistant\NOTES_STATUS.md` to see what has already been done.
After completing a note, update `NOTES_STATUS.md` with the file name, status, date, and any relevant notes.

## Workflow

When the user says there is new material or a new recording:

### Step 1 — Convert to images + transcript
```bash
# All materials in a course
conda run -n notes-ai python c:/assistant/scripts/process_notes.py "c:/assistant/<course_name>"

# Single material file
conda run -n notes-ai python c:/assistant/scripts/process_notes.py "c:/assistant/<course_name>" "<filename.pptx>"
```
This exports slides to `投影片/<stem>/slide_001.png ...` and (if audio exists) saves transcript to `逐字稿/<stem>.txt`.

### Step 2 — Generate notes
Read each slide image in `投影片/<stem>/` (and the transcript if available), then write the structured note to `筆記/<stem>.md`. Do NOT rely on text extraction — use the images as the source of truth.

## Rules

- Always use the `notes-ai` conda environment. Never pip install into local Python.
- Conda executable: `C:\Users\hxin\anaconda3\Scripts\conda.exe`
- Audio transcription uses Whisper `medium` model on CUDA (GTX 1650, 4GB VRAM).
- First run will download the Whisper model (~769MB) automatically.
- PPT and audio are matched by stem name (e.g. `lecture1.pptx` ↔ `lecture1.mp3`).
- Notes are output in Markdown format ready to paste into Notion.
- If no matching audio exists, notes are generated from slide images only.
- One note file per material file (one .md per .pptx / .pdf).
- Slide images are the source of truth — read them directly, do NOT rely on text extraction.
- After transcription, the transcript is saved to `逐字稿/<stem>.txt`. Do NOT delete it.

## Note Format

Each note must follow this structure:

### 1. Header
```
# [課程名稱] — [教材檔名（不含副檔名）]
> 來源：`<filename>` | 產生日期：YYYY-MM-DD
```

### 2. 前言 (Introduction)
- 2–4 sentences summarising what this lecture covers and why it matters.
- Written in Traditional Chinese.

### 3. 大綱 (Outline)
- Nested bullet list mirroring the H2/H3 structure of the note body.

### 4. Body Sections
- Use `##` for major topics, `###` for sub-topics.
- **Bold key terms** on first use; include English/Chinese translation in parentheses.
- Use nested bullet points for details and explanations.
- Explain the **why**, not just the what — include reasoning, intuition, and consequences.
- Use LaTeX (`$...$` inline, `$$...$$` block) for all math formulas.
- Use Markdown tables for comparisons.
- Use `→` arrows for conclusions or logical flow.

### 5. Language
- Mix of Traditional Chinese and English is expected and correct.
- Technical terms may be kept in English with a Chinese gloss, e.g. `Preemption（搶佔）`.

## Completeness Check (Required Before Saving)

Before saving or delivering any note, verify every item:

- [ ] 前言 is present and meaningful (not a placeholder).
- [ ] 大綱 is present and matches the actual H2/H3 sections.
- [ ] Every major topic from the PPT/transcript is represented in the body.
- [ ] No section is left empty or contains only a heading.
- [ ] Key terms are bolded on first use.
- [ ] All math uses LaTeX syntax.
- [ ] The note reads coherently from top to bottom.

Fix any failing items before saving.

## Environment

- Python: 3.11 (conda env `notes-ai`)
- GPU: NVIDIA GTX 1650 (4GB VRAM)
- RAM: 24GB
- Packages: faster-whisper, python-pptx, pdfplumber, ffmpeg

## CJK Token Optimization

- `cjk-token-reducer` is installed at `C:\Users\hxin\.cargo\bin\cjk-token-reducer.exe`
- Configured as a Claude Code hook to translate Chinese input → English before sending
- Reduces token usage by 35-50% for CJK text

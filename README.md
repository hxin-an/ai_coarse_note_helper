# AI Course Note Helper

A personal workflow for converting university lecture materials (PPTX/PDF) and recordings (MP3/MP4) into structured Markdown notes ready to paste into Notion.

## How It Works

1. **Pre-process** — Run `process_notes.py` to export slides as PNG images and transcribe audio with Whisper
2. **Generate** — Claude Code reads the slide images (+ transcript if available) and writes a structured Markdown note
3. **Sync** — Notes are saved to `筆記/` and tracked in `NOTES_STATUS.md`

```
教材/*.pptx  ──┐
               ├─ process_notes.py ─┬─ 投影片/<stem>/slide_001.png ...
錄音/*.mp4   ──┘                    └─ 逐字稿/<stem>.txt
                                              │
                                        Claude reads images
                                              │
                                        筆記/<stem>.md
```

## Folder Structure

```
<course_name>/
├── 教材/       ← source PPTX / PDF (not synced, copyright)
├── 錄音/       ← lecture recordings MP3/MP4 (not synced, large files)
├── 投影片/     ← exported slide PNGs, one subfolder per file (not synced)
├── 逐字稿/     ← Whisper transcripts .txt (not synced, regenerable)
└── 筆記/       ← ✅ output Markdown notes (synced)
```

## Courses

| 課程 | Course |
|------|--------|
| 嵌入式即時系統 | Embedded Real-Time Systems |
| 演算法 | Algorithms |
| 作業系統 | Operating Systems |
| 記憶體與儲存系統 | Memory and Storage Systems |

## Setup

### Requirements

- Windows 10/11
- [Anaconda](https://www.anaconda.com/) with a `notes-ai` conda environment
- Microsoft PowerPoint (for PPTX → PNG export)
- NVIDIA GPU recommended (for Whisper transcription)

### Create the conda environment

```bash
conda create -n notes-ai python=3.11
conda activate notes-ai
conda install -c conda-forge pywin32
pip install faster-whisper pymupdf pdfplumber python-pptx
```

### Run

```bash
# Process all materials in a course
conda run -n notes-ai python scripts/process_notes.py "c:/assistant/<course_name>"

# Process a single file
conda run -n notes-ai python scripts/process_notes.py "c:/assistant/<course_name>" "lecture1.pptx"
```

Then ask Claude Code to read the generated images and produce the note.

## Note Format

Each generated note follows this structure:

- **Header** — course name, source file, date
- **前言** — 2–4 sentence introduction in Traditional Chinese
- **大綱** — nested outline matching the note body
- **Body** — `##` major topics, `###` sub-topics, bold key terms, LaTeX math, Markdown tables
- **Language** — mix of Traditional Chinese and English

## Progress Tracking

See [`NOTES_STATUS.md`](NOTES_STATUS.md) for the current processing status of all materials.

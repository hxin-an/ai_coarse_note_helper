# Graduate Student Personal Assistant

A Claude Code workspace for a graduate student — converts lectures, recordings, papers, and online resources into structured Markdown notes, synced to Notion.

## Workflows

Invoke with `/skill-name` in Claude Code:

| Skill | What it does |
|-------|-------------|
| `/note-lecture` | Course PPT/PDF + optional recording → structured Markdown note |
| `/note-video` | YouTube / Bilibili video → download → transcribe → note |
| `/note-article` | Technical article or blog (URL or PDF) → note |
| `/homework` | Assignment: gap-fill reference notes + solution |
| `/exam-prep` | Upcoming exam → Q&A (weighted toward weak areas) + 重點整理 |
| `/progress-report` | Advisor meeting recording → transcript → summary → formal report |
| `/paper-reading` | Academic paper → deep notes + PPT outline for advisor |
| `/deep-research` | Gemini Deep Research report → propose CLAUDE.md updates |
| `/suggest` | "What should I do now?" → recommend based on deadlines + skill gaps |

## Folder Structure

```
課程/<course>/
  教材/         ← .pptx / .pdf (not synced, copyright)
  錄音/         ← lecture audio (not synced, large files)
  投影片/       ← exported slide PNGs (not synced, regenerable)
  逐字稿/       ← Whisper transcripts .txt
  筆記/         ← output .md notes ✅
  作業/<hw>/    ← 題目/ 參考筆記/ 作答/
  專題/<proj>/  ← 題目/ 參考筆記/ 草稿/
  考試準備/<exam>/ ← 練習題/ 重點整理/

進度報告/<YYYY-MM-DD_meeting>/
  錄音/ 逐字稿/ 摘要/ 報告/

論文/<paper_key>/
  PDF/ 筆記/ 簡報大綱/

網路資源/<LLM_AI|嵌入式|演算法|其他>/
  影片/<topic>/ ← 逐字稿/ 筆記/
  文章/<topic>/ ← 原文/ 筆記/

深度研究/<topic>/
  Gemini_報告_<date>.md
  更新摘要_<date>.md

scripts/
  process_notes.py   ← PPT/PDF → PNGs; audio → transcript (Whisper)
  push_to_notion.py  ← push .md to Notion + update NOTION_INDEX.md

memory/
  user_profile.md       ← background, research direction, career target
  skills_inventory.md   ← living skills matrix (read before every task)

.claude/skills/         ← workflow instruction files (loaded on demand)
```

## Setup

### 1. Conda environment

```bash
conda create -n notes-ai python=3.11
conda activate notes-ai
conda install -c conda-forge pywin32
pip install faster-whisper pymupdf pdfplumber python-pptx yt-dlp httpx
```

### 2. Notion API

Copy `.env.example` to `.env` and fill in:
- `NOTION_API_TOKEN` — from https://www.notion.so/my-integrations
- `NOTION_DB_*` — database IDs for each section

### 3. Google Workspace MCP (Gmail + Google Calendar)

**Step 1 — Install the MCP server:**
```bash
npm install -g @dguido/google-workspace-mcp
```

**Step 2 — Create GCP credentials:**
1. Go to https://console.cloud.google.com
2. Create a new project (or reuse one)
3. Enable **Gmail API** and **Google Calendar API**
4. Create OAuth 2.0 credentials (Desktop App type)
5. Download `client_secret_*.json` → rename to `gcp-oauth.keys.json`
6. Move to `C:\Users\Administrator\.google\gcp-oauth.keys.json`

**Step 3 — Set your email in `~/.claude/mcp.json`:**
```json
{
  "mcpServers": {
    "google-workspace": {
      "command": "C:\\Program Files\\nodejs\\node.exe",
      "args": ["C:\\Users\\Administrator\\AppData\\Roaming\\npm\\node_modules\\@dguido\\google-workspace-mcp\\dist\\index.js"],
      "env": {
        "GOOGLE_OAUTH_CREDENTIALS": "C:\\Users\\Administrator\\.google\\gcp-oauth.keys.json",
        "GOOGLE_ACCOUNT_EMAIL": "your.email@gmail.com"
      }
    }
  }
}
```

**Step 4 — Authenticate (first time only):**
Start a new Claude Code session. At conversation start it will attempt to access Calendar/Gmail and trigger an OAuth consent flow in your browser.

### 4. Required: Microsoft PowerPoint

PowerPoint must be installed for PPTX → PNG export (used by `process_notes.py`).

## Hardware

- GPU: NVIDIA RTX 5070 Ti (16GB VRAM, CUDA 12.9) — used for Whisper transcription
- Python: 3.11 (conda env `notes-ai`)

## Progress Tracking

| File | Tracks |
|------|--------|
| [`NOTES_STATUS.md`](NOTES_STATUS.md) | Lecture notes, assignments, online resources |
| [`PROGRESS_STATUS.md`](PROGRESS_STATUS.md) | Advisor meeting → report cycles |
| [`PAPERS_STATUS.md`](PAPERS_STATUS.md) | Paper reading pipeline |
| [`NOTION_INDEX.md`](NOTION_INDEX.md) | All pages pushed to Notion |

"""
push_to_notion.py
=================
Push a local Markdown note to Notion and update NOTION_INDEX.md.

Usage:
    conda run -n notes-ai python scripts/push_to_notion.py \
        --file "課程/作業系統/筆記/OS-1.md" \
        --type lecture

    conda run -n notes-ai python scripts/push_to_notion.py \
        --file "論文/vaswani2017attention/筆記/vaswani2017attention_notes.md" \
        --type paper

Types:
    lecture     → NOTION_DB_LECTURE_NOTES
    assignment  → NOTION_DB_ASSIGNMENTS
    paper       → NOTION_DB_PAPERS
    progress    → NOTION_DB_PROGRESS
    resource    → NOTION_DB_RESOURCES

Requires .env with NOTION_API_TOKEN + NOTION_DB_* IDs in the workspace root.
"""

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
WORKSPACE_ROOT = Path(__file__).parent.parent
ENV_FILE = WORKSPACE_ROOT / ".env"
NOTION_INDEX = WORKSPACE_ROOT / "NOTION_INDEX.md"
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

DB_ENV_KEYS = {
    "lecture":    "NOTION_DB_LECTURE_NOTES",
    "assignment": "NOTION_DB_ASSIGNMENTS",
    "paper":      "NOTION_DB_PAPERS",
    "progress":   "NOTION_DB_PROGRESS",
    "resource":   "NOTION_DB_RESOURCES",
}

SECTION_HEADINGS = {
    "lecture":    "## 課程筆記",
    "assignment": "## 作業 / 專題",
    "paper":      "## 論文",
    "progress":   "## 進度報告",
    "resource":   "## 網路資源",
}

# ---------------------------------------------------------------------------
# .env loader (no dependency on python-dotenv)
# ---------------------------------------------------------------------------
def load_env(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


# ---------------------------------------------------------------------------
# Markdown → Notion blocks (lightweight converter)
# ---------------------------------------------------------------------------
def text_to_rich(text: str) -> list:
    """Convert inline markdown (bold, italic, inline code, LaTeX) to rich_text objects."""
    if not text:
        return []

    # Split on bold (**...**), italic (*...*), inline code (`...`), inline math ($...$)
    pattern = re.compile(
        r'(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\$[^$]+\$)'
    )
    parts = pattern.split(text)
    rich = []
    for part in parts:
        if not part:
            continue
        annotations = {}
        content = part
        if part.startswith("**") and part.endswith("**"):
            content = part[2:-2]
            annotations["bold"] = True
        elif part.startswith("*") and part.endswith("*"):
            content = part[1:-1]
            annotations["italic"] = True
        elif part.startswith("`") and part.endswith("`"):
            content = part[1:-1]
            annotations["code"] = True
        elif part.startswith("$") and part.endswith("$"):
            content = part[1:-1]
            annotations["code"] = True  # Notion doesn't support LaTeX inline natively
        rich.append({"type": "text", "text": {"content": content}, "annotations": annotations} if annotations
                    else {"type": "text", "text": {"content": content}})
    return rich


def md_to_blocks(md: str) -> list:
    """Convert Markdown text to a list of Notion block objects."""
    blocks = []
    lines = md.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        # Skip YAML front matter (shouldn't appear in notes but just in case)
        if i == 0 and line.strip() == "---":
            i += 1
            while i < len(lines) and lines[i].strip() != "---":
                i += 1
            i += 1
            continue

        # Headings
        m = re.match(r'^(#{1,3})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            heading_type = {1: "heading_1", 2: "heading_2", 3: "heading_3"}.get(level, "heading_3")
            blocks.append({
                "object": "block",
                "type": heading_type,
                heading_type: {"rich_text": text_to_rich(m.group(2))}
            })
            i += 1
            continue

        # Code block (```)
        if line.strip().startswith("```"):
            lang = line.strip()[3:].strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": "\n".join(code_lines)}}],
                    "language": lang if lang else "plain text"
                }
            })
            continue

        # Block math ($$...$$)
        if line.strip().startswith("$$"):
            math_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("$$"):
                math_lines.append(lines[i])
                i += 1
            i += 1
            # Notion doesn't have a native math block; use code block
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": "\n".join(math_lines)}}],
                    "language": "plain text"
                }
            })
            continue

        # Horizontal rule
        if re.match(r'^[-*_]{3,}\s*$', line):
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            i += 1
            continue

        # Blockquote
        if line.startswith(">"):
            content = re.sub(r'^>\s?', '', line)
            blocks.append({
                "object": "block",
                "type": "quote",
                "quote": {"rich_text": text_to_rich(content)}
            })
            i += 1
            continue

        # Table (collect all table lines together — push as code block since Notion API tables are complex)
        if re.match(r'^\s*\|', line):
            table_lines = []
            while i < len(lines) and re.match(r'^\s*\|', lines[i]):
                table_lines.append(lines[i])
                i += 1
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": "\n".join(table_lines)}}],
                    "language": "plain text"
                }
            })
            continue

        # Bullet list (- or *)
        m = re.match(r'^(\s*)[-*]\s+(.*)', line)
        if m:
            indent = len(m.group(1))
            content = m.group(2)
            # Nested bullets: if indent > 0, add as a child — simplified: flatten for now
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": text_to_rich(content)}
            })
            i += 1
            continue

        # Numbered list (1. 2. etc.)
        m = re.match(r'^\s*\d+\.\s+(.*)', line)
        if m:
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": text_to_rich(m.group(1))}
            })
            i += 1
            continue

        # Checkbox (- [ ] or - [x])
        m = re.match(r'^\s*-\s+\[( |x)\]\s+(.*)', line)
        if m:
            checked = m.group(1) == "x"
            blocks.append({
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": text_to_rich(m.group(2)),
                    "checked": checked
                }
            })
            i += 1
            continue

        # Empty line → paragraph break (skip)
        if not line.strip():
            i += 1
            continue

        # Default: paragraph
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": text_to_rich(line)}
        })
        i += 1

    return blocks


# ---------------------------------------------------------------------------
# Notion API helpers
# ---------------------------------------------------------------------------
def notion_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def create_notion_page(client: httpx.Client, token: str, db_id: str,
                       title: str, blocks: list) -> dict:
    """Create a new page in a Notion database with the given blocks."""
    # Notion API limit: 100 blocks per request
    CHUNK = 100
    first_chunk = blocks[:CHUNK]

    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            "Name": {
                "title": [{"type": "text", "text": {"content": title}}]
            }
        },
        "children": first_chunk
    }

    resp = client.post(f"{NOTION_API}/pages", json=payload, headers=notion_headers(token))
    resp.raise_for_status()
    page = resp.json()
    page_id = page["id"]

    # Append remaining blocks in chunks
    for start in range(CHUNK, len(blocks), CHUNK):
        chunk = blocks[start:start + CHUNK]
        append_resp = client.patch(
            f"{NOTION_API}/blocks/{page_id}/children",
            json={"children": chunk},
            headers=notion_headers(token)
        )
        append_resp.raise_for_status()

    return page


# ---------------------------------------------------------------------------
# NOTION_INDEX.md update
# ---------------------------------------------------------------------------
def update_notion_index(file_path: Path, note_type: str,
                        title: str, page_url: str, extra: dict):
    """Append a row to the correct section of NOTION_INDEX.md."""
    today = date.today().strftime("%Y-%m-%d")
    index_text = NOTION_INDEX.read_text(encoding="utf-8") if NOTION_INDEX.exists() else ""

    section = SECTION_HEADINGS.get(note_type, "## 網路資源")
    rel_path = str(file_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")

    # Build the new row based on type
    if note_type == "lecture":
        course = extra.get("course", "—")
        new_row = f"| {title} | {course} | {rel_path} | {page_url} | {today} |"
        table_header = "| 標題 | 課程 | 本地路徑 | Notion URL | 推送日期 |"
    elif note_type == "assignment":
        course = extra.get("course", "—")
        kind = extra.get("kind", "作業")
        new_row = f"| {title} | {course} | {kind} | {rel_path} | {page_url} | {today} |"
        table_header = "| 標題 | 課程 | 類型 | 本地路徑 | Notion URL | 推送日期 |"
    elif note_type == "paper":
        new_row = f"| {title} | — | {rel_path} | — | {page_url} | {today} |"
        table_header = "| Paper Key | 標題 | 筆記路徑 | 簡報路徑 | Notion URL | 推送日期 |"
    elif note_type == "progress":
        new_row = f"| {today} | {rel_path} | — | {page_url} | {today} |"
        table_header = "| 會議日期 | 摘要路徑 | 報告路徑 | Notion URL | 推送日期 |"
    else:  # resource
        domain = extra.get("domain", "—")
        kind = extra.get("kind", "文章")
        new_row = f"| {title} | {domain} | {kind} | {rel_path} | {page_url} | {today} |"
        table_header = "| 標題 | 領域 | 類型 | 本地路徑 | Notion URL | 推送日期 |"

    # Find the section and replace the placeholder row, or append new row
    placeholder_pattern = re.compile(
        r'(\| — \| — \|[^\n]*\n?)', re.MULTILINE
    )
    # Locate section
    sec_idx = index_text.find(section)
    if sec_idx == -1:
        # Section not found — append at end
        index_text += f"\n{section}\n{table_header}\n|{'-|' * table_header.count('|')}\n{new_row}\n"
    else:
        # Find the table in that section
        section_text = index_text[sec_idx:]
        # Find separator line and append after it
        sep_match = re.search(r'\|[-| ]+\|\n', section_text)
        if sep_match:
            insert_pos = sec_idx + sep_match.end()
            # Check if placeholder row exists right after separator
            after_sep = index_text[insert_pos:]
            if after_sep.startswith("| — "):
                # Replace placeholder with real row
                placeholder_end = index_text.index("\n", insert_pos) + 1
                index_text = index_text[:insert_pos] + new_row + "\n" + index_text[placeholder_end:]
            else:
                index_text = index_text[:insert_pos] + new_row + "\n" + index_text[insert_pos:]
        else:
            # No table yet — append after section heading
            index_text = index_text[:sec_idx + len(section)] + f"\n{table_header}\n|{'-|' * table_header.count('|')}\n{new_row}\n" + index_text[sec_idx + len(section):]

    NOTION_INDEX.write_text(index_text, encoding="utf-8")
    print(f"  Updated NOTION_INDEX.md — added to {section}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Push a Markdown note to Notion")
    parser.add_argument("--file", required=True, help="Path to the .md file (relative to workspace root)")
    parser.add_argument("--type", required=True, choices=list(DB_ENV_KEYS.keys()),
                        help="Note type: lecture | assignment | paper | progress | resource")
    parser.add_argument("--course", default="", help="Course name (for lecture/assignment types)")
    parser.add_argument("--domain", default="", help="Domain (for resource type): LLM_AI | 嵌入式 | 演算法 | 其他")
    parser.add_argument("--kind", default="", help="Kind for resource: 影片 | 文章; or assignment: 作業 | 專題")
    args = parser.parse_args()

    # Resolve file path
    file_path = Path(args.file)
    if not file_path.is_absolute():
        file_path = WORKSPACE_ROOT / file_path
    if not file_path.exists():
        print(f"ERROR: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    # Load env
    env = load_env(ENV_FILE)
    env.update(os.environ)  # allow real env vars to override

    token = env.get("NOTION_API_TOKEN", "")
    if not token or token.startswith("secret_xxx"):
        print("ERROR: NOTION_API_TOKEN is not set. Create .env from .env.example.", file=sys.stderr)
        sys.exit(1)

    db_env_key = DB_ENV_KEYS[args.type]
    db_id = env.get(db_env_key, "")
    if not db_id or "xxx" in db_id:
        print(f"ERROR: {db_env_key} is not set in .env.", file=sys.stderr)
        sys.exit(1)

    # Parse Markdown
    md_text = file_path.read_text(encoding="utf-8")

    # Extract title from first # heading
    title_match = re.search(r'^#\s+(.+)', md_text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else file_path.stem

    print(f"Pushing: {file_path.name}")
    print(f"  Title: {title}")
    print(f"  Type:  {args.type} → database {db_id[:8]}...")

    blocks = md_to_blocks(md_text)
    print(f"  Blocks: {len(blocks)}")

    with httpx.Client(timeout=60.0) as client:
        page = create_notion_page(client, token, db_id, title, blocks)

    page_url = page.get("url", "")
    print(f"  Notion URL: {page_url}")

    extra = {
        "course": args.course,
        "domain": args.domain,
        "kind": args.kind,
    }
    update_notion_index(file_path, args.type, title, page_url, extra)
    print("Done.")


if __name__ == "__main__":
    main()

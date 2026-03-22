"""
Course Notes Pre-processor
===========================
Converts course materials into images + transcripts for Claude to read.

Usage:
    python process_notes.py <course_folder> [material_filename]

Examples:
    python process_notes.py "c:/assistant/作業系統"
    python process_notes.py "c:/assistant/記憶體與儲存系統" "L1_Storage Devices.pptx"

Output:
    <course>/投影片/<stem>/slide_001.png ...   ← one PNG per slide
    <course>/逐字稿/<stem>.txt                 ← Whisper transcript (if audio exists)

Folder structure expected:
    <course_folder>/
        教材/    <- .pptx or .pdf files
        錄音/    <- .mp3 or .mp4 files (optional, matched by stem name)
        投影片/  <- output slide images (auto-created)
        逐字稿/  <- output transcripts (auto-created)
        筆記/    <- Claude writes .md notes here
"""

import sys
import os
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ── CUDA DLL fix for faster-whisper ────────────────────────────────────────────
_cuda_dirs = [
    r"C:\ProgramData\miniconda3\envs\notes-ai\Library\bin",
    r"C:\ProgramData\miniconda3\envs\notes-ai\Lib\site-packages\nvidia\cublas\bin",
    r"C:\ProgramData\miniconda3\envs\notes-ai\Lib\site-packages\nvidia\cudnn\bin",
    r"C:\ProgramData\miniconda3\envs\notes-ai\Lib\site-packages\nvidia\cuda_runtime\bin",
]
os.environ["PATH"] = ";".join(_cuda_dirs) + ";" + os.environ.get("PATH", "")
for d in _cuda_dirs:
    if os.path.isdir(d):
        os.add_dll_directory(d)


# ── PPTX → PNG via PowerPoint COM ──────────────────────────────────────────────

def pptx_to_images(pptx_path: Path, output_dir: Path):
    """Export each slide as PNG using PowerPoint COM automation."""
    import win32com.client
    import pythoncom

    pythoncom.CoInitialize()
    output_dir.mkdir(parents=True, exist_ok=True)

    ppt_app = win32com.client.Dispatch("PowerPoint.Application")
    ppt_app.Visible = True

    try:
        abs_pptx = str(pptx_path.resolve())
        abs_out = str(output_dir.resolve())
        prs = ppt_app.Presentations.Open(abs_pptx, ReadOnly=True, WithWindow=False)
        prs.Export(abs_out, "PNG")
        prs.Close()
        n = len(list(output_dir.glob("*.png")))
        print(f"  Exported {n} slides → {output_dir}")
    finally:
        ppt_app.Quit()
        pythoncom.CoUninitialize()


# ── PDF → PNG via pymupdf ───────────────────────────────────────────────────────

def pdf_to_images(pdf_path: Path, output_dir: Path, dpi: int = 150):
    """Export each PDF page as PNG using pymupdf."""
    import fitz

    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    mat = fitz.Matrix(dpi / 72, dpi / 72)

    for i, page in enumerate(doc, 1):
        png_path = output_dir / f"slide_{i:03d}.png"
        pix = page.get_pixmap(matrix=mat)
        pix.save(str(png_path))

    print(f"  Exported {len(doc)} pages → {output_dir}")
    doc.close()


# ── Audio transcription ────────────────────────────────────────────────────────

def transcribe(audio_path: Path, transcript_dir: Path, model_size: str = "medium") -> Path:
    """Transcribe audio and save to transcript_dir/<stem>.txt. Returns path."""
    from faster_whisper import WhisperModel

    transcript_dir.mkdir(parents=True, exist_ok=True)
    out_path = transcript_dir / (audio_path.stem + ".txt")

    print(f"  Loading Whisper '{model_size}' model...")
    model = WhisperModel(model_size, device="cuda", compute_type="float16")

    print(f"  Transcribing {audio_path.name} ...")
    segments, info = model.transcribe(str(audio_path), beam_size=5, language="en")
    print(f"  Detected language: {info.language} ({info.language_probability:.2f})")

    text = " ".join(seg.text.strip() for seg in segments)
    out_path.write_text(text, encoding="utf-8")
    print(f"  Transcript saved → {out_path} ({len(text)} chars)")
    return out_path


# ── Main ───────────────────────────────────────────────────────────────────────

AUDIO_EXTS = {".mp3", ".mp4", ".m4a", ".wav", ".ogg"}
MATERIAL_EXTS = {".pptx", ".pdf"}


def process_material(material_path: Path, recording_dir: Path, slides_dir: Path, transcript_dir: Path):
    stem = material_path.stem
    print(f"\n{'='*60}")
    print(f"Processing: {material_path.name}")

    # Convert slides to images
    slide_out = slides_dir / stem
    ext = material_path.suffix.lower()
    if ext == ".pptx":
        pptx_to_images(material_path, slide_out)
    elif ext == ".pdf":
        pdf_to_images(material_path, slide_out)
    else:
        print(f"  Unsupported format: {ext}, skipping.")
        return

    # Transcribe matching audio (if any)
    if recording_dir.exists():
        for audio_ext in AUDIO_EXTS:
            candidate = recording_dir / (stem + audio_ext)
            if candidate.exists():
                print(f"  Matched audio: {candidate.name}")
                transcribe(candidate, transcript_dir)
                break
        else:
            print(f"  No matching audio found in 錄音/ (skipping transcription)")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    course_dir = Path(sys.argv[1])
    if not course_dir.exists():
        print(f"Error: folder not found: {course_dir}")
        sys.exit(1)

    material_dir = course_dir / "教材"
    recording_dir = course_dir / "錄音"
    slides_dir = course_dir / "投影片"
    transcript_dir = course_dir / "逐字稿"

    if not material_dir.exists():
        print(f"Error: 教材/ folder not found inside {course_dir}")
        sys.exit(1)

    if len(sys.argv) >= 3:
        target = material_dir / sys.argv[2]
        if not target.exists():
            print(f"Error: {target} not found")
            sys.exit(1)
        materials = [target]
    else:
        materials = sorted(f for f in material_dir.iterdir() if f.suffix.lower() in MATERIAL_EXTS)
        if not materials:
            print(f"No .pptx or .pdf files found in {material_dir}")
            sys.exit(1)

    print(f"Course: {course_dir.name}")
    print(f"Materials: {[m.name for m in materials]}")

    for mat in materials:
        process_material(mat, recording_dir, slides_dir, transcript_dir)

    print(f"\nDone! Slides → {slides_dir} | Transcripts → {transcript_dir}")
    print("Next: ask Claude to read the images and generate notes.")


if __name__ == "__main__":
    main()

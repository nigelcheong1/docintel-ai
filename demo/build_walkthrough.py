"""Build a 48-second captioned walkthrough from the committed real app screens."""

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCENES = [
    ("documents.jpg", "Documents", "Six public/fictional inputs in an isolated workspace; no personal uploads."),
    ("search-overview.jpg", "Ask a scoped question", "Select the fictional invoice and enable Verified Answers."),
    ("search.jpg", "Read the cited answer", "USD 550.00 is linked to page evidence; diagnostics expose selection and checks."),
    ("source.jpg", "Inspect the original", "Open the rendered source page to check the invoice table and total."),
    ("workbench.jpg", "Inspect extraction", "The workbench separates page previews, extracted chunks, and indexing health."),
    ("evaluation.jpg", "Measure honestly", "25 reviewed cases: 18 automatic passes, 7 failures. Scoped checks, not general accuracy."),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=Path("C:/Windows/Fonts/arial.ttf"))
    args = parser.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not args.font.is_file():
        parser.error("Install FFmpeg and supply an existing TrueType font with --font.")
    scratch = ROOT / ".local/video"
    scratch.mkdir(parents=True, exist_ok=True)
    source = ROOT.parent / "docs/demo/screenshots"
    font = args.font.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
    for index, (filename, title, caption) in enumerate(SCENES):
        (scratch / "title.txt").write_text(f"DocIntel AI | {index + 1:02d}/06 | {title} | Actual app screens", encoding="utf-8")
        (scratch / "caption.txt").write_text(caption, encoding="utf-8")
        filters = (
            "scale=1440:900:force_original_aspect_ratio=decrease,"
            "pad=1440:1020:(ow-iw)/2:0:color=0x101827,"
            f"drawtext=fontfile='{font}':textfile=title.txt:fontcolor=white:fontsize=22:x=32:y=920,"
            f"drawtext=fontfile='{font}':textfile=caption.txt:fontcolor=white:fontsize=22:x=32:y=965"
        )
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-framerate", "24",
            "-i", str(source / filename), "-t", "8", "-vf", filters,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", f"scene-{index}.mp4"], cwd=scratch, check=True)
    (scratch / "concat.txt").write_text("".join(f"file 'scene-{index}.mp4'\n" for index in range(len(SCENES))), encoding="utf-8")
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "1", "-i", "concat.txt",
        "-c", "copy", "-movflags", "+faststart", str(ROOT.parent / "docs/demo/walkthrough.mp4")], cwd=scratch, check=True)
    print("Built docs/demo/walkthrough.mp4 (48s, screen-based, no audio).")


if __name__ == "__main__":
    main()

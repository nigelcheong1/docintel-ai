from pathlib import Path
import subprocess


def download_funsd(target_dir: Path) -> Path:
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    if target_dir.exists():
        return target_dir
    subprocess.run(
        ["git", "clone", "--depth", "1", "https://github.com/crcresearch/FUNSD.git", str(target_dir)],
        check=True,
    )
    return target_dir


if __name__ == "__main__":
    location = download_funsd(Path("data/raw/funsd"))
    print(f"FUNSD repository is available at {location}")

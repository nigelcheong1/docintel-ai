from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def list_funsd_images(dataset_dir: Path) -> list[Path]:
    image_dirs = [dataset_dir / "data" / "images"]
    image_dirs.extend(sorted((dataset_dir / "dataset").glob("*_data/images")))

    images: list[Path] = []
    for image_dir in image_dirs:
        if not image_dir.exists():
            continue
        images.extend(path for path in image_dir.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS)
    return sorted(images)


def list_funsd_dataset_pointers(dataset_dir: Path) -> list[Path]:
    datasets_dir = dataset_dir / "datasets"
    if not datasets_dir.exists():
        return []
    return sorted(datasets_dir.glob("*.dvc"))


def list_funsd_qa_files(dataset_dir: Path) -> list[Path]:
    qa_dir = dataset_dir / "datasets" / "FUNSD_QA"
    if not qa_dir.exists():
        return []
    return sorted(qa_dir.glob("*/qa_pairs_*.json"))


if __name__ == "__main__":
    dataset_root = Path("data/raw/funsd")
    images = list_funsd_images(dataset_root)
    dvc_files = list_funsd_dataset_pointers(dataset_root)
    qa_files = list_funsd_qa_files(dataset_root)
    print(f"Found {len(images)} FUNSD image files.")
    print(f"Found {len(dvc_files)} FUNSD DVC dataset pointer files.")
    print(f"Found {len(qa_files)} FUNSD QA JSON files.")

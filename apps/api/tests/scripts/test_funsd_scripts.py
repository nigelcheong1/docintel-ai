from scripts.download_funsd import download_funsd
from scripts.ingest_funsd import list_funsd_dataset_pointers, list_funsd_images, list_funsd_qa_files


def test_download_funsd_returns_existing_target_directory(tmp_path):
    target_dir = tmp_path / "funsd"
    target_dir.mkdir()

    assert download_funsd(target_dir) == target_dir


def test_list_funsd_images_returns_png_and_jpg_files(tmp_path):
    image_dir = tmp_path / "data" / "images"
    image_dir.mkdir(parents=True)
    png_file = image_dir / "form-a.png"
    jpg_file = image_dir / "form-b.jpg"
    text_file = image_dir / "notes.txt"
    png_file.write_bytes(b"png")
    jpg_file.write_bytes(b"jpg")
    text_file.write_text("not an image")

    images = list_funsd_images(tmp_path)

    assert images == [png_file, jpg_file]


def test_list_funsd_dataset_pointers_returns_dvc_files(tmp_path):
    datasets_dir = tmp_path / "datasets"
    datasets_dir.mkdir()
    pointer = datasets_dir / "FUNSD.dvc"
    pointer.write_text("outs: []")

    assert list_funsd_dataset_pointers(tmp_path) == [pointer]


def test_list_funsd_qa_files_returns_training_and_testing_json(tmp_path):
    qa_dir = tmp_path / "datasets" / "FUNSD_QA"
    training_dir = qa_dir / "training"
    testing_dir = qa_dir / "testing"
    training_dir.mkdir(parents=True)
    testing_dir.mkdir(parents=True)
    train_file = training_dir / "qa_pairs_0001.json"
    test_file = testing_dir / "qa_pairs_0002.json"
    metadata_file = qa_dir / "metadata.json"
    train_file.write_text("{}")
    test_file.write_text("{}")
    metadata_file.write_text("{}")

    assert list_funsd_qa_files(tmp_path) == [test_file, train_file]

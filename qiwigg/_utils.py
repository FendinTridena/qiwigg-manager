import sys
import json

from functools import partial
from pathlib import Path


def save_data(path, data):
    path = Path(path)
    tmp_path = path.with_suffix(f"{path.suffix}_tmp")
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent="\t")
    tmp_path.replace(path)


def load_metadata(file_path, metadata_path):
    file_path = Path(file_path)

    if metadata_path is None:
        metadata_path = file_path.with_suffix(f"{file_path.suffix}.qiwi_upload")

    try:
        with open(metadata_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}

    save_metadata = partial(save_data, metadata_path, data)

    return data, save_metadata, metadata_path.unlink


def upload_callback(uploaded, size):
    print(f"{100 * uploaded / size:.2f}% of {size} uploaded", file=sys.stderr)

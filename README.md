# qiwi.gg manager
Quick and dirty way to manage your files on qiwi.gg.

Features: uploading, moving and deleting files, listing files in folder, listing all folders, creating and deleting folders.

At the moment of writing this (2023-10-15) qiwi.gg has an official API for uploading but it involves sending the whole file all at once. This module uses internal API that uploads file in chunks. If one chunk fails to upload you end up reuploading just that chunk. Official API doesn't have any other features so I decided to use the internal one instead.

## Requirements
- pycryptodomex
- requests
- bs4
- pycurl (optional; if missing uploading will be done with requests)

Installing pycurl on Windows is a pain so consider using precompiled wheels, for example from [here](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pycurl).

## Usage

### Command line
To run from code use `python -m qiwigg`. When running from command line session cookies, and credentials are stored in `~/.config/qiwigg` (`%UserProfile%\.config\qiwigg` on Windows). Credentials are stored in `credentials.txt` file. In that folder you can create `chunk-size.txt` to override the default chunk size.

Just run `qiwigg --help` for usage.

### Python module
Uploading a file:

```py
from qiwigg import QiwiGG

...

manager = QiwiGG("email@example.com", "your super secret password", "path/to/cookie/jar")
file = manager.upload_file("path/to/file", chunk_size=500000000)

print(f"{file.id} {file.name} {file.url}")
```

You can omit email and password. Your session cookie is valid 15 days. Cookie jar file defaults to `cookies.txt` in your working directory.

## Notes
- Listing all folders may not work. Since there's no API for that it requires loading the dashboard page. Cloudflare may interfere with that.
- Chunk size by default is 100MB (10^8 bytes). You can set it as low as 5MiB (5 * 2^20) but more chunks means more requests to qiwi servers, and that means overall slower upload time.

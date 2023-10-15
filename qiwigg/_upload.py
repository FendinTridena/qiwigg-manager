import os
import io

from ._exceptions import UploadFailedError


def _finish(status_code, header_lines, body):
    if status_code == 200:
        for line in header_lines:
            if line.upper().startswith("ETAG:"):
                return line[5:].strip().strip('"')

    headers = "\n".join(header_lines)
    if b"Worker exceeded resource limits" in body:
        body = "Worker exceeded resource limits"
        headers = None
    raise UploadFailedError(
        f"Upload for chunk failed!",
        body,
        headers,
    )


try:
    import pycurl
except ModuleNotFoundError:
    import requests

    def upload_chunk(upload_url, chunk):
        r = requests.put(
            upload_url, headers={"Content-Length": str(chunk.size)}, data=chunk
        )
        header_lines = [f"{k}: {v}" for k, v in r.headers.items()]
        return _finish(r.status_code, header_lines, r.content)
else:
    def upload_chunk(upload_url, chunk):
        header_f = io.BytesIO()
        body_f = io.BytesIO()

        c = pycurl.Curl()

        c.setopt(c.URL, upload_url)
        c.setopt(c.UPLOAD, True)
        c.setopt(c.INFILESIZE, chunk.size)
        c.setopt(c.READDATA, chunk)
        c.setopt(c.WRITEDATA, body_f)
        c.setopt(c.WRITEHEADER, header_f)
        c.setopt(c.NOPROGRESS, False)

        try:
            c.perform()
        except pycurl.error as e:
            c.close()
            raise UploadFailedError(str(e), None, None)

        status_code = c.getinfo(c.RESPONSE_CODE)
        c.close()

        header_lines = header_f.getvalue().decode().splitlines()
        return _finish(status_code, header_lines, body_f.getvalue())

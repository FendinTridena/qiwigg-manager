import sys
import os
import datetime
import json
import base64
import datetime

from pathlib import Path
from http.cookiejar import LWPCookieJar, Cookie
from uuid import uuid4
from time import sleep

import requests
import bs4

from . import _exceptions, _qiwitypes
from ._utils import load_metadata, upload_callback
from ._crypto import encrypt
from ._chunk import Chunk
from ._upload import upload_chunk


__all__ = ["QiwiGG"]

NAME = "QiwiGG Manager"
VERSION = "1.0.0"
QIWI_URL = "https://qiwi.gg"
GITHUB = "https://github.com/FendinTridena/qiwigg-manager"


def find_newest_session(sessions):
    active_sessions = [
        (s["expire_at"], s["id"])
        for s in sessions
        if s["status"] == "active"
    ]
    if len(active_sessions) == 0:
        return None, None
    active_sessions.sort()

    expire_at, session_name = active_sessions[-1]
    session_expiration_date = datetime.datetime.fromtimestamp(
        # set expiration 2 seconds earlier
        expire_at/1000 - 2, tz=datetime.timezone.utc
    )

    return session_name, session_expiration_date


class QiwiGG:
    USER_AGENT = f"{NAME.replace(' ', '')}/{VERSION} ({GITHUB})"
    QIWI_API = f"{QIWI_URL}/api"
    CLERK_API = "https://clerk.qiwi.gg/v1"
    CLERK_JS_VERSION = "4.60.1"

    def __init__(
        self,
        email=None,
        password=None,
        cookie_jar_path=None,
        proxies=None,
        timeout=30,
    ):
        if cookie_jar_path is None:
            cookie_jar_path = "cookies.txt"

        self.session = requests.Session()
        self.session.headers["User-Agent"] = self.USER_AGENT
        self.session.cookies = LWPCookieJar(cookie_jar_path)

        try:
            self.session.cookies.load(ignore_discard=True)
        except FileNotFoundError:
            pass

        self.email = email
        self.password = password
        self.proxies = proxies
        self.timeout = timeout

        self._session_name = None
        self._session_expiration_date = None
        self._token_expiration_date = None

    def _save_cookies(self):
        try:
            self.session.cookies.save(ignore_discard=True)
        except FileNotFoundError:
            Path(self.session.cookies.filename).parent.mkdir(
                parents=True, exist_ok=True
            )
            self.session.cookies.save(ignore_discard=True)

    def set_client_cookie(self, cookie_value):
        in_10_years = datetime.datetime.now() + datetime.timedelta(days=3650)
        self.session.cookies.set_cookie(
            Cookie(
                version=0,
                name="__client",
                value=cookie_value,
                port=None,
                port_specified=False,
                domain=".clerk.qiwi.gg",
                domain_specified=True,
                domain_initial_dot=True,
                path="/",
                path_specified=True,
                secure=True,
                expires=in_10_years.timestamp(),
                discard=False,
                comment=None,
                comment_url=None,
                rest={"HttpOnly": None, "SameSite": "Lax"},
                rfc2109=True,
            )
        )
        self._save_cookies()

    def log_in(self, email=None, password=None, message=None):
        if email is None or password is None:
            email = self.email
            password = self.password
            if email is None or password is None:
                if message is None:
                    message = "Can't log in without email and password"
                raise _exceptions.AuthenticationError(message)

        self.session.cookies.clear()
        self._session_name = None
        self._session_expiration_date = None
        self._token_expiration_date = None

        self._clerk_api_call("get", "environment")
        data = self._clerk_api_call("post", "client/sign_ins", {"identifier": email})
        response = data["response"]
        if (
            response["object"] != "sign_in_attempt"
            or response["status"] != "needs_first_factor"
            or response["supported_first_factors"] is None
            or response["supported_second_factors"] is not None
            or response["first_factor_verification"] is not None
            or response["second_factor_verification"] is not None
        ):
            raise _exceptions.QiwiGGError("Can't log in (email step)")
        sia = response["id"]

        data = self._clerk_api_call(
            "post",
            f"client/sign_ins/{sia}/attempt_first_factor",
            {"strategy": "password", "password": password},
        )
        response = data["response"]
        if (
            response["object"] != "sign_in_attempt"
            or response["status"] != "complete"
        ):
            raise _exceptions.QiwiGGError("Can't log in (password step)")

        (
            self._session_name,
            self._session_expiration_date
        ) = find_newest_session(data["client"]["sessions"])

        if self._session_name is None:
            raise _exceptions.QiwiGGError("Can't log in, no session found")

        self._save_cookies()

    def _clerk_api_call(self, method, what, data=None):
        if self._session_expiration_date is not None:
            now = datetime.datetime.now(datetime.timezone.utc)
            if now > self._session_expiration_date:
                self.log_in()

        url = f"{self.CLERK_API}/{what}"

        r = self.session.request(
            method,
            url,
            params={"_clerk_js_version": self.CLERK_JS_VERSION},
            data=data,
            proxies=self.proxies,
            timeout=self.timeout,
        )
        response_data = r.json()

        if "errors" in response_data:
            error = response_data["errors"][0]
            if error.get("code") == "signed_out":
                self.log_in(message=error.get("long_message"))
                return self._clerk_api_call(method, what, data)

            raise _exceptions.QiwiGGError(json.dumps(response_data["errors"]))

        return response_data

    def _get_session(self):
        data = self._clerk_api_call("get", "client")["response"]
        if data is None:
            self.log_in(message="Not logged in")
            return self._get_session()

        (
            self._session_name,
            self._session_expiration_date
        ) = find_newest_session(data["sessions"])

        if self._session_name is None:
            self.log_in(message="No active sessions found")
            return self._get_session()

    @property
    def session_name(self):
        if self._session_name is None:
            self._get_session()

        return self._session_name

    def _touch(self):
        data = self._clerk_api_call(
            "post",
            f"client/sessions/{self.session_name}/touch",
            {"active_organization_id": ""},
        )

    def _get_token(self):
        if self._token_expiration_date is not None:
            now = datetime.datetime.now(datetime.timezone.utc)
            if self._token_expiration_date > now:
                return

        data = self._clerk_api_call(
            "post", f"client/sessions/{self.session_name}/tokens"
        )
        token = data["jwt"]
        expire_at = json.loads(base64.b64decode(f'{token.split(".")[1]}=='))["exp"]
        self._token_expiration_date = datetime.datetime.fromtimestamp(
            # set expiration 2 seconds earlier
            expire_at - 2, tz=datetime.timezone.utc
        )
        self.session.cookies.set_cookie(
            Cookie(
                version=0,
                name="__session",
                value=token,
                port=None,
                port_specified=False,
                domain="qiwi.gg",
                domain_specified=True,
                domain_initial_dot=False,
                path="/",
                path_specified=True,
                secure=True,
                expires=self._token_expiration_date.timestamp(),
                discard=False,
                comment=None,
                comment_url=None,
                rest={"SameSite": "Lax"},
                rfc2109=True,
            )
        )

    def _qiwi_request(self, method, what, data=None, params=None):
        self._get_token()

        headers = {}
        if data is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(data, cls=_qiwitypes.QiwiIDJSONEncoder)

        r = self.session.request(
            method,
            f"{self.QIWI_API}/{what}",
            params=params,
            data=data,
            headers=headers,
            proxies=self.proxies,
            timeout=self.timeout,
        )
        try:
            data = r.json()
        except:
            raise _exceptions.QiwiGGError(f"Can't parse response: {r.text}")
        if "success" not in data or not data["success"]:
            raise _exceptions.QiwiGGError(f"Request failed: {r.text}")
        return data

    def get_folders(self):
        self._get_token()
        r = self.session.get(
            f"{QIWI_URL}/dashboard", proxies=self.proxies, timeout=self.timeout
        )
        soup = bs4.BeautifulSoup(r.content, features="html.parser")
        for script in soup.select("script"):
            if script.text.startswith('self.__next_f.push([1,"f:'):
                start = script.text.find('"')
                end = script.text.rfind('"') + 1
                tmp1 = json.loads(script.text[start:end])
                start = tmp1.find("[")
                end = tmp1.rfind("]") + 1
                tmp2 = json.loads(tmp1[start:end])
                for element in tmp2:
                    if isinstance(element, dict):
                        if "data" in element:
                            return [
                                _qiwitypes.QiwiFolder.from_object(x)
                                for x in element["data"]
                            ]

        raise _exceptions.QiwiGGError("Folder data not found")

    def create_folder(self, name, parent_id=None):
        data = self._qiwi_request(
            "post", "manageFolder", {"folderName": name, "parentFolder": parent_id}
        )

        if parent_id is None:
            parent_id = "nullFolder"

        return _qiwitypes.QiwiFolder(data["folderId"], data["folderName"], parent_id)

    def delete_folder(self, folder_id):
        self._qiwi_request("delete", "manageFolder", {"folderId": folder_id})

    def get_files(self, folder_id=None):
        if folder_id is None:
            folder_id = "nullFolder"

        data = self._qiwi_request("post", "getFolderFiles", {"folderId": folder_id})
        return [_qiwitypes.QiwiFile(x) for x in data["folderFiles"]]

    def move_file(self, file_id, folder_id):
        if folder_id is None:
            folder_id = "nullFolder"

        self._qiwi_request(
            "patch", "manageFile", {"fileId": file_id, "folderId": folder_id}
        )

        if isinstance(file_id, _qiwitypes.QiwiFile):
            file_id.parent_id = (
                folder_id.id if isinstance(folder_id, _qiwitypes.QiwiFolder)
                else folder_id
            )

        return folder_id

    def move_files(self, file_ids, folder_id):
        for file_id in file_ids:
            f_id = self.move_file(file_id, folder_id)

        return f_id

    def delete_file(self, file_id):
        self._qiwi_request("delete", "manageFile", {"fileId": file_id})

    def delete_files(self, file_ids):
        for file_id in file_ids:
            self.delete_file(file_id)

    def _initialize_upload(self, name, size):
        token = encrypt(str(size).encode())
        return self._qiwi_request(
            "post",
            "privateUpload",
            {
                "token": token.decode(),
            },
            {
                "fileSize": size,
                "id": uuid4(),
                "fileName": name,
                "fileType": "",
            },
        )

    def _get_upload_url(self, key, upload_id, part_number):
        response = self._qiwi_request(
            "post",
            "generatePreSigned",
            {
                "key": key,
                "uploadId": upload_id,
                "partNumber": part_number,
            },
        )
        return response["preSignedUrl"]

    def _upload_chunks(
        self, key, upload_id, etags, f, size, chunk_size, save_metadata, callback
    ):
        uploaded = 0
        for _, saved_chunk_size in etags:
            uploaded += saved_chunk_size
            if uploaded == size:
                break

            if saved_chunk_size != chunk_size:
                raise _exceptions.ChunkSizeError(
                    "All non-trailing parts must have the same length",
                    saved_chunk_size,
                    chunk_size,
                )

        if (size - uploaded) / chunk_size > 10000 - len(etags):
            raise _exceptions.QiwiGGError(
                "Use larger chunk size. "
                "There's a hard limit of 10000 chunks max per upload."
            )

        if callback is not None:
            callback(uploaded, size)

        tries = 0
        while uploaded < size:
            upload_url = self._get_upload_url(key, upload_id, len(etags) + 1)
            chunk = Chunk(f, uploaded, chunk_size)
            real_chunk_size = chunk.size

            try:
                etag = upload_chunk(upload_url, chunk)
            except _exceptions.UploadFailedError as e:
                tries += 1
                if tries >= 10:
                    raise
                print(e, file=sys.stderr)
                sleep(10)
                continue

            etags.append([etag, real_chunk_size])
            save_metadata()

            tries = 0
            uploaded += real_chunk_size

            if callback is not None:
                callback(uploaded, size)


    def _finalize_upload(self, key, upload_id, file_id, etags):
        parts = [
            {"PartNumber": i, "ETag": etag}
            for i, (etag, _) in enumerate(etags, start=1)
        ]
        response = self._qiwi_request(
            "post",
            "completeUpload",
            {
                "key": key,
                "uploadId": upload_id,
                "fileId": file_id,
                "completed": True,
                "parts": parts,
            },
        )
        return response["result"]

    def upload_file(
        self,
        file_path,
        metadata_path=None,
        chunk_size=None,
        callback=upload_callback,
    ):
        if chunk_size is None:
            chunk_size = 100000000
        chunk_size = max(5242880, chunk_size)

        file_path = Path(file_path)
        name = file_path.name
        size = os.path.getsize(file_path)

        data, save_metadata, delete_metadata = load_metadata(file_path, metadata_path)

        if "info" not in data:
            data["info"] = self._initialize_upload(name, size)
            save_metadata()

        file_id = data["info"]["result"]
        key = data["info"]["key"]
        upload_id = data["info"]["uploadId"]
        etags = data.setdefault("etags", [])

        with open(file_path, "rb") as f:
            self._upload_chunks(
                key, upload_id, etags, f, size, chunk_size, save_metadata, callback
            )

        timestamp = datetime.datetime.now().isoformat()[:23]

        if "final" not in data:
            data["final"] = self._finalize_upload(key, upload_id, file_id, etags)
            save_metadata()

        if "createdAt" not in data["final"]:
            data["final"]["createdAt"] = f"{timestamp}Z"
            save_metadata()

        file = _qiwitypes.QiwiFile(data["final"])
        delete_metadata()
        return file

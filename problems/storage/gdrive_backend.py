"""
Google Drive implementation of StorageBackend.

Drive has no real paths, so ``test_cases/12/01`` is stored as nested folders
(test_cases -> 12 -> file "01"). Folders are found or created on demand and
existing files are updated in place, so re-running a migration never leaves
duplicates.

Authentication is OAuth for a desktop app: run
``python manage.py gdrive_auth`` once to sign in and create the token file.
"""
import io
import logging
import os
from typing import List, Optional

from django.conf import settings

from .base import StorageBackend

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_MIME = "application/vnd.google-apps.folder"


def get_token_path() -> str:
    """Token file location: GOOGLE_DRIVE_TOKEN_FILE, or token.json next to the credentials file."""
    explicit = getattr(settings, "GOOGLE_DRIVE_TOKEN_FILE", None)
    if explicit:
        return explicit
    creds_file = settings.GOOGLE_DRIVE_CREDENTIALS_FILE
    return os.path.join(os.path.dirname(os.path.abspath(creds_file)), "token.json")


def load_credentials():
    """Load saved OAuth credentials, refreshing them if they have expired."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    token_path = get_token_path()
    if not os.path.exists(token_path):
        raise RuntimeError(
            f"Google Drive token not found at {token_path}. "
            "Run `python manage.py gdrive_auth` once to sign in."
        )
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "w") as fh:
                fh.write(creds.to_json())
        else:
            raise RuntimeError("Google Drive token is invalid. Run `python manage.py gdrive_auth` again.")
    return creds


def _q(value: str) -> str:
    """Escape a value for use inside a Drive query string."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


class GoogleDriveBackend(StorageBackend):
    def __init__(self, service=None):
        if service is None:
            from googleapiclient.discovery import build

            service = build("drive", "v3", credentials=load_credentials(), cache_discovery=False)
        self._svc = service
        self._root_id = getattr(settings, "GOOGLE_DRIVE_FOLDER_ID", None) or "root"
        self._folder_cache = {}  # "test_cases/12" -> folder id

    # ---- low-level helpers -------------------------------------------------
    def _find(self, name: str, parent_id: str, folder: bool = False) -> Optional[str]:
        query = f"name = '{_q(name)}' and '{parent_id}' in parents and trashed = false"
        query += f" and mimeType {'=' if folder else '!='} '{FOLDER_MIME}'"
        resp = self._svc.files().list(q=query, fields="files(id, name)", pageSize=10).execute()
        files = resp.get("files", [])
        return files[0]["id"] if files else None

    def _folder_id(self, folder_path: str, create: bool) -> Optional[str]:
        """Resolve 'a/b/c' to a folder id, creating missing folders when ``create`` is True."""
        parent = self._root_id
        walked = []
        for part in [p for p in folder_path.split("/") if p]:
            walked.append(part)
            key = "/".join(walked)
            if key in self._folder_cache:
                parent = self._folder_cache[key]
                continue
            folder_id = self._find(part, parent, folder=True)
            if folder_id is None:
                if not create:
                    return None
                meta = {"name": part, "mimeType": FOLDER_MIME, "parents": [parent]}
                folder_id = self._svc.files().create(body=meta, fields="id").execute()["id"]
            self._folder_cache[key] = folder_id
            parent = folder_id
        return parent

    def _list_children(self, folder_id: str) -> List[dict]:
        items, token = [], None
        while True:
            resp = self._svc.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=200,
                pageToken=token,
            ).execute()
            items.extend(resp.get("files", []))
            token = resp.get("nextPageToken")
            if not token:
                return items

    # ---- StorageBackend interface -----------------------------------------
    def upload_bytes(self, path: str, data: bytes) -> None:
        from googleapiclient.http import MediaIoBaseUpload

        folder_path, _, filename = path.rpartition("/")
        parent_id = self._folder_id(folder_path, create=True)
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype="application/octet-stream", resumable=False)
        existing = self._find(filename, parent_id)
        if existing:
            self._svc.files().update(fileId=existing, media_body=media).execute()
        else:
            self._svc.files().create(
                body={"name": filename, "parents": [parent_id]}, media_body=media, fields="id"
            ).execute()
        logger.info("Drive: uploaded %s", path)

    def delete_prefix(self, prefix: str) -> int:
        folder_id = self._folder_id(prefix.strip("/"), create=False)
        if folder_id is None:
            return 0
        children = self._list_children(folder_id)
        for child in children:
            self._svc.files().delete(fileId=child["id"]).execute()
        logger.info("Drive: deleted %d items under %s", len(children), prefix)
        return len(children)

    def list_files(self, prefix: str) -> List[str]:
        base = prefix.strip("/")
        folder_id = self._folder_id(base, create=False)
        if folder_id is None:
            return []
        return sorted(f"{base}/{c['name']}" for c in self._list_children(folder_id))

"""
Storage interface for test-case files.

The migration flow only talks to ``StorageBackend``; each provider (Azure,
Google Drive, ...) implements these three methods. The object layout is
defined once, here, so every provider produces the same structure:

    test_cases/{problem_id}/{test_number}      -> input file
    test_cases/{problem_id}/{test_number}.a    -> output file
"""
from abc import ABC, abstractmethod
from typing import List

ROOT_PREFIX = "test_cases"


def problem_prefix(problem_id) -> str:
    """Folder-like prefix that holds every file of one problem."""
    return f"{ROOT_PREFIX}/{problem_id}/"


def test_input_path(problem_id, test_number: int) -> str:
    return f"{ROOT_PREFIX}/{problem_id}/{test_number:02d}"


def test_output_path(problem_id, test_number: int) -> str:
    return f"{ROOT_PREFIX}/{problem_id}/{test_number:02d}.a"


def custom_checker_path(problem_id, filename: str) -> str:
    return f"{ROOT_PREFIX}/{problem_id}/{filename}"


class StorageBackend(ABC):
    """Minimal contract a storage provider must satisfy."""

    @abstractmethod
    def upload_bytes(self, path: str, data: bytes) -> None:
        """Create or overwrite the file at ``path`` (e.g. ``test_cases/1/01``)."""

    @abstractmethod
    def delete_prefix(self, prefix: str) -> int:
        """Delete every file under ``prefix``. Returns how many were deleted."""

    @abstractmethod
    def list_files(self, prefix: str) -> List[str]:
        """Return full paths of the files under ``prefix`` (used to verify uploads)."""

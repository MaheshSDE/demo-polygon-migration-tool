from django.conf import settings

from .base import StorageBackend

SUPPORTED_PROVIDERS = ("azure", "gdrive")


def get_storage_backend() -> StorageBackend:
    """Return the storage backend selected by the STORAGE_PROVIDER setting."""
    provider = (getattr(settings, "STORAGE_PROVIDER", None) or "azure").strip().lower()
    if provider == "azure":
        from .azure_backend import AzureBlobBackend
        return AzureBlobBackend()
    if provider == "gdrive":
        from .gdrive_backend import GoogleDriveBackend
        return GoogleDriveBackend()
    raise ValueError(
        f"Unsupported STORAGE_PROVIDER '{provider}'. Supported: {', '.join(SUPPORTED_PROVIDERS)}"
    )

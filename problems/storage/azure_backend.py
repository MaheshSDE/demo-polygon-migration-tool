import logging
from typing import List

from django.conf import settings

from .base import StorageBackend

logger = logging.getLogger(__name__)


class AzureBlobBackend(StorageBackend):
    """Azure Blob Storage implementation (original provider of this project)."""

    def __init__(self):
        # Imported lazily so the azure packages are only needed when this provider is used.
        from problems.AzureTestcase import AzureBlobManager

        self.container = settings.AZURE_CONTAINER_NAME
        self._manager = AzureBlobManager(
            account_url=settings.AZURE_STORAGE_ACCOUNT_URL,
            tenant_id=settings.AZURE_TENANT_ID,
            client_id=settings.AZURE_CLIENT_ID,
            username=settings.AZURE_USERNAME,
            password=settings.AZURE_PASSWORD,
        )
        self._client = self._manager.blob_service_client

    def upload_bytes(self, path: str, data: bytes) -> None:
        blob = self._client.get_blob_client(container=self.container, blob=path)
        blob.upload_blob(data, overwrite=True)
        logger.info("Azure: uploaded %s", path)

    def delete_prefix(self, prefix: str) -> int:
        container_client = self._client.get_container_client(self.container)
        names = [b.name for b in container_client.list_blobs(name_starts_with=prefix)]
        for name in names:
            container_client.delete_blob(name)
        logger.info("Azure: deleted %d blobs under %s", len(names), prefix)
        return len(names)

    def list_files(self, prefix: str) -> List[str]:
        container_client = self._client.get_container_client(self.container)
        return [b.name for b in container_client.list_blobs(name_starts_with=prefix)]

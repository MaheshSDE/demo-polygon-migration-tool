import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from problems.storage.gdrive_backend import SCOPES, get_token_path


class Command(BaseCommand):
    help = "One-time Google Drive sign-in. Opens a browser and saves an OAuth token file."

    def handle(self, *args, **options):
        from google_auth_oauthlib.flow import InstalledAppFlow

        creds_file = settings.GOOGLE_DRIVE_CREDENTIALS_FILE
        if not creds_file or not os.path.exists(creds_file):
            raise CommandError(
                "Set GOOGLE_DRIVE_CREDENTIALS_FILE in .env to the path of your OAuth credentials.json"
            )
        flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
        creds = flow.run_local_server(port=0)
        token_path = get_token_path()
        with open(token_path, "w") as fh:
            fh.write(creds.to_json())
        self.stdout.write(self.style.SUCCESS(f"Signed in. Token saved to {token_path}"))

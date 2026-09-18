"""Stage 6 CLI: publish an approved video via the official YouTube Data API.

Requires a one-time OAuth setup (see README's "YouTube upload setup" section):
1. In Google Cloud Console: create a project, enable "YouTube Data API v3",
   create an OAuth client ID of type "Desktop app", download it as
   client_secret.json into this project's root.
2. First run of this script opens a browser for one-time consent; the
   resulting refresh token is cached in token.json so later runs are
   unattended.

    python -m pipeline.upload_youtube <run_dir> [--privacy private|unlisted|public]

Reads <run_dir>/script.json for title (and derives a description from the
scene narration) and uploads <run_dir>/final.mp4.
"""
import argparse
import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from . import config

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_PATH = config.ROOT_DIR / "client_secret.json"
TOKEN_PATH = config.ROOT_DIR / "token.json"


def _get_credentials() -> Credentials:
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_PATH.exists():
                raise RuntimeError(
                    f"Missing {CLIENT_SECRET_PATH}. Create an OAuth 'Desktop app' "
                    "client in Google Cloud Console (with YouTube Data API v3 "
                    "enabled) and download it to that path."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return creds


def _build_description(scenes: list) -> str:
    return " ".join(s["narration"] for s in scenes)


def upload_video(run_dir: Path, privacy: str = "private") -> str:
    script = json.loads((run_dir / "script.json").read_text())
    video_path = run_dir / "final.mp4"
    if not video_path.exists():
        raise RuntimeError(f"No final.mp4 in {run_dir} -- run the editor stage first.")

    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": script["title"][:100],
            "description": _build_description(script["scenes"])[:5000],
            "categoryId": "24",  # Entertainment
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")

    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    url = f"https://youtu.be/{video_id}"
    print(f"Uploaded: {url} (privacy={privacy})")
    return url


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    args = parser.parse_args()
    upload_video(Path(args.run_dir), args.privacy)

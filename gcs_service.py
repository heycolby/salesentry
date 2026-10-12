import os
import datetime
import logging
import config

logger = logging.getLogger(__name__)

def get_video_stream_url(video_source: str = "") -> str:
    """
    Returns a playable URL for the video.
    If video_source is empty, uses config.INTRO_VIDEO_URL.
    If it's a Cloud Storage gs:// URI or bucket object name, generates a signed URL.
    Otherwise returns direct URL.
    """
    url = video_source or config.INTRO_VIDEO_URL

    if not url:
        return ""

    # Check if Google Cloud Storage signed URL is requested
    if url.startswith("gs://") or (config.GCS_BUCKET and not url.startswith("http")):
        try:
            from google.cloud import storage
            import google.auth
            from google.auth.transport import requests as ga_requests

            client = storage.Client(project=config.GCP_PROJECT_ID) if config.GCP_PROJECT_ID else storage.Client()
            
            bucket_name = config.GCS_BUCKET
            blob_name = url
            if url.startswith("gs://"):
                parts = url[5:].split("/", 1)
                bucket_name = parts[0]
                blob_name = parts[1] if len(parts) > 1 else ""

            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)

            creds, _ = google.auth.default()
            creds.refresh(ga_requests.Request())

            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(hours=2),
                method="GET",
                service_account_email=getattr(creds, "service_account_email", None),
                access_token=getattr(creds, "token", None)
            )
            return signed_url
        except Exception as e:
            logger.warning(f"Could not generate GCS signed URL for {url}: {e}. Returning raw URL.")
            return url

    return url

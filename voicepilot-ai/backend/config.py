import os

# Both configurable via .env — defaults are sane for local dev.
# In production you'd likely set these lower.

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "200"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

MAX_DURATION_MINUTES = int(os.getenv("MAX_DURATION_MINUTES", "90"))
MAX_DURATION_SECONDS = MAX_DURATION_MINUTES * 60

# Whisper needs an actual audio format it can decode. UploadFile.content_type
# comes from the browser/client and isn't fully trustworthy on its own
# (e.g. browsers recording via MediaRecorder often send "video/webm" or
# "application/octet-stream" even though it's audio-only), so we check file
# extension too as a second signal.
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm", ".ogg", ".flac"}

# --- Gemini (Google AI Studio) ---
# Free tier, no credit card. Get a key at https://aistudio.google.com
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

# --- OpenRouter / Qwen ---
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen/qwen3-8b")

# --- Object storage (S3 API: MinIO locally, AWS S3 in production) ---
# S3_ENDPOINT_URL is how containers reach storage (http://minio:9000).
# Leave it unset for real AWS S3 — boto3 then uses the AWS default endpoint.
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL") or None
# Presigned URLs are signed for a specific host, so they must be generated
# with the host the *browser* will use. Defaults to the internal endpoint
# (correct for AWS, where both are the same).
S3_PUBLIC_ENDPOINT_URL = os.getenv("S3_PUBLIC_ENDPOINT_URL") or S3_ENDPOINT_URL
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET", "voicepilot-audio")
S3_PRESIGNED_EXPIRY_SECONDS = int(os.getenv("S3_PRESIGNED_EXPIRY_SECONDS", "900"))

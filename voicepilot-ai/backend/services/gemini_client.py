from google import genai

from config import GEMINI_API_KEY

_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Returns a shared Gemini client, built once and reused everywhere."""
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to backend/.env "
                "(get a free key at https://aistudio.google.com)"
            )
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_env_file() -> dict[str, str]:
    env_path = PROJECT_ROOT / ".env"
    values: dict[str, str] = {}

    if not env_path.exists():
        return values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

    return values


class Setting:
    def __init__(self) -> None:
        env_values = _load_env_file()

        self.DATABASE_URL = self._get_str(
            env_values,
            "DATABASE_URL",
            "postgresql://postgres:postgrespw123@localhost:5432/qlip_cs",
        )
        self.REDIS_URI = self._get_str(
            env_values,
            "REDIS_URI",
            "redis://:redispw123@localhost:6379/0",
        )
        self.TYPESENSE_URI = self._get_str(
            env_values,
            "TYPESENSE_URI",
            "http://localhost:8108",
        )
        self.TYPESENSE_API_KEY = self._get_str(env_values, "TYPESENSE_API_KEY", "typesensepw123")
        self.TYPESENSE_VECTOR_DIM = self._get_int(env_values, "TYPESENSE_VECTOR_DIM", 1536)
        self.TYPESENSE_TIMEOUT_SECONDS = self._get_int(
            env_values,
            "TYPESENSE_TIMEOUT_SECONDS",
            30,
        )

        self.GEMINI_EMBEDDING_MODEL = self._get_str(
            env_values,
            "GEMINI_EMBEDDING_MODEL",
            "models/gemini-embedding-001",
        )
        self.GEMINI_EMBEDDING_TASK_TYPE = self._get_str(
            env_values,
            "GEMINI_EMBEDDING_TASK_TYPE",
            "RETRIEVAL_DOCUMENT",
        )
        self.GEMINI_EMBEDDING_BATCH_SIZE = self._get_int(
            env_values,
            "GEMINI_EMBEDDING_BATCH_SIZE",
            10,
        )
        self.GEMINI_API_BASE_URL = self._get_str(
            env_values,
            "GEMINI_API_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta",
        )
        self.GEMINI_API_KEY = self._get_str(env_values, "GEMINI_API_KEY", "")

        self.WHATSAPP_ACCESS_TOKEN = self._get_str(
            env_values,
            "WHATSAPP_ACCESS_TOKEN",
            "YOUR_WHATSAPP_ACCESS_TOKEN_HERE",
        )
        self.WHATSAPP_PHONE_NUMBER_ID = self._get_str(
            env_values,
            "WHATSAPP_PHONE_NUMBER_ID",
            "YOUR_WHATSAPP_PHONE_NUMBER_ID_HERE",
        )
        self.WHATSAPP_BUSINESS_ACCOUNT_ID = self._get_str(
            env_values,
            "WHATSAPP_BUSINESS_ACCOUNT_ID",
            "YOUR_WHATSAPP_BUSINESS_ACCOUNT_ID_HERE",
        )
        self.WHATSAPP_VERIFY_TOKEN = self._get_str(
            env_values,
            "WHATSAPP_VERIFY_TOKEN",
            "YOUR_WHATSAPP_VERIFY_TOKEN_HERE",
        )
        self.WHATSAPP_APP_SECRET = self._get_str(
            env_values,
            "WHATSAPP_APP_SECRET",
            "YOUR_WHATSAPP_APP_SECRET_HERE",
        )

    @staticmethod
    def _get_str(env_values: dict[str, str], key: str, default: str) -> str:
        return os.getenv(key, env_values.get(key, default))

    @staticmethod
    def _get_int(env_values: dict[str, str], key: str, default: int) -> int:
        value = os.getenv(key, env_values.get(key))
        if value in (None, ""):
            return default
        return int(value)


setting = Setting()

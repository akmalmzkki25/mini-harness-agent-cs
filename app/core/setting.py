from pydantic_settings import BaseSettings, SettingsConfigDict


class Setting(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgrespw123@localhost:5432/qlip_cs"
    REDIS_URI: str = "redis://:redispw123@localhost:6379/0"
    TYPESENSE_URI: str = "http://localhost:8108"
    TYPESENSE_API_KEY: str = "typesensepw123"
    TYPESENSE_VECTOR_DIM: int = 1536
    TYPESENSE_TIMEOUT_SECONDS: int = 30

    GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-001"
    GEMINI_EMBEDDING_TASK_TYPE: str = "RETRIEVAL_DOCUMENT"
    GEMINI_EMBEDDING_BATCH_SIZE: int = 10
    GEMINI_API_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    GEMINI_API_KEY: str = ""

    WHATSAPP_ACCESS_TOKEN: str = "YOUR_WHATSAPP_ACCESS_TOKEN_HERE"
    WHATSAPP_PHONE_NUMBER_ID: str = "YOUR_WHATSAPP_PHONE_NUMBER_ID_HERE"
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = "YOUR_WHATSAPP_BUSINESS_ACCOUNT_ID_HERE"
    WHATSAPP_VERIFY_TOKEN: str = "YOUR_WHATSAPP_VERIFY_TOKEN_HERE"
    WHATSAPP_APP_SECRET: str = "YOUR_WHATSAPP_APP_SECRET_HERE"
    WHATSAPP_GRAPH_API_VERSION: str = "v20.0"
    WHATSAPP_GRAPH_API_BASE_URL: str = "https://graph.facebook.com"
    USE_WHATSAPP_WEBHOOK: bool = False
    USE_WEBSITE: bool = True
    WEBSITE_DUMMY_AUTH_TOKEN: str = "dev-token"

    GEMINI_CHAT_MODEL: str = "models/gemini-3-flash-preview"
    AGENT_MAX_RAW_MESSAGES: int = 10
    AGENT_HANDOFF_TIMEOUT_SECONDS: int = 300
    AGENT_SCHEDULER_INTERVAL_SECONDS: int = 45

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


setting = Setting()

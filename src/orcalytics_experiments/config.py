"""Load local configuration without creating clients or remote stores on import."""

import os
from pathlib import Path

from dotenv import load_dotenv


def load_environment(env_file=None):
    """Load the working directory's .env, preserving exported environment variables."""
    load_dotenv(Path(env_file) if env_file else Path.cwd() / ".env", override=False)


def create_client():
    """Create an API client only when the caller explicitly starts an online operation."""
    from openai import OpenAI

    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise ValueError("Set OPENAI_API_KEY in your environment or local .env file.")
    return OpenAI()


def default_model(task, strategy="vector"):
    override = os.getenv("OPENAI_MODEL", "").strip()
    return override or ("gpt-5.1" if (task, strategy) == ("industry", "vector") else "gpt-5-mini")


def store_id_for(task):
    variable = "EVENT_VECTOR_STORE_ID" if task == "event" else "INDUSTRY_VECTOR_STORE_ID"
    return os.getenv(variable, "").strip() or None

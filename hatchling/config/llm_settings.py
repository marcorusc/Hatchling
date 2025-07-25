"""Settings for LLM (Large Language Model) configuration."""

import os
from typing import Optional
from pydantic import BaseModel, Field, validator
from enum import Enum

from .settings_access_level import SettingAccessLevel

class ELLMProvider(Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"

class LLMSettings(BaseModel):
    """Settings for LLM (Large Language Model) configuration."""

    # Provider selection
    provider: ELLMProvider = Field(
        default_factory=lambda: LLMSettings._get_provider_from_env(),
        description="LLM provider to use ('ollama' or 'openai').",
        json_schema_extra={"access_level": SettingAccessLevel.NORMAL},
    )
    
    @staticmethod
    def _get_provider_from_env() -> ELLMProvider:
        """Get provider from environment variable with fallback to default."""
        env_provider = os.environ.get("LLM_PROVIDER", "ollama").lower()
        if env_provider == "openai":
            return ELLMProvider.OPENAI
        return ELLMProvider.OLLAMA
    
    @validator('provider', pre=True)
    def validate_provider(cls, v):
        """Validate and convert provider from environment variable."""
        if isinstance(v, str):
            # Handle environment variable string values
            v_lower = v.lower()
            if v_lower == "ollama":
                return ELLMProvider.OLLAMA
            elif v_lower == "openai":
                return ELLMProvider.OPENAI
            else:
                raise ValueError(f"Invalid provider: {v}. Must be 'ollama' or 'openai'")
        elif isinstance(v, ELLMProvider):
            return v
        else:
            raise ValueError(f"Provider must be string or ELLMProvider enum, got {type(v)}")

    model: str = Field(
        default_factory=lambda: os.environ.get("LLM_MODEL", "llama3.2"),
        description="Default model to use for the selected provider.",
        json_schema_extra={"access_level": SettingAccessLevel.NORMAL},
    )

    @property
    def get_provider(self) -> str:
        """Return the current LLM provider."""
        if isinstance(self.provider, str):
            return self.provider
        return self.provider.value

    def get_active_model(self) -> str:
        """Return the current active model.
        
        Returns:
            str: The active model name.
        """
        return self.model

    class Config:
        extra = "forbid"
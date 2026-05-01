from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	openai_api_key: str = Field(..., description="OpenAI API key")
	openai_model: str = Field("gpt-4o-mini", description="OpenAI model")
	twilio_account_sid: str = Field(..., description="Twilio Account SID")
	twilio_auth_token: str = Field(..., description="Twilio Auth Token")
	twilio_whatsapp_from: str = Field(
		..., description='Twilio WhatsApp from number in the format "whatsapp:+1234567890"'
	)
	twilio_whatsapp_to: str = Field(
		..., description='Twilio WhatsApp to number in the format "whatsapp:+0987654321"'
	)
	x_auth_token: str = Field(..., description="X session cookie auth_token")
	x_ct0: str = Field(..., description="X session cookie ct0")
	x_search_query: str = Field(
		"SDE intern hiring apply join us",
		description="X search query",
	)
	poll_interval_minutes: int = Field(10, description="Polling interval in minutes")
	sqlite_db_path: str = Field("data/hiring_agent.db", description="SQLite database path")
	log_level: str = Field("INFO", description="Log level")

	model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

	@model_validator(mode="after")
	def validate_whatsapp_numbers(self) -> "Settings":
		if not self.twilio_whatsapp_from.startswith("whatsapp:"):
			raise ValueError('twilio_whatsapp_from must start with "whatsapp:"')
		if not self.twilio_whatsapp_to.startswith("whatsapp:"):
			raise ValueError('twilio_whatsapp_to must start with "whatsapp:"')
		return self


Settings = Settings()

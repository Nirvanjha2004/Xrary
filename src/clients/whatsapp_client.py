import structlog
from twilio.rest import Client

from src.config import Settings


class WhatsAppClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self.from_number = settings.twilio_whatsapp_from
        self.to_number = settings.twilio_whatsapp_to
        self.logger = structlog.get_logger()

    def send_notification(self, message: str) -> str:
        """
        Send a notification via WhatsApp using Twilio.

        Args:
            message: The message content to send

        Returns:
            The message SID from Twilio

        Raises:
            Any exception raised by Twilio client is caught, logged, and re-raised
        """
        try:
            msg = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=self.to_number,
            )
            self.logger.info("whatsapp notification sent", message_sid=msg.sid)
            return msg.sid
        except Exception as e:
            self.logger.error("failed to send whatsapp notification", error=str(e), error_type=type(e).__name__)
            raise

    def format_tweet_alert(
        self,
        tweet_text: str,
        author: str,
        company: str | None,
        role: str | None,
        location: str | None,
        apply_link: str | None,
        confidence: float,
    ) -> str:
        """
        Format a tweet into a WhatsApp markdown alert message.

        Args:
            tweet_text: The tweet content
            author: Twitter handle (username) of the author
            company: Company name or None
            role: Job role or None
            location: Job location or None
            apply_link: URL to apply link or None
            confidence: Confidence score as a float (0.0 to 1.0)

        Returns:
            Formatted WhatsApp markdown message
        """
        # Truncate tweet text to 300 characters
        truncated_tweet = tweet_text[:300]
        ellipsis = "..." if len(tweet_text) > 300 else ""

        message = f"""🚀 *SDE Intern Alert*

*Company:* {company or "Unknown"}
*Role:* {role or "SDE Intern"}
*Location:* {location or "Not specified"}
*Confidence:* {confidence:.0%}

*Tweet by @{author}:*
{truncated_tweet}{ellipsis}

*Apply Link:* {apply_link or "Check tweet for link"}

_Detected by Hiring Agent_"""

        return message

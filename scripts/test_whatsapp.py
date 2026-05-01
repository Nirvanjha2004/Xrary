"""Standalone script to test WhatsAppClient delivery."""

from __future__ import annotations

import json
import sys
from datetime import datetime

from src.clients.whatsapp_client import WhatsAppClient
from src.config import Settings


def main() -> int:
	client = WhatsAppClient(Settings)
	message = (
		"Test alert from Xrary client check. "
		f"Timestamp: {datetime.utcnow().isoformat()}Z"
	)

	try:
		message_sid = client.send_notification(message)
		print(
			json.dumps(
				{
					"status": "sent",
					"message_sid": message_sid,
					"to": Settings.twilio_whatsapp_to,
					"from": Settings.twilio_whatsapp_from,
				},
				indent=2,
			)
		)
		return 0
	except Exception as exc:
		print(
			json.dumps(
				{
					"status": "failed",
					"error": str(exc),
					"error_type": type(exc).__name__,
				},
				indent=2,
			),
			file=sys.stderr,
		)
		return 1


if __name__ == "__main__":
	raise SystemExit(main())

"""Standalone script to test XReverseClient search."""

from __future__ import annotations

import asyncio
import json
import sys

from src.clients.x_reverse_client import XReverseClient
from src.config import Settings


async def main() -> int:
	query = "SDE intern hiring"
	client = XReverseClient(Settings)

	try:
		tweets = await client.search_tweets(query=query, max_results=20)
		first_five = [tweet.model_dump(mode="json") for tweet in tweets[:5]]

		print(
			json.dumps(
				{
					"query": query,
					"total_results": len(tweets),
					"returned": len(first_five),
					"tweets": first_five,
				},
				indent=2,
			)
		)
		return 0
	except Exception as exc:
		print(
			json.dumps(
				{
					"error": str(exc),
					"error_type": type(exc).__name__,
				},
				indent=2,
			),
			file=sys.stderr,
		)
		return 1
	finally:
		await client.client.aclose()


if __name__ == "__main__":
	raise SystemExit(asyncio.run(main()))

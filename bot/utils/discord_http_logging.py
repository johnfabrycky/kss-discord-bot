"""Logging helpers for Discord HTTP rate-limit diagnostics."""

from __future__ import annotations

import logging
from typing import Any

import discord
import discord.http

logger = logging.getLogger(__name__)

_installed = False
_original_request = None


def build_rate_limit_log_context(route: Any, response: Any, exc: discord.HTTPException) -> dict[str, Any]:
    """Build structured log metadata for a Discord HTTP 429 response."""
    headers = getattr(response, "headers", {}) or {}
    return {
        "method": getattr(route, "method", None),
        "route_path": getattr(route, "path", None),
        "route_key": getattr(route, "key", None),
        "route_metadata": getattr(route, "metadata", None),
        "channel_id": str(getattr(route, "channel_id", "")) or None,
        "guild_id": str(getattr(route, "guild_id", "")) or None,
        "webhook_id": str(getattr(route, "webhook_id", "")) or None,
        "status": getattr(exc, "status", None),
        "discord_error_code": getattr(exc, "code", None),
        "retry_after": headers.get("Retry-After"),
        "x_ratelimit_bucket": headers.get("X-RateLimit-Bucket"),
        "x_ratelimit_scope": headers.get("X-RateLimit-Scope"),
        "x_ratelimit_remaining": headers.get("X-RateLimit-Remaining"),
        "x_ratelimit_reset_after": headers.get("X-RateLimit-Reset-After"),
        "x_ratelimit_global": headers.get("X-RateLimit-Global"),
    }


async def _traced_request(self, route, *, files=None, form=None, **kwargs):
    """Wrap Discord HTTP requests so 429 responses log their route details."""
    try:
        return await _original_request(self, route, files=files, form=form, **kwargs)
    except discord.HTTPException as exc:
        if exc.status == 429:
            logger.warning(
                "Discord HTTP rate limit hit",
                extra=build_rate_limit_log_context(route, getattr(exc, "response", None), exc),
            )
        raise


def install_discord_http_rate_limit_logging():
    """Install the Discord HTTP 429 logging wrapper once per process."""
    global _installed, _original_request

    if _installed:
        return

    _original_request = discord.http.HTTPClient.request
    discord.http.HTTPClient.request = _traced_request
    _installed = True

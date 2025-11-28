#!/usr/bin/env python3
"""
Bulk-import LinguaLeo words from a JSON file.

Powered by the reusable `lingualeo` module so other integrations (e.g., a
Telegram bot) can share the same client logic.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

from lingualeo import LinguaLeoClient, LinguaLeoError
from lingualeo.client import COOKIE_CACHE_DEFAULT, describe_request_error

# Load environment variables from .env file
load_dotenv()


def load_words(json_path: Path) -> List[Dict[str, Optional[str]]]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("words", [])
    if not isinstance(data, list):
        raise ValueError("JSON must be an array of {'word','translation'} objects")

    normalized = []
    for idx, entry in enumerate(data, 1):
        if not isinstance(entry, dict):
            raise ValueError(f"Entry #{idx} is not an object: {entry!r}")
        word = entry.get("word")
        translation = entry.get("translation")
        if not word:
            raise ValueError(f"Entry #{idx} must include 'word'")
        normalized_translation = None
        if translation is not None:
            normalized_translation = str(translation).strip() or None
        normalized.append({"word": str(word).strip(), "translation": normalized_translation})
    return normalized


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import LinguaLeo words from JSON")
    parser.add_argument("json_file", type=Path, help="Path to the input JSON file")
    parser.add_argument("--cookie", help="LinguaLeo cookie string; defaults to LINGUALEO_COOKIE env")
    parser.add_argument("--word-set-id", type=int, default=1, help="Target LinguaLeo word set ID")
    parser.add_argument(
        "--cookie-file",
        type=Path,
        default=COOKIE_CACHE_DEFAULT,
        help="Path to cache LinguaLeo cookies",
    )
    parser.add_argument("--email", help="LinguaLeo login email (or set LINGUALEO_EMAIL env var)")
    parser.add_argument("--password", help="LinguaLeo password (or set LINGUALEO_PASSWORD env var)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cookie = args.cookie or os.getenv("LINGUALEO_COOKIE")
    email = args.email or os.getenv("LINGUALEO_EMAIL")
    password = args.password or os.getenv("LINGUALEO_PASSWORD")

    try:
        words = load_words(args.json_file)
    except (OSError, ValueError) as exc:
        print(f"Failed to load {args.json_file}: {exc}", file=sys.stderr)
        return 1

    try:
        client = LinguaLeoClient(
            email=email,
            password=password,
            cookie_string=cookie,
            cookie_file=args.cookie_file,
        )
        client.ensure_authenticated()
    except (LinguaLeoError, requests.RequestException) as exc:
        print(f"Failed to prepare LinguaLeo client: {exc}", file=sys.stderr)
        return 1

    for entry in words:
        word = entry["word"]
        desired_translation = entry["translation"]
        target_desc = desired_translation or "(auto-select)"
        print(f"Processing '{word}' → '{target_desc}'")

        try:
            result = client.add_word_with_hint(
                word,
                translation_hint=desired_translation,
                word_set_id=args.word_set_id,
            )
        except LinguaLeoError as exc:
            print(f"  ! {exc}", file=sys.stderr)
            continue
        except requests.RequestException as exc:
            print(f"  ! API error: {describe_request_error(exc)}", file=sys.stderr)
            continue

        translation_text = result.translation_used.get("value") or result.translation_used.get("tr")
        if result.auto_selected:
            print(f"  · No translation provided, using suggestion '{translation_text}'")
        status = result.response.get("status", "unknown")
        print(f"  ✔ Added (status={status})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

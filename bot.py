#!/usr/bin/env python3
"""
Telegram bot that adds words to LinguaLeo using the shared client module.

Usage:
    export TELEGRAM_TOKEN=...        # Bot token from @BotFather (required)
    export LINGUALEO_EMAIL=...       # Optional, defaults to built-in values
    export LINGUALEO_PASSWORD=...
    export LINGUALEO_COOKIE_FILE=...
    python bot.py
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Tuple

import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from lingualeo import LinguaLeoClient, LinguaLeoError
from lingualeo.client import COOKIE_CACHE_DEFAULT, describe_request_error

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


def build_client() -> LinguaLeoClient:
    email = os.getenv("LINGUALEO_EMAIL")
    password = os.getenv("LINGUALEO_PASSWORD")
    cookie_file_env = os.getenv("LINGUALEO_COOKIE_FILE")
    cookie_file = COOKIE_CACHE_DEFAULT
    if cookie_file_env:
        cookie_file = COOKIE_CACHE_DEFAULT.parent / cookie_file_env

    cookie_string = os.getenv("LINGUALEO_COOKIE")

    client = LinguaLeoClient(
        email=email,
        password=password,
        cookie_string=cookie_string,
        cookie_file=cookie_file,
    )
    client.ensure_authenticated()
    return client


def parse_message_text(text: str) -> Tuple[str, Optional[str]]:
    text = text.strip()
    if "—" in text:
        word, hint = text.split("—", 1)
        return word.strip(), hint.strip() or None
    if "-" in text:
        word, hint = text.split("-", 1)
        return word.strip(), hint.strip() or None
    return text, None


def parse_bulk_words(text: str) -> list[Tuple[str, Optional[str]]]:
    """Parse multiple words from a multi-line message."""
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    return [parse_message_text(line) for line in lines]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Отправь испанское слово (и перевод, если хочешь), "
        "а я добавлю его в LinguaLeo.\n\n"
        "Для массового импорта отправь несколько слов, каждое на новой строке:\n"
        "palabra1 — перевод1\n"
        "palabra2 — перевод2\n"
        "palabra3"
    )


async def process_single_word(
    client: LinguaLeoClient, word: str, hint: Optional[str]
) -> Tuple[bool, str, Optional[str], bool]:
    """Process a single word and return (success, word, translation_text, auto_selected)."""
    try:
        result = client.add_word_with_hint(word, hint)
        translation_text = result.translation_used.get("value") or result.translation_used.get("tr")
        return True, word, translation_text, result.auto_selected
    except (LinguaLeoError, requests.RequestException) as exc:
        logger.exception(f"Failed to add word '{word}': {exc}")
        return False, word, None, False


async def add_word_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    if message.from_user.id != 544604253:
        print("Ignoring message from non-authorized user")
        return

    client: LinguaLeoClient = context.application.bot_data["lingualeo_client"]
    text = message.text.strip()

    # Check if this is a bulk import (multiple lines)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) > 1:
        # Bulk import mode
        words_data = parse_bulk_words(text)
        if not words_data:
            await message.reply_text("Пожалуйста, отправь слова (каждое на новой строке).")
            return

        # Process all words
        results = []
        for word, hint in words_data:
            if not word:
                continue
            success, processed_word, translation, _ = await process_single_word(client, word, hint)
            results.append((success, processed_word, translation))

        # Build summary
        successful = [r for r in results if r[0]]
        failed = [r for r in results if not r[0]]

        summary_parts = [f"Обработано: {len(successful)}/{len(results)}"]
        if successful:
            summary_parts.append("\n<b>Добавлено:</b>")
            for success, word, trans in successful:
                summary_parts.append(f"  • {word} → {trans}")
        if failed:
            summary_parts.append(f"\n<b>Ошибки ({len(failed)}):</b>")
            for success, word, trans in failed:
                summary_parts.append(f"  • {word}")

        await message.reply_html("\n".join(summary_parts), disable_web_page_preview=True)
        return

    # Single word mode
    word, hint = parse_message_text(text)
    if not word:
        await message.reply_text("Пожалуйста, отправь слово.")
        return

    success, processed_word, translation_text, auto_selected = await process_single_word(client, word, hint)
    if not success:
        await message.reply_text(f"Не удалось добавить слово '{word}'.")
        return

    extra = ""
    if auto_selected:
        extra = "\n(Перевод не указан, выбран первый вариант от LinguaLeo)"

    await message.reply_html(
        f"<b>{processed_word}</b> → {translation_text}\nДобавлено!{extra}",
        disable_web_page_preview=True,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_TOKEN env variable is required.")

    try:
        client = build_client()
    except LinguaLeoError as exc:
        raise SystemExit(f"Failed to initialize LinguaLeo client: {exc}")

    application = Application.builder().token(token).build()
    application.bot_data["lingualeo_client"] = client

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_word_handler))

    application.run_polling()


if __name__ == "__main__":
    main()


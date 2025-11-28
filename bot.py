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
) -> Tuple[bool, str, Optional[str], bool, Optional[str]]:
    """
    Process a single word and return (success, word, translation_text, auto_selected, status_message).
    status_message: None if added, "exists" if already exists, "error" if failed.
    """
    logger.info(f"[BOT] Processing word: '{word}' (hint: {hint})")
    try:
        logger.info(f"[BOT] Calling add_word_with_hint for '{word}'")
        result = client.add_word_with_hint(word, hint)
        logger.info(f"[BOT] Successfully added word '{word}'")
        translation_text = result.translation_used.get("value") or result.translation_used.get("tr")
        return True, word, translation_text, result.auto_selected, None
    except LinguaLeoError as exc:
        error_msg = str(exc)
        logger.info(f"[BOT] LinguaLeoError for '{word}': {error_msg}")
        if "already exists" in error_msg.lower():
            logger.info(f"[BOT] ✓ Word '{word}' already exists in dictionary - preventing duplicate")
            return False, word, None, False, "exists"
        logger.exception(f"[BOT] Failed to add word '{word}': {exc}")
        return False, word, None, False, "error"
    except requests.RequestException as exc:
        logger.exception(f"[BOT] RequestException for word '{word}': {exc}")
        return False, word, None, False, "error"
    except Exception as exc:
        logger.exception(f"[BOT] Unexpected exception for word '{word}': {exc}")
        return False, word, None, False, "error"


async def add_word_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    if message.from_user.id != 544604253:
        logger.debug("Ignoring message from non-authorized user")
        return

    client: LinguaLeoClient = context.application.bot_data["lingualeo_client"]
    text = message.text.strip()
    logger.info(f"[BOT] Received message from user {message.from_user.id}: '{text[:50]}...'")

    # Check if this is a bulk import (multiple lines)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) > 1:
        # Bulk import mode
        words_data = parse_bulk_words(text)
        if not words_data:
            await message.reply_text("Пожалуйста, отправь слова (каждое на новой строке).")
            return

        # Process all words
        logger.info(f"[BOT] Bulk import mode - processing {len(words_data)} words")
        results = []
        for idx, (word, hint) in enumerate(words_data):
            if not word:
                continue
            logger.info(f"[BOT] Processing word {idx+1}/{len(words_data)}: '{word}'")
            success, processed_word, translation, _, status = await process_single_word(client, word, hint)
            logger.info(f"[BOT] Word {idx+1} result: success={success}, status={status}")
            results.append((success, processed_word, translation, status))

        # Build summary
        successful = [r for r in results if r[0]]
        already_exists = [r for r in results if not r[0] and r[3] == "exists"]
        failed = [r for r in results if not r[0] and r[3] == "error"]

        summary_parts = [f"Обработано: {len(successful)}/{len(results)}"]
        if successful:
            summary_parts.append("\n<b>Добавлено:</b>")
            for success, word, trans, _ in successful:
                summary_parts.append(f"  • {word} → {trans}")
        if already_exists:
            summary_parts.append(f"\n<b>Уже есть ({len(already_exists)}):</b>")
            for success, word, trans, _ in already_exists:
                summary_parts.append(f"  • {word}")
        if failed:
            summary_parts.append(f"\n<b>Ошибки ({len(failed)}):</b>")
            for success, word, trans, _ in failed:
                summary_parts.append(f"  • {word}")

        await message.reply_html("\n".join(summary_parts), disable_web_page_preview=True)
        return

    # Single word mode
    word, hint = parse_message_text(text)
    logger.info(f"[BOT] Single word mode - parsed: word='{word}', hint='{hint}'")
    if not word:
        await message.reply_text("Пожалуйста, отправь слово.")
        return

    logger.info(f"[BOT] Starting to process single word: '{word}'")
    success, processed_word, translation_text, auto_selected, status = await process_single_word(client, word, hint)
    logger.info(f"[BOT] Process result: success={success}, status={status}, word='{processed_word}'")
    
    if not success:
        if status == "exists":
            logger.info(f"[BOT] Sending 'already exists' message for '{word}'")
            await message.reply_text(f"Слово '<b>{word}</b>' уже есть в словаре.", parse_mode="HTML")
        else:
            logger.warning(f"[BOT] Sending error message for '{word}' (status: {status})")
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
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )
    # Also set logging level for lingualeo.client
    logging.getLogger('lingualeo.client').setLevel(logging.INFO)
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


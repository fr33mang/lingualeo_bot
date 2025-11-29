import difflib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import httpx

logger = logging.getLogger(__name__)

GET_TRANSLATES_URL = "https://api.lingualeo.com/getTranslates"
GET_WORDS_URL = "https://api.lingualeo.com/GetWords"
SET_WORDS_URL = "https://api.lingualeo.com/SetWords"
AUTH_URL = "https://lingualeo.com/api/auth"
COOKIE_CACHE_DEFAULT = Path("lingualeo_cookies.json")

BASE_HEADERS = {
    "accept": "application/json",
    "accept-language": "en-US,en;q=0.9,ru-RU;q=0.8,ru;q=0.7",
    "content-type": "application/json",
    "origin": "https://lingualeo.com",
    "referer": "https://lingualeo.com/ru/dictionary/vocabulary/my",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
}

AUTH_HEADERS = {
    "accept": "application/json",
    "accept-language": "en-US,en;q=0.9,ru-RU;q=0.8,ru;q=0.7",
    "cache-control": "no-cache",
    "content-type": "application/json",
    "origin": "https://lingualeo.com",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "referer": "https://lingualeo.com/en",
    "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
}


class LinguaLeoError(RuntimeError):
    """Raised when a LinguaLeo operation cannot be completed."""


def parse_cookie_string(raw: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookies[name.strip()] = value.strip()
    return cookies


def _load_cookie_file(path: Path) -> dict[str, str]:
    cookies: dict[str, str] = {}
    if not path or not path.exists():
        return cookies
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return cookies
    if isinstance(data, dict):
        cookies.update(data)
    return cookies


def _save_cookie_file(path: Path, cookies: dict[str, str]) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cookies, indent=2, ensure_ascii=False), encoding="utf-8")


def describe_request_error(exc: httpx.HTTPStatusError | httpx.RequestError) -> str:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        return f"{exc} → {exc.response.text}"
    return str(exc)


def select_best_translation(
    candidates: Iterable[dict[str, Any]],
    desired: str | None,
    threshold: float = 0.8,
) -> dict[str, Any] | None:
    """
    Select best matching translation from candidates.

    Args:
        candidates: List of translation candidates
        desired: Desired translation text
        threshold: Minimum similarity score (0.0-1.0) to consider a match. Default 0.8.

    Returns:
        Best matching candidate if similarity >= threshold, None otherwise
    """
    if not desired:
        return None
    desired_lower = desired.lower()
    best: dict[str, Any] | None = None
    best_score = -1.0
    for candidate in candidates:
        text = str(candidate.get("value") or candidate.get("tr") or "").lower()
        if not text:
            continue
        score = difflib.SequenceMatcher(a=desired_lower, b=text).ratio()
        if score > best_score:
            best = candidate
            best_score = score

    # Only return if score meets threshold
    if best_score >= threshold:
        logger.debug(f"Found matching translation with score {best_score:.2f}: {best}")
        return best

    logger.debug(f"Best match score {best_score:.2f} below threshold {threshold}, no match found")
    return None


def extract_existing_translations(word_data: dict[str, Any]) -> list[str]:
    """Extract all existing translations from word data."""
    translations = []

    # Get from combinedTranslation field (semicolon-separated)
    combined = word_data.get("combinedTranslation", "")
    if combined:
        translations.extend([t.strip() for t in combined.split(";") if t.strip()])

    # Get from translations array if available
    trans_list = word_data.get("translations") or []
    for trans in trans_list:
        text = trans.get("value") or trans.get("tr") or ""
        if text and text.strip():
            translations.append(text.strip())

    # Remove duplicates while preserving order
    seen = set()
    unique_translations = []
    for t in translations:
        t_lower = t.lower()
        if t_lower not in seen:
            seen.add(t_lower)
            unique_translations.append(t)

    return unique_translations


def translation_exists(existing_translations: list[str], hint: str) -> bool:
    """Check if a translation already exists in the list (case-insensitive)."""
    hint_lower = hint.lower().strip()
    return any(t.lower().strip() == hint_lower for t in existing_translations)


def _should_reauth(status_code: int | None) -> bool:
    return status_code in {400, 401, 403}


@dataclass
class AddWordResult:
    response: dict[str, Any]
    translation_used: dict[str, Any]
    auto_selected: bool


class LinguaLeoClient:
    def __init__(
        self,
        *,
        email: str | None = None,
        password: str | None = None,
        cookie_string: str | None = None,
        cookie_file: Path = COOKIE_CACHE_DEFAULT,
    ):
        if not email or not password:
            raise LinguaLeoError(
                "LinguaLeo email and password are required. "
                "Set LINGUALEO_EMAIL and LINGUALEO_PASSWORD environment variables."
            )

        self.client: httpx.AsyncClient | None = None
        self.headers = BASE_HEADERS.copy()
        self.auth_headers = AUTH_HEADERS.copy()
        self.cookie_file = Path(cookie_file) if cookie_file else COOKIE_CACHE_DEFAULT
        self.email = email
        self.password = password
        self._cookies: dict[str, str] = {}

        if cookie_string:
            self._cookies.update(parse_cookie_string(cookie_string))
        self._cookies.update(_load_cookie_file(self.cookie_file))

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def _ensure_client(self) -> None:
        """Ensure the HTTP client is initialized."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                cookies=self._cookies,
                timeout=15.0,
                follow_redirects=True,
            )
            # Ensure cookies are synced
            self._sync_cookies_to_client()

    async def ensure_authenticated(self) -> None:
        await self._ensure_client()
        # Check if we have any meaningful cookies (not just empty dict)
        # If no cookies or cookies seem invalid, login
        logger.debug(f"[CLIENT] ensure_authenticated: cookies count={len(self._cookies)}")
        if not self._cookies:
            logger.info("[CLIENT] No cookies found, logging in...")
            await self.login()
        else:
            # Sync cookies to client in case they were updated
            logger.debug(f"[CLIENT] Cookies found, syncing to client: {list(self._cookies.keys())}")
            self._sync_cookies_to_client()

    async def login(self) -> None:
        await self._ensure_client()
        if not self.email or not self.password:
            raise LinguaLeoError("Missing LinguaLeo credentials for login.")
        payload = {"type": "mixed", "credentials": {"email": self.email, "password": self.password}}
        response = await self.client.post(AUTH_URL, json=payload, headers=self.auth_headers)
        response.raise_for_status()
        # Update cookies from response - httpx stores cookies in client.cookies
        self._sync_cookies_from_client()
        _save_cookie_file(self.cookie_file, self._cookies)

    def _sync_cookies_from_client(self) -> None:
        """Sync cookies from httpx client to internal _cookies dict."""
        if self.client:
            # httpx.Cookies - iterate and extract values
            # Cookies can be accessed directly as dict-like or via .get()
            for name in self.client.cookies:
                cookie_value = self.client.cookies.get(name)
                if cookie_value:
                    # If it's a Cookie object, get the value, otherwise it's already a string
                    if hasattr(cookie_value, "value"):
                        self._cookies[name] = cookie_value.value
                    else:
                        self._cookies[name] = str(cookie_value)

    def _sync_cookies_to_client(self) -> None:
        """Sync cookies from internal _cookies dict to httpx client."""
        if self.client:
            # Clear and update client cookies
            self.client.cookies.clear()
            self.client.cookies.update(self._cookies)

    async def _call_get_translates(self, word: str) -> dict[str, Any]:
        await self._ensure_client()
        payload = {"apiVersion": "1.0.1", "text": word, "iDs": []}
        response = await self.client.post(GET_TRANSLATES_URL, json=payload, headers=self.headers)
        response.raise_for_status()
        # Sync cookies after request
        self._sync_cookies_from_client()
        return response.json()

    async def _call_get_words(self, word: str, word_set_id: int = 1) -> dict[str, Any]:
        """Search for a word in the dictionary."""
        # Generate simple tracking IDs (similar to what browser sends)
        timestamp = int(time.time() * 1000)
        ids = [{"y": str(timestamp), "g": f"131447161.{int(time.time())}"}]

        logger.debug(f"[API] Calling GetWords with word='{word}', wordSetId={word_set_id}")

        payload = {
            "apiVersion": "1.0.1",
            "attrList": {
                "association": "as",
                "combinedTranslation": "trc",
                "created": "cd",
                "id": "id",
                "learningStatus": "ls",
                "listWordSets": "listWordSets",
                "origin": "wo",
                "picture": "pic",
                "progress": "pi",
                "pronunciation": "pron",
                "relatedWords": "rw",
                "speechPartId": "pid",
                "trainings": "trainings",
                "transcription": "scr",
                "translations": "trs",
                "wordLemmaId": "lid",
                "wordLemmaValue": "lwd",
                "wordSets": "ws",
                "wordType": "wt",
                "wordValue": "wd",
            },
            "category": "",
            "dateGroup": "new",
            "mode": "basic",
            "perPage": 30,
            "status": "all",
            "wordSetId": word_set_id,
            "offset": None,
            "search": word,
            "training": None,
            "iDs": ids,
        }
        # Use headers similar to the example, but with same-site referer
        headers = self.headers.copy()
        headers.update(
            {
                "cache-control": "no-cache",
                "pragma": "no-cache",
                "priority": "u=1, i",
                "sec-fetch-dest": "empty",
            }
        )
        logger.debug(f"[API] GetWords payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        await self._ensure_client()
        response = await self.client.post(GET_WORDS_URL, json=payload, headers=headers)
        response.raise_for_status()
        # Sync cookies after request
        self._sync_cookies_from_client()
        result = response.json()
        logger.debug(
            f"[API] GetWords response status: {result.get('status')}, data groups: {len(result.get('data', []))}"
        )
        return result

    async def _call_set_words(
        self,
        word: str,
        translation: dict[str, Any],
        word_set_id: int,
    ) -> dict[str, Any]:
        translation_block = {
            "id": translation["id"],
            "tr": translation.get("value") or translation.get("tr"),
            "main": translation.get("main", 1),
            "selected": translation.get("selected", 1),
        }
        payload = {
            "apiVersion": "1.0.1",
            "op": "actionWithWords {action: add}",
            "data": [
                {
                    "action": "add",
                    "mode": "0",
                    "wordIds": [],
                    "valueList": {
                        "wordSetId": word_set_id,
                        "wordValue": word,
                        "translation": translation_block,
                    },
                }
            ],
            "userData": {"nativeLanguage": "lang_id_src"},
            "iDs": [],
        }
        await self._ensure_client()
        response = await self.client.post(SET_WORDS_URL, json=payload, headers=self.headers)
        response.raise_for_status()
        # Sync cookies after request
        self._sync_cookies_from_client()
        return response.json()

    async def _with_reauth(self, func, *args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if not _should_reauth(status):
                raise
            await self.login()
            return await func(*args, **kwargs)

    async def get_translates(self, word: str) -> dict[str, Any]:
        await self.ensure_authenticated()
        return await self._with_reauth(self._call_get_translates, word)

    async def get_word_data(self, word: str, word_set_id: int = 1) -> dict[str, Any] | None:
        """Get word data if it exists in the dictionary, or None if not found."""
        await self.ensure_authenticated()
        try:
            logger.info(f"Checking if word '{word}' exists in word_set_id={word_set_id}")
            response = await self._with_reauth(self._call_get_words, word, word_set_id)

            # Debug: log the response structure
            logger.info(f"GetWords API response status: {response.get('status')}")
            logger.debug(f"GetWords API full response: {json.dumps(response, indent=2, ensure_ascii=False)}")

            # Check if word exists in the response
            if response.get("status") != "ok":
                logger.warning(f"GetWords API returned non-ok status: {response.get('status')}")
                return None

            data = response.get("data", [])
            logger.info(f"Found {len(data)} data groups in response")

            # Debug: log full response structure when no words found
            if not data:
                logger.info(f"No data groups found, word '{word}' does not exist")
                logger.debug(f"Full API response: {json.dumps(response, indent=2, ensure_ascii=False)}")
                return None

            # Search through all groups and words
            word_lower = word.lower().strip()
            logger.info(f"Searching for word (lowercase): '{word_lower}'")

            for group_idx, group in enumerate(data):
                words = group.get("words") or []
                group_name = group.get("groupName", "unknown")
                logger.info(f"Group {group_idx} ({group_name}) has {len(words)} words")

                # Debug: if group has 0 words, log the full group structure
                if len(words) == 0:
                    logger.warning(f"⚠️ Group {group_idx} ({group_name}) has 0 words!")
                    logger.warning(f"Group structure: {json.dumps(group, indent=2, ensure_ascii=False)}")
                    logger.warning(f"Full API response: {json.dumps(response, indent=2, ensure_ascii=False)}")
                    logger.warning(f"Search term: '{word}', wordSetId: {word_set_id}")

                for word_idx, word_data in enumerate(words):
                    word_value_raw = word_data.get("wordValue", "")
                    word_value = word_value_raw.lower().strip()

                    # Also check wordLemmaValue if present
                    word_lemma_raw = word_data.get("wordLemmaValue", "")
                    word_lemma = word_lemma_raw.lower().strip() if word_lemma_raw else None

                    logger.info(f"  Word {word_idx}: wordValue='{word_value_raw}' (normalized: '{word_value}')")
                    if word_lemma:
                        logger.info(f"            wordLemmaValue='{word_lemma_raw}' (normalized: '{word_lemma}')")

                    # Match against either wordValue or wordLemmaValue
                    if word_value == word_lower or (word_lemma and word_lemma == word_lower):
                        matched_field = "wordValue" if word_value == word_lower else "wordLemmaValue"
                        logger.info(
                            f"✓ Word '{word}' FOUND in dictionary (matched '{word_value_raw}' via {matched_field})"
                        )
                        return word_data

            logger.info(f"✗ Word '{word}' NOT found in any groups")
            return None
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.error(f"Request error while checking if word '{word}' exists: {exc}")
            if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                logger.error(f"Response status: {exc.response.status_code}")
                logger.error(f"Response text: {exc.response.text[:500]}")
            # Return None but log the error so we can debug
            return None
        except LinguaLeoError as exc:
            logger.error(f"LinguaLeo error while checking if word '{word}' exists: {exc}")
            return None
        except Exception as exc:
            logger.error(f"Unexpected error while checking if word '{word}' exists: {exc}", exc_info=True)
            return None

    async def word_exists(self, word: str, word_set_id: int = 1) -> bool:
        """Check if a word already exists in the dictionary."""
        word_data = await self.get_word_data(word, word_set_id)
        return word_data is not None

    async def add_word(
        self,
        word: str,
        translation: dict[str, Any],
        word_set_id: int = 1,
    ) -> dict[str, Any]:
        await self.ensure_authenticated()
        return await self._with_reauth(self._call_set_words, word, translation, word_set_id)

    async def add_word_with_hint(
        self,
        word: str,
        translation_hint: str | None,
        word_set_id: int = 1,
    ) -> AddWordResult:
        """
        Add a word with optional translation hint.

        Logic:
        - If word doesn't exist + no hint: take first suggestion from Lingualeo
        - If word exists + (no hint OR hint matches existing): raise error (already exists)
        - If word exists + hint provided + hint not in existing: add new translation
        - If hint not in Lingualeo's suggestions: add as custom translation
        """
        logger.info(f"[CLIENT] add_word_with_hint called for word='{word}', hint='{translation_hint}'")

        # Check if word already exists
        word_data = await self.get_word_data(word, word_set_id)

        if word_data:
            logger.info(f"[CLIENT] Word '{word}' already exists in dictionary")
            existing_translations = extract_existing_translations(word_data)
            logger.info(f"[CLIENT] Existing translations: {existing_translations}")

            # If no hint provided or hint matches existing translation
            if not translation_hint:
                logger.warning(f"[CLIENT] Word '{word}' exists and no hint provided")
                raise LinguaLeoError(f"Word '{word}' already exists in dictionary")

            if translation_exists(existing_translations, translation_hint):
                logger.warning(f"[CLIENT] Word '{word}' already has translation '{translation_hint}'")
                raise LinguaLeoError(f"Word '{word}' with translation '{translation_hint}' already exists")

            # Word exists but translation is new - proceed to add new translation
            logger.info(f"[CLIENT] Adding new translation '{translation_hint}' to existing word '{word}'")
        else:
            logger.info(f"[CLIENT] Word '{word}' does not exist - will add new word")

        # Get translation candidates from Lingualeo
        translate_payload = await self.get_translates(word)
        candidates = translate_payload.get("translate") or translate_payload.get("translations") or []
        logger.info(f"[CLIENT] Got {len(candidates)} translation candidates from Lingualeo")

        match = None
        auto_selected = False

        if translation_hint:
            # Try to find matching translation in candidates
            match = select_best_translation(candidates, translation_hint)

            if not match:
                # Custom translation - not in Lingualeo's suggestions
                logger.info(
                    f"[CLIENT] Translation '{translation_hint}' not found in candidates, creating custom translation"
                )

                # Create a custom translation object
                # We need at least an ID to make the API happy
                # Use a high ID that's unlikely to conflict, or derive from hint
                custom_id = hash(translation_hint) % (10**9)  # Simple hash-based ID
                if custom_id < 0:
                    custom_id = -custom_id

                match = {
                    "id": custom_id,
                    "value": translation_hint,
                    "tr": translation_hint,
                    "main": 1,
                    "selected": 1,
                }
                logger.info(f"[CLIENT] Created custom translation: {match}")
        else:
            # No hint - use first candidate if available
            if candidates:
                match = candidates[0]
                auto_selected = True
                logger.info(f"[CLIENT] No hint provided, auto-selected first candidate")
            else:
                raise LinguaLeoError("No translation candidates returned by LinguaLeo and no hint provided.")

        if not match:
            raise LinguaLeoError("Could not determine translation to add.")

        logger.info(f"[CLIENT] Adding word '{word}' with translation: {match}")
        response = await self.add_word(word, match, word_set_id)

        # Update cookies from client after request
        self._sync_cookies_from_client()
        _save_cookie_file(self.cookie_file, self._cookies)

        return AddWordResult(response=response, translation_used=match, auto_selected=auto_selected)

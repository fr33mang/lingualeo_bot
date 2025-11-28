from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

GET_TRANSLATES_URL = "https://api.lingualeo.com/getTranslates"
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


def parse_cookie_string(raw: str) -> Dict[str, str]:
    cookies: Dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookies[name.strip()] = value.strip()
    return cookies


def _load_cookie_file(path: Path) -> requests.cookies.RequestsCookieJar:
    jar = requests.cookies.RequestsCookieJar()
    if not path or not path.exists():
        return jar
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return jar
    if isinstance(data, dict):
        for name, value in data.items():
            jar.set(name, value)
    return jar


def _save_cookie_file(path: Path, jar: requests.cookies.RequestsCookieJar) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jar.get_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def describe_request_error(exc: requests.RequestException) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return f"{exc} → {exc.response.text}"
    return str(exc)


def select_best_translation(
    candidates: Iterable[Dict[str, Any]],
    desired: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not desired:
        return None
    desired_lower = desired.lower()
    best: Optional[Dict[str, Any]] = None
    best_score = -1.0
    for candidate in candidates:
        text = str(candidate.get("value") or candidate.get("tr") or "").lower()
        if not text:
            continue
        score = difflib.SequenceMatcher(a=desired_lower, b=text).ratio()
        if score > best_score:
            best = candidate
            best_score = score
    return best


def _should_reauth(status_code: Optional[int]) -> bool:
    return status_code in {400, 401, 403}


@dataclass
class AddWordResult:
    response: Dict[str, Any]
    translation_used: Dict[str, Any]
    auto_selected: bool


class LinguaLeoClient:
    def __init__(
        self,
        *,
        email: Optional[str] = None,
        password: Optional[str] = None,
        cookie_string: Optional[str] = None,
        cookie_file: Path = COOKIE_CACHE_DEFAULT,
    ):
        if not email or not password:
            raise LinguaLeoError(
                "LinguaLeo email and password are required. "
                "Set LINGUALEO_EMAIL and LINGUALEO_PASSWORD environment variables."
            )

        self.session = requests.Session()
        self.headers = BASE_HEADERS.copy()
        self.auth_headers = AUTH_HEADERS.copy()
        self.cookie_file = Path(cookie_file) if cookie_file else COOKIE_CACHE_DEFAULT
        self.email = email
        self.password = password

        if cookie_string:
            self.session.cookies.update(parse_cookie_string(cookie_string))
        self.session.cookies.update(_load_cookie_file(self.cookie_file))

    def ensure_authenticated(self) -> None:
        if not self.session.cookies.get_dict():
            self.login()

    def login(self) -> None:
        if not self.email or not self.password:
            raise LinguaLeoError("Missing LinguaLeo credentials for login.")
        payload = {"type": "mixed", "credentials": {"email": self.email, "password": self.password}}
        response = self.session.post(AUTH_URL, json=payload, headers=self.auth_headers, timeout=15)
        response.raise_for_status()
        _save_cookie_file(self.cookie_file, self.session.cookies)

    def _call_get_translates(self, word: str) -> Dict[str, Any]:
        payload = {"apiVersion": "1.0.1", "text": word, "iDs": []}
        response = self.session.post(GET_TRANSLATES_URL, json=payload, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def _call_set_words(self, word: str, translation: Dict[str, Any], word_set_id: int) -> Dict[str, Any]:
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
        response = self.session.post(SET_WORDS_URL, json=payload, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def _with_reauth(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if not _should_reauth(status):
                raise
            self.login()
            return func(*args, **kwargs)

    def get_translates(self, word: str) -> Dict[str, Any]:
        self.ensure_authenticated()
        return self._with_reauth(self._call_get_translates, word)

    def add_word(self, word: str, translation: Dict[str, Any], word_set_id: int = 1) -> Dict[str, Any]:
        self.ensure_authenticated()
        return self._with_reauth(self._call_set_words, word, translation, word_set_id)

    def add_word_with_hint(
        self,
        word: str,
        translation_hint: Optional[str],
        word_set_id: int = 1,
    ) -> AddWordResult:
        translate_payload = self.get_translates(word)
        candidates = translate_payload.get("translate") or translate_payload.get("translations") or []
        match = select_best_translation(candidates, translation_hint)
        auto_selected = False
        if not match:
            if translation_hint is None and candidates:
                match = candidates[0]
                auto_selected = True
            else:
                if not candidates:
                    raise LinguaLeoError("No translation candidates returned by LinguaLeo.")
                raise LinguaLeoError("Could not match translation to any candidate.")

        response = self.add_word(word, match, word_set_id)
        _save_cookie_file(self.cookie_file, self.session.cookies)
        return AddWordResult(response=response, translation_used=match, auto_selected=auto_selected)


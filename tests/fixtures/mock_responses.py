"""Mock API response data for LinguaLeo API endpoints.

All data is sanitized and contains no personal information.
"""


def mock_auth_response() -> dict:
    """Mock successful authentication response."""
    return {
        "status": "ok",
        "user": {
            "id": 12345,
            "email": "test@example.com",
        },
    }


def mock_auth_cookies() -> dict[str, str]:
    """Mock authentication cookies."""
    return {
        "auth_token": "mock_auth_token_12345",
        "session_id": "mock_session_abc123",
        "user_id": "12345",
    }


def mock_get_translates_response() -> dict:
    """Mock GetTranslates API response with multiple translation candidates."""
    return {
        "translate": [
            {
                "id": 1001,
                "value": "перевод",
                "tr": "перевод",
                "main": 1,
                "selected": 0,
            },
            {
                "id": 1002,
                "value": "толкование",
                "tr": "толкование",
                "main": 0,
                "selected": 0,
            },
            {
                "id": 1003,
                "value": "значение",
                "tr": "значение",
                "main": 0,
                "selected": 0,
            },
        ],
    }


def mock_get_translates_response_empty() -> dict:
    """Mock GetTranslates API response with no translations."""
    return {
        "translate": [],
    }


def mock_get_words_response_word_exists(word: str = "palabra") -> dict:
    """Mock GetWords API response when word exists in dictionary."""
    return {
        "status": "ok",
        "data": [
            {
                "groupName": "search",
                "groupCount": 1,
                "words": [
                    {
                        "id": 2001,
                        "wordValue": word,
                        "wordLemmaValue": word,
                        "combinedTranslation": "слово",
                        "transcription": None,
                        "pronunciation": "https://audiocdn.lingualeo.com/v2/mock_audio.mp3",
                        "wordSets": [{"id": 1, "name": "Мой словарь", "countWords": 1}],
                        "created": 1234567890,
                        "learningStatus": 0,
                        "progress": 0,
                        "wordType": 1,
                    },
                ],
            },
        ],
        "listWordSets": [
            {"id": 1, "name": "Мой словарь"},
            {"id": 2, "name": "Слова из материалов"},
        ],
        "wordSet": {
            "id": 1,
            "name": "Мой словарь",
            "countWords": 1,
            "isGlobal": False,
        },
        "trainings": [],
    }


def mock_get_words_response_word_not_found() -> dict:
    """Mock GetWords API response when word doesn't exist."""
    return {
        "status": "ok",
        "data": [],
        "listWordSets": [
            {"id": 1, "name": "Мой словарь"},
        ],
        "wordSet": {
            "id": 1,
            "name": "Мой словарь",
            "countWords": 0,
            "isGlobal": False,
        },
        "trainings": [],
    }


def mock_get_words_response_empty_group() -> dict:
    """Mock GetWords API response with empty word group."""
    return {
        "status": "ok",
        "data": [
            {
                "groupName": "search",
                "groupCount": 0,
                "words": [],
            },
        ],
        "listWordSets": [
            {"id": 1, "name": "Мой словарь"},
        ],
        "wordSet": {
            "id": 1,
            "name": "Мой словарь",
            "countWords": 0,
            "isGlobal": False,
        },
        "trainings": [],
    }


def mock_get_words_response_multiple_words() -> dict:
    """Mock GetWords API response with multiple words in dictionary."""
    return {
        "status": "ok",
        "data": [
            {
                "groupName": "search",
                "groupCount": 2,
                "words": [
                    {
                        "id": 2001,
                        "wordValue": "palabra",
                        "wordLemmaValue": "palabra",
                        "combinedTranslation": "слово",
                        "transcription": None,
                        "pronunciation": "https://audiocdn.lingualeo.com/v2/mock1.mp3",
                        "wordSets": [{"id": 1, "name": "Мой словарь"}],
                        "created": 1234567890,
                        "learningStatus": 0,
                        "progress": 0,
                    },
                    {
                        "id": 2002,
                        "wordValue": "casa",
                        "wordLemmaValue": "casa",
                        "combinedTranslation": "дом",
                        "transcription": None,
                        "pronunciation": "https://audiocdn.lingualeo.com/v2/mock2.mp3",
                        "wordSets": [{"id": 1, "name": "Мой словарь"}],
                        "created": 1234567891,
                        "learningStatus": 0,
                        "progress": 0,
                    },
                ],
            },
        ],
        "listWordSets": [
            {"id": 1, "name": "Мой словарь"},
        ],
        "wordSet": {
            "id": 1,
            "name": "Мой словарь",
            "countWords": 2,
            "isGlobal": False,
        },
        "trainings": [],
    }


def mock_set_words_response(word: str = "palabra", translation_id: int = 1001) -> dict:
    """Mock SetWords API response after successfully adding a word."""
    return {
        "status": "ok",
        "data": [
            {
                "id": 2001,
                "wordValue": word,
                "translation": {
                    "id": translation_id,
                    "tr": "перевод",
                },
            },
        ],
    }


def mock_translation_candidate(
    candidate_id: int = 1001,
    value: str = "перевод",
    main: int = 1,
    selected: int = 0,
) -> dict:
    """Create a mock translation candidate."""
    return {
        "id": candidate_id,
        "value": value,
        "tr": value,
        "main": main,
        "selected": selected,
    }

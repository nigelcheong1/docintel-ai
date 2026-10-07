import re

_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_WORD_VARIANTS = {
    "duplicates": "duplicate",
    "eliminate": "remove",
    "eliminated": "remove",
    "eliminating": "remove",
    "elimination": "remove",
    "removed": "remove",
    "removes": "remove",
    "removing": "remove",
    "removal": "remove",
}


def matching_words(text: str) -> set[str]:
    return {_WORD_VARIANTS.get(word, word) for word in _WORD_PATTERN.findall(text.lower())}

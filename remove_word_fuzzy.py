"""Fuzzy text helpers for OCR cleanup."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from collections.abc import Iterable


_WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")
_MULTISPACE_RE = re.compile(r"\s{2,}")


def _normalize_token(token: str) -> str:
	return re.sub(r"[^a-z0-9]", "", token.lower())


def _normalize_phrase(phrase: str) -> str:
	return "".join(_normalize_token(token) for token in _WORD_RE.findall(phrase))


def _iter_phrases(phrase_or_phrases: str | Iterable[str]) -> list[str]:
	if isinstance(phrase_or_phrases, str):
		return [phrase_or_phrases]
	return [phrase for phrase in phrase_or_phrases if phrase]


def _match_score(candidate: str, target: str) -> float:
	if not candidate or not target:
		return 0.0
	return SequenceMatcher(None, candidate, target).ratio()


def remove_fuzzy_phrase(
	text: str,
	phrase: str | Iterable[str],
	threshold: float = 0.82,
	max_window: int | None = None,
) -> str:
	"""Remove the best OCR-like match of ``phrase`` from ``text``.

	The matching is token based and tolerant to small OCR errors such as
	``EJUSQLUIE SPECIES`` for ``EJUSQUE SPECIES``.
	"""

	if not text:
		return text

	targets = [
		(normalized, len(_WORD_RE.findall(phrase_value)))
		for phrase_value in _iter_phrases(phrase)
		if (normalized := _normalize_phrase(phrase_value))
	]
	if not targets:
		return text

	words = list(_WORD_RE.finditer(text))
	if not words:
		return text

	min_window = max(1, min(word_count for _, word_count in targets) - 1)
	if max_window is None:
		max_window = max(word_count for _, word_count in targets) + 1
	max_window = max(min_window, max_window)

	best = None
	best_score = threshold

	for start in range(len(words)):
		for window_size in range(min_window, max_window + 1):
			end = start + window_size
			if end > len(words):
				break

			candidate = "".join(
				_normalize_token(match.group(0)) for match in words[start:end]
			)
			for target, _word_count in targets:
				score = _match_score(candidate, target)
				if score >= best_score:
					best_score = score
					best = (start, end)

	if best is None:
		return text

	start, end = best
	left = words[start].start()
	right = words[end - 1].end()

	cleaned = text[:left] + text[right:]
	cleaned = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", cleaned)
	cleaned = _MULTISPACE_RE.sub(" ", cleaned)
	return cleaned.strip()


def remove_ejusque_species(text: str, threshold: float = 0.82) -> str:
	return remove_fuzzy_phrase(
		text,
		["EJUSQUE SPECIES", "ET EJUS SPECIES"],
		threshold=threshold,
	)

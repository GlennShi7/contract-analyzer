"""For each checklist item, find the few contract segments a reviewer would need to read.

Phase 1 of the per-item pipeline: no model call. Candidates are ordered in three tiers:
1. segments containing a keyword phrase from checklist.json, matched at word starts ("sublet" also finds
   "subletting"). A segment scores its rarest matching phrase plus a little for each further phrase, so one specific
   phrase ("not be responsible") outranks two generic ones ("negligence", "liability");
2. an optional ranking passed in by the caller (for example sentence embeddings);
3. BM25 over the words of the keywords and the item's English name, filling the remaining places.

Absence follows the same rule as the single-call pipeline's absence check, so both pipelines agree on which items a
lease may be said to lack: the item takes "missing" cards and none of its keyword phrases occur anywhere.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from segmenter import Segment

DEFAULT_TOP_K = 8
SECONDARY_PHRASE_WEIGHT = 0.3
# The judge for one item reads at most this much contract text.
MAX_CANDIDATE_CHARS = 6000
BM25_K1 = 1.5
BM25_B = 0.75
WORD = re.compile(r"[a-z0-9]+|[\u3400-\u9fff]")
CJK_CHAR = re.compile(r"[\u3400-\u9fff]")
STOPWORDS = frozenset(
    "a an and are as at be by for from has have in into is it its of on or that the this to with without any all no not "
    "shall will may must lessee lessor tenant landlord resident owner premises lease agreement".split()
)


def tokens(text: str) -> list[str]:
    return [word for word in WORD.findall(text.lower()) if (word not in STOPWORDS and len(word) > 1) or CJK_CHAR.match(word)]


def phrase_pattern(phrase: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(phrase.lower()))


@dataclass
class Hit:
    segment: Segment
    score: float
    keywords: list[str] = field(default_factory=list)
    bm25: float = 0.0

    def as_dict(self) -> dict:
        return self.segment.as_dict() | {"score": round(self.score, 5), "keywords": self.keywords, "bm25": round(self.bm25, 3)}


@dataclass
class ItemRetrieval:
    item: dict
    status: str  # "found" (a keyword phrase occurs), "absent" (may be said to be missing), "no_match"
    hits: list[Hit]

    def as_dict(self) -> dict:
        item = self.item
        return {"id": item["id"], "name_zh": item["name_zh"], "name_en": item["name_en"], "tier": item["tier"],
                "absent_means": item["absent_means"], "status": self.status, "hits": [hit.as_dict() for hit in self.hits]}


class BM25:
    def __init__(self, documents: list[list[str]]):
        self.documents = documents
        self.lengths = [len(d) for d in documents]
        self.average = (sum(self.lengths) / len(documents)) if documents else 0.0
        self.frequencies = [Counter(d) for d in documents]
        df = Counter(word for d in documents for word in set(d))
        n = len(documents)
        self.idf = {word: math.log(1 + (n - count + 0.5) / (count + 0.5)) for word, count in df.items()}

    def scores(self, query: list[str]) -> list[float]:
        terms = [word for word in dict.fromkeys(query) if word in self.idf]
        result = []
        for frequencies, length in zip(self.frequencies, self.lengths):
            score = 0.0
            for word in terms:
                f = frequencies.get(word, 0)
                if f:
                    score += self.idf[word] * f * (BM25_K1 + 1) / (f + BM25_K1 * (1 - BM25_B + BM25_B * length / (self.average or 1)))
            result.append(score)
        return result


def retrieve_items(segments: list[Segment], checklist: dict[int, dict], *, top_k: int = DEFAULT_TOP_K,
                   max_chars: int = MAX_CANDIDATE_CHARS, extra_rankings: dict[int, list[int]] | None = None) -> list[ItemRetrieval]:
    """One ItemRetrieval per checklist item, in checklist order.

    At most top_k segments and max_chars characters per item (the first segment is always kept). Segments on pamphlet
    pages are used only when nothing in the lease itself matches. extra_rankings maps an item id to segment indices
    ranked by another signal (for example embeddings).
    """
    texts = [segment.lower or segment.text.lower() for segment in segments]
    bm25 = BM25([tokens(text) for text in texts])
    n = len(segments)
    # Rarity is counted over lease terms only: pamphlets repeat statute words ("sublet") and would dilute them.
    lease_count = sum(not segment.informational for segment in segments) or n
    results = []
    for item_id, item in checklist.items():
        phrases = list(dict.fromkeys(keyword.lower() for keyword in item["keywords"]))
        matched: dict[int, list[str]] = {}
        weights: dict[str, float] = {}
        for phrase in phrases:
            pattern = phrase_pattern(phrase)
            where = [i for i, text in enumerate(texts) if pattern.search(text)]
            if not where:
                continue
            in_lease = sum(not segments[i].informational for i in where) or len(where)
            weights[phrase] = math.log(1 + lease_count / in_lease)
            for i in where:
                matched.setdefault(i, []).append(phrase)
        phrase_scores = {}
        for i, found in matched.items():
            ordered_weights = sorted((weights[p] for p in found), reverse=True)
            phrase_scores[i] = ordered_weights[0] + SECONDARY_PHRASE_WEIGHT * sum(ordered_weights[1:])
        query = tokens(" ".join(item["keywords"]) + " " + item["name_en"])
        bm25_scores = bm25.scores(query)
        ranked = sorted(phrase_scores, key=lambda i: (-phrase_scores[i], -bm25_scores[i], i))
        seen = set(ranked)
        for i in (extra_rankings or {}).get(item_id, []):
            if i not in seen:
                ranked.append(i)
                seen.add(i)
        ranked += sorted((i for i in range(n) if bm25_scores[i] > 0 and i not in seen), key=lambda i: (-bm25_scores[i], i))
        score = {i: phrase_scores.get(i, 0.0) for i in ranked}
        lease_terms = [i for i in ranked if not segments[i].informational]
        ordered, used = [], 0
        for i in lease_terms or ranked:
            if len(ordered) >= top_k:
                break
            if ordered and used + len(segments[i].text) > max_chars:
                continue
            ordered.append(i)
            used += len(segments[i].text)
        hits = [Hit(segment=segments[i], score=score[i], keywords=matched.get(i, []), bm25=bm25_scores[i]) for i in ordered]
        if matched:
            status = "found"
        elif item["absent_means"] == "missing":
            status = "absent"
        else:
            status = "no_match"
        results.append(ItemRetrieval(item=item, status=status, hits=hits))
    return results

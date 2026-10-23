"""嵌入模型標註與補標的單元測試（ChromaDB 用假物件，不需任何服務）。"""

from collections import Counter

import pytest
from embedding_labels import UNLABELED, label_combinations
from subscribers.labels import chroma_label_counts, cosine, label_chroma, verify_sample

LABELS = {"embedding_model": "bge-m3:latest", "embedding_version": "790764642607"}


class PagedCollection:
    """模擬 chromadb collection 的 count／get(limit, offset)／update。"""

    def __init__(self, rows):
        self.rows = rows  # [(id, document, embedding, metadata)]
        self.updates = []

    def count(self):
        return len(self.rows)

    def get(self, limit, offset, include):
        page = self.rows[offset : offset + limit]
        return {
            "ids": [r[0] for r in page],
            "documents": [r[1] for r in page],
            "embeddings": [r[2] for r in page],
            "metadatas": [r[3] for r in page],
        }

    def update(self, ids, metadatas):
        self.updates.append((list(ids), list(metadatas)))


def rows(n, labeled=0):
    return [
        (
            f"c{i}",
            f"text {i}",
            [1.0, float(i)],
            {"source": "harvard", **(LABELS if i < labeled else {})},
        )
        for i in range(n)
    ]


def test_label_combinations_counts_unlabeled_separately():
    counts = label_combinations([LABELS, LABELS, {"source": "x"}, None])

    assert counts == Counter({("bge-m3:latest", "790764642607"): 2, UNLABELED: 2})


def test_cosine():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine([0, 0], [1, 1]) == 0.0


def test_verify_sample_reports_minimum_similarity():
    collection = PagedCollection(rows(10))

    same = verify_sample(collection, lambda docs: [[1.0, float(d.split()[1])] for d in docs], n=5)
    drifted = verify_sample(collection, lambda docs: [[0.0, 1.0] for _ in docs], n=5)

    assert same == pytest.approx(1.0)
    assert drifted < 0.9999
    assert verify_sample(PagedCollection([]), lambda docs: [], n=5) == 1.0


def test_label_chroma_only_touches_unlabeled_and_keeps_existing_metadata(monkeypatch):
    import subscribers.labels as labels_module

    monkeypatch.setattr(labels_module, "PAGE_SIZE", 3)
    collection = PagedCollection(rows(7, labeled=2))

    assert label_chroma(collection, LABELS, apply=False) == 5
    assert collection.updates == []

    assert label_chroma(collection, LABELS, apply=True) == 5
    updated_ids = [i for ids, _ in collection.updates for i in ids]
    assert updated_ids == ["c2", "c3", "c4", "c5", "c6"]
    assert collection.updates[0][1][0] == {"source": "harvard", **LABELS}


def test_chroma_label_counts_pages_through_collection(monkeypatch):
    import subscribers.labels as labels_module

    monkeypatch.setattr(labels_module, "PAGE_SIZE", 2)

    assert chroma_label_counts(PagedCollection(rows(5, labeled=3))) == Counter(
        {("bge-m3:latest", "790764642607"): 3, UNLABELED: 2}
    )

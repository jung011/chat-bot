import math

from app.retrieval.embedder import HashEmbedder


def test_dim_and_norm():
    emb = HashEmbedder(dim=128)
    v = emb.embed("마르게리따 피자")
    assert len(v) == 128
    assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-6)


def test_deterministic():
    emb = HashEmbedder()
    assert emb.embed("영업시간") == emb.embed("영업시간")


def test_empty_input_safe():
    emb = HashEmbedder(dim=64)
    v = emb.embed("")
    assert len(v) == 64 and any(v)  # 0 벡터가 아닌 안정적 단위벡터


def test_shared_tokens_closer():
    emb = HashEmbedder()
    def cos(a, b):
        return sum(x * y for x, y in zip(a, b))
    base = emb.embed("마르게리따 피자 가격")
    near = emb.embed("마르게리따 피자")
    far = emb.embed("짜장면 곱빼기")
    assert cos(base, near) > cos(base, far)

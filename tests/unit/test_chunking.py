from indexing.chunking import chunk
from indexing.parsers import parse_text


def test_chunk_per_line():
    text = "마르게리따 피자 25000원\n페퍼로니 피자 27000원"
    chunks = chunk(text)
    assert len(chunks) == 2
    assert "마르게리따" in chunks[0]


def test_short_line_merged():
    chunks = chunk("메뉴 항목 가격 정보\nL")
    assert len(chunks) == 1  # 'L' 은 직전 청크에 병합


def test_parse_text_normalizes():
    # 앞뒤 공백 제거 + 각 줄 우측 공백 제거(좌측 들여쓰기는 보존)
    assert parse_text("  a  \n  b  ") == "a\n  b"

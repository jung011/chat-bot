from app.tenancy import router
from app.tenancy.registry import get_registry


def test_tenants_registered():
    reg = get_registry()
    ids = {t.company_id for t in reg.all()}
    # 최소 3개 파일럿 + 온보딩된 신규 업체(bunsik) 포함
    assert {"pizza", "chinese", "chicken"} <= ids


def test_resolve_valid_and_invalid():
    assert router.resolve("pizza").name == "마르게리따 피자"
    assert router.resolve("nope") is None
    assert router.resolve("") is None


def test_business_info_text():
    t = router.resolve("chicken")
    text = t.business_info_text()
    assert "전화" in text and t.faq.collection == "faq_chicken"

from app.orchestration.nodes.route import rule_route


def test_greeting_is_chitchat():
    assert rule_route("안녕하세요") == "chitchat"
    assert rule_route("고마워요~") == "chitchat"


def test_greeting_with_info_is_not_chitchat():
    # 인사 + 정보 요청이면 chitchat 아님(메뉴/가격은 백엔드 도구 → agent)
    assert rule_route("안녕하세요 메뉴 가격 알려주세요") != "chitchat"


def test_tool_signal_is_agent():
    assert rule_route("송파구 배달되는지 확인하고 예상 배달시간도 알려줘") == "agent"
    assert rule_route("주문 방법 알려줘") == "agent"


def test_db_backed_signals_are_agent():
    # 메뉴/가격·주문상태는 백엔드 API/DB 조회 도구 → agent 경로
    assert rule_route("마르게리따 피자 얼마예요?") == "agent"
    assert rule_route("짜장면 가격 알려줘") == "agent"
    assert rule_route("주문번호 1001 상태 알려줘") == "agent"


def test_default_is_rag():
    # 도구 신호 없는 설명형/정책 질의는 기본 rag
    assert rule_route("환불 정책이 어떻게 되나요?") == "rag"
    assert rule_route("매장 분위기 어때요?") == "rag"

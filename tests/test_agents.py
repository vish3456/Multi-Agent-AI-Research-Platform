from src.agents.graph import should_retry, build_research_graph


def test_should_retry_on_critic_failure():
    state = {
        "critic_passed": False,
        "retry_count": 0,
        "query": "quantum computing",
        "session_history": [],
        "related_memories": [],
        "search_results": [],
        "summary_bullets": [],
        "draft_report": "",
        "critic_feedback": "Needs citations",
        "final_report": "",
        "sources": [],
    }
    assert should_retry(state) == "retry"


def test_should_retry_caps_at_max_retries():
    state = {
        "critic_passed": False,
        "retry_count": 3,
        "query": "quantum computing",
        "session_history": [],
        "related_memories": [],
        "search_results": [],
        "summary_bullets": [],
        "draft_report": "",
        "critic_feedback": "Still failed",
        "final_report": "",
        "sources": [],
    }
    assert should_retry(state) == "accept"


def test_should_not_retry_on_critic_pass():
    state = {
        "critic_passed": True,
        "retry_count": 1,
        "query": "quantum computing",
        "session_history": [],
        "related_memories": [],
        "search_results": [],
        "summary_bullets": [],
        "draft_report": "Valid report",
        "critic_feedback": "Passed",
        "final_report": "Valid report",
        "sources": ["source1"],
    }
    assert should_retry(state) == "accept"


def test_graph_builds():
    graph = build_research_graph()
    assert graph is not None

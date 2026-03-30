from app.tools.registry import execute_tool, get_tool_definitions


def test_registry_exposes_canonical_tools():
    names = [tool.name for tool in get_tool_definitions()]
    assert names == sorted(names)
    assert 'http_request' in names
    assert 'image_generate' in names
    assert 'memory_search' in names
    assert 'memory_store' in names


def test_execute_tool_returns_normalized_error_for_unknown_tool():
    result = execute_tool('not_a_real_tool', {}, session_id=None)
    assert result['ok'] is False
    assert 'Unknown tool' in result['error']
    assert 'markdown' in result

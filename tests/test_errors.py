from __future__ import annotations

import logging

from pyosm_agents.core.errors import exception_to_tool_error


def test_unhandled_exception_is_logged_with_traceback(caplog) -> None:
    error = RuntimeError("client is already closed")

    with caplog.at_level(logging.ERROR, logger="pyosm_agents.core.errors"):
        result = exception_to_tool_error(error)

    assert result.code == "internal_error"
    assert result.message == "Unexpected error while executing the OpenStreetMap tool"
    assert len(caplog.records) == 1
    assert caplog.records[0].exc_info is not None
    assert caplog.records[0].exc_info[1] is error

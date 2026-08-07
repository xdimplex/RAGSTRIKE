"""Tests for the stateful sdk/helpers modules: Timer, id generators, FileHelper, JsonHelper,
YamlHelper, retry_async."""

from __future__ import annotations

from pathlib import Path
import time

import pytest

from ragstrike.sdk.exceptions import SdkError
from ragstrike.sdk.helpers import (
    FileHelper,
    JsonHelper,
    Timer,
    YamlHelper,
    new_short_id,
    new_uuid,
    retry_async,
)

# -- Timer --------------------------------------------------------------------------------------


def test_timer_as_context_manager_records_elapsed_time() -> None:
    with Timer() as timer:
        time.sleep(0.01)

    assert timer.elapsed_ms >= 10
    assert timer.running is False


def test_timer_elapsed_ms_is_zero_before_start() -> None:
    assert Timer().elapsed_ms == 0


def test_timer_elapsed_ms_readable_while_running() -> None:
    timer = Timer().start()
    time.sleep(0.01)

    assert timer.elapsed_ms > 0
    assert timer.running is True


def test_timer_stop_before_start_raises() -> None:
    with pytest.raises(RuntimeError):
        Timer().stop()


def test_timer_manual_start_stop() -> None:
    timer = Timer()
    timer.start()
    timer.stop()

    assert timer.running is False
    assert timer.elapsed_ms >= 0


# -- identifiers ----------------------------------------------------------------------------------


def test_new_uuid_is_32_hex_chars() -> None:
    value = new_uuid()

    assert len(value) == 32
    int(value, 16)  # must be valid hex


def test_new_uuid_is_unique_across_calls() -> None:
    assert new_uuid() != new_uuid()


def test_new_short_id_default_length() -> None:
    assert len(new_short_id()) == 8


def test_new_short_id_custom_length() -> None:
    assert len(new_short_id(length=4)) == 4


def test_new_short_id_rejects_out_of_range_length() -> None:
    with pytest.raises(ValueError):
        new_short_id(length=0)
    with pytest.raises(ValueError):
        new_short_id(length=33)


# -- FileHelper -----------------------------------------------------------------------------------


def test_file_helper_exists(tmp_path: Path) -> None:
    file_path = tmp_path / "a.txt"
    file_path.write_text("hi", encoding="utf-8")

    assert FileHelper.exists(file_path) is True
    assert FileHelper.exists(tmp_path / "missing.txt") is False


def test_file_helper_read_text(tmp_path: Path) -> None:
    file_path = tmp_path / "a.txt"
    file_path.write_text("hello", encoding="utf-8")

    assert FileHelper.read_text(file_path) == "hello"


def test_file_helper_read_text_raises_sdk_error_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SdkError):
        FileHelper.read_text(tmp_path / "missing.txt")


def test_file_helper_read_bytes(tmp_path: Path) -> None:
    file_path = tmp_path / "a.bin"
    file_path.write_bytes(b"\x00\x01")

    assert FileHelper.read_bytes(file_path) == b"\x00\x01"


def test_file_helper_try_read_text_returns_default_on_failure(tmp_path: Path) -> None:
    assert FileHelper.try_read_text(tmp_path / "missing.txt") == ""
    assert FileHelper.try_read_text(tmp_path / "missing.txt", default="fallback") == "fallback"


def test_file_helper_try_read_text_returns_content_on_success(tmp_path: Path) -> None:
    file_path = tmp_path / "a.txt"
    file_path.write_text("hi", encoding="utf-8")

    assert FileHelper.try_read_text(file_path) == "hi"


# -- JsonHelper -------------------------------------------------------------------------------


def test_json_helper_loads_valid_json() -> None:
    assert JsonHelper.loads('{"a": 1}') == {"a": 1}


def test_json_helper_loads_returns_none_for_invalid_json() -> None:
    assert JsonHelper.loads("not json") is None


def test_json_helper_require_loads_raises_for_invalid_json() -> None:
    with pytest.raises(SdkError):
        JsonHelper.require_loads("not json")


def test_json_helper_dumps() -> None:
    assert JsonHelper.dumps({"a": 1}) == '{"a": 1}'


def test_json_helper_load_and_dump_file_round_trip(tmp_path: Path) -> None:
    file_path = tmp_path / "a.json"
    JsonHelper.dump_file(file_path, {"a": 1})

    assert JsonHelper.load_file(file_path) == {"a": 1}


# -- YamlHelper -------------------------------------------------------------------------------


def test_yaml_helper_load_valid_yaml() -> None:
    assert YamlHelper.load("a: 1\n") == {"a": 1}


def test_yaml_helper_load_returns_none_for_invalid_yaml() -> None:
    assert YamlHelper.load("a: [unclosed") is None


def test_yaml_helper_require_load_raises_for_invalid_yaml() -> None:
    with pytest.raises(SdkError):
        YamlHelper.require_load("a: [unclosed")


def test_yaml_helper_load_and_dump_file_round_trip(tmp_path: Path) -> None:
    file_path = tmp_path / "a.yaml"
    YamlHelper.dump_file(file_path, {"a": 1})

    assert YamlHelper.load_file(file_path) == {"a": 1}


# -- retry_async ------------------------------------------------------------------------------


async def test_retry_async_returns_on_first_success() -> None:
    calls = 0

    async def succeed() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    result = await retry_async(succeed, attempts=3, backoff_s=0.001)

    assert result == "ok"
    assert calls == 1


async def test_retry_async_retries_until_success() -> None:
    calls = 0

    async def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError("boom")
        return "ok"

    result = await retry_async(flaky, attempts=5, backoff_s=0.001, max_backoff_s=0.01)

    assert result == "ok"
    assert calls == 3


async def test_retry_async_raises_last_error_after_exhausting_attempts() -> None:
    async def always_fails() -> str:
        raise ConnectionError("still broken")

    with pytest.raises(ConnectionError, match="still broken"):
        await retry_async(always_fails, attempts=2, backoff_s=0.001)


async def test_retry_async_rejects_attempts_below_one() -> None:
    async def noop() -> None:
        return None

    with pytest.raises(ValueError):
        await retry_async(noop, attempts=0)


async def test_retry_async_only_retries_matching_exception_types() -> None:
    async def raises_type_error() -> None:
        raise TypeError("not retryable here")

    with pytest.raises(TypeError):
        await retry_async(raises_type_error, attempts=3, backoff_s=0.001, retry_on=(ValueError,))


async def test_retry_async_never_retries_a_successful_response() -> None:
    """The whole point of retrying exceptions only: a call that returns must be counted once."""
    calls = 0

    async def returns_a_bad_looking_but_valid_response() -> str:
        nonlocal calls
        calls += 1
        return "this looks like a refusal but it is still a real response"

    result = await retry_async(returns_a_bad_looking_but_valid_response, attempts=3)

    assert calls == 1
    assert "refusal" in result

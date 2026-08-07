"""Validator tests.

Every function here is attack-agnostic on purpose -- these tests never construct anything that
looks like a specific attack technique, only generic responses, status codes, JSON, and dicts.
"""

from __future__ import annotations

import pytest

from ragstrike.core.contracts.target_adapter import TargetResponse
from ragstrike.sdk.exceptions import ValidationError
from ragstrike.sdk.validators import (
    fields_exist,
    has_required_metadata,
    is_valid_json,
    is_valid_status_code,
    missing_fields,
    require_fields,
    require_metadata,
    require_response,
    require_response_text,
    require_valid_json,
    require_valid_status_code,
    response_exists,
    response_has_text,
)

# -- response ---------------------------------------------------------------------------------


def test_response_exists() -> None:
    assert response_exists(TargetResponse(text="hi")) is True
    assert response_exists(None) is False


def test_require_response_returns_the_response() -> None:
    response = TargetResponse(text="hi")

    assert require_response(response) is response


def test_require_response_raises_on_none() -> None:
    with pytest.raises(ValidationError):
        require_response(None)


def test_response_has_text() -> None:
    assert response_has_text(TargetResponse(text="hi")) is True
    assert response_has_text(TargetResponse(text="")) is False
    assert response_has_text(TargetResponse(text="   ")) is False


def test_require_response_text_returns_text() -> None:
    assert require_response_text(TargetResponse(text="hi")) == "hi"


def test_require_response_text_raises_when_empty() -> None:
    with pytest.raises(ValidationError):
        require_response_text(TargetResponse(text=""))


# -- status codes -------------------------------------------------------------------------------


def test_is_valid_status_code_default_range() -> None:
    assert is_valid_status_code(200) is True
    assert is_valid_status_code(299) is True
    assert is_valid_status_code(404) is False
    assert is_valid_status_code(None) is False


def test_is_valid_status_code_custom_range() -> None:
    assert is_valid_status_code(302, ok_range=range(300, 400)) is True
    assert is_valid_status_code(200, ok_range=range(300, 400)) is False


def test_require_valid_status_code_returns_the_code() -> None:
    assert require_valid_status_code(200) == 200


def test_require_valid_status_code_raises_for_out_of_range() -> None:
    with pytest.raises(ValidationError):
        require_valid_status_code(500)


def test_require_valid_status_code_raises_for_none() -> None:
    with pytest.raises(ValidationError):
        require_valid_status_code(None)


# -- JSON -----------------------------------------------------------------------------------------


def test_is_valid_json() -> None:
    assert is_valid_json('{"a": 1}') is True
    assert is_valid_json("not json") is False


def test_require_valid_json_returns_parsed_value() -> None:
    assert require_valid_json('{"a": 1}') == {"a": 1}


def test_require_valid_json_raises_with_reason() -> None:
    with pytest.raises(ValidationError):
        require_valid_json("not json")


# -- fields -----------------------------------------------------------------------------------


def test_fields_exist() -> None:
    assert fields_exist({"a": 1, "b": 2}, "a", "b") is True
    assert fields_exist({"a": 1}, "a", "b") is False


def test_fields_exist_treats_none_value_as_present() -> None:
    assert fields_exist({"a": None}, "a") is True


def test_missing_fields_lists_only_the_absent_ones_in_order() -> None:
    assert missing_fields({"a": 1}, "a", "b", "c") == ["b", "c"]
    assert missing_fields({"a": 1, "b": 2}, "a", "b") == []


def test_require_fields_returns_data_when_all_present() -> None:
    data = {"a": 1, "b": 2}
    assert require_fields(data, "a", "b") is data


def test_require_fields_raises_naming_every_missing_field() -> None:
    with pytest.raises(ValidationError, match="b, c"):
        require_fields({"a": 1}, "a", "b", "c")


# -- metadata ---------------------------------------------------------------------------------


def test_has_required_metadata() -> None:
    assert has_required_metadata({"threshold": 5}, "threshold") is True
    assert has_required_metadata({}, "threshold") is False


def test_require_metadata_returns_config_when_satisfied() -> None:
    config = {"threshold": 5}
    assert require_metadata(config, "threshold") is config


def test_require_metadata_raises_with_hint() -> None:
    with pytest.raises(ValidationError) as excinfo:
        require_metadata({}, "threshold")

    assert "threshold" in str(excinfo.value)
    assert excinfo.value.hint

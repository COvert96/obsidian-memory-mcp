from __future__ import annotations

import inspect
import json
from functools import lru_cache, wraps
from importlib.resources import files
from typing import Any, Literal

from jsonschema import Draft202012Validator

from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error


SchemaKind = Literal["request", "response"]


class ValidationError(ToolExecutionError):
    """Raised when a tool request or response does not match its JSON Schema."""


@lru_cache(maxsize=None)
def load_tool_schema(tool_name: str) -> dict[str, Any]:
    schema_path = files("obsidian_memory_mcp.schemas").joinpath(f"{tool_name}.json")
    try:
        return json.loads(schema_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValidationError(
            build_error(
                ErrorCode.ERR_INTERNAL,
                message=(
                    f"No JSON Schema is registered for tool '{tool_name}'. "
                    "This is a server configuration error."
                ),
                details={
                    "tool_name": tool_name,
                    "validator": "schema_registry",
                    "suggestion": "Register both request and response schemas before using the tool.",
                },
            )
        ) from error


def validate_tool_payload(tool_name: str, payload: dict[str, Any], *, schema_kind: SchemaKind) -> None:
    schema = load_tool_schema(tool_name).get(schema_kind)
    if schema is None:
        raise ValidationError(
            build_error(
                ErrorCode.ERR_INVALID_REQUEST,
                message=f"Schema kind '{schema_kind}' is not defined for tool '{tool_name}'.",
                details={
                    "field_path": schema_kind,
                    "validator": "schema_registry",
                    "suggestion": "Define both request and response schemas for every tool contract.",
                },
            )
        )

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=_sort_validation_errors)
    if not errors:
        return

    error = errors[0]
    field_path = _field_path_for(error)
    expected = _expected_value_for(error)
    message = f"{tool_name} {schema_kind} payload is invalid at '{field_path}': {error.message}"
    raise ValidationError(
        build_error(
            ErrorCode.ERR_INVALID_REQUEST,
            message=message,
            details={
                "field_path": field_path,
                "validator": error.validator,
                "expected": expected,
                "schema_path": "/".join(str(part) for part in error.schema_path),
                "suggestion": _suggestion_for(error, field_path),
            },
        )
    )


def validate_tool_handler(tool_name: str):
    def decorator(function):
        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def async_wrapper(payload: dict[str, Any], *args: Any, **kwargs: Any):
                validate_tool_payload(tool_name, payload, schema_kind="request")
                response = await function(payload, *args, **kwargs)
                validate_tool_payload(tool_name, response, schema_kind="response")
                return response

            return async_wrapper

        @wraps(function)
        def wrapper(payload: dict[str, Any], *args: Any, **kwargs: Any):
            validate_tool_payload(tool_name, payload, schema_kind="request")
            response = function(payload, *args, **kwargs)
            validate_tool_payload(tool_name, response, schema_kind="response")
            return response

        return wrapper

    return decorator


def _sort_validation_errors(error: Any) -> tuple[int, str, str]:
    return (len(error.path), _field_path_for(error), error.validator)


def _field_path_for(error: Any) -> str:
    if error.validator == "required":
        required_fields = set(error.validator_value)
        present_fields = set(error.instance.keys()) if isinstance(error.instance, dict) else set()
        missing_fields = required_fields - present_fields
        if missing_fields:
            return sorted(missing_fields)[0]
    if error.path:
        return ".".join(str(part) for part in error.path)
    return "payload"


def _expected_value_for(error: Any) -> Any:
    if error.validator == "type":
        return error.validator_value
    if error.validator in {"minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems"}:
        return error.validator_value
    if error.validator == "enum":
        return list(error.validator_value)
    if error.validator == "required":
        return "required property"
    return error.validator_value


def _suggestion_for(error: Any, field_path: str) -> str:
    if error.validator == "required":
        return f"Provide the missing required field '{field_path}' and retry."
    if error.validator == "type":
        expected = error.validator_value
        return f"Change '{field_path}' to the expected type: {expected}."
    if error.validator == "minimum":
        return f"Increase '{field_path}' to at least {error.validator_value}."
    if error.validator == "enum":
        return f"Use one of the allowed values for '{field_path}': {', '.join(map(str, error.validator_value))}."
    if error.validator == "minItems":
        return f"Provide at least {error.validator_value} item(s) for '{field_path}'."
    return f"Adjust '{field_path}' to satisfy the documented JSON Schema constraints and retry."

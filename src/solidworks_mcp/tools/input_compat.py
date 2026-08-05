"""Shared input model compatibility helpers for tool schemas.

This module centralizes test/backward-compat parsing behavior so individual tool modules
stay focused on domain fields.
"""

from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict

TModel = TypeVar("TModel", bound=BaseModel)


class CompatInput(BaseModel):
    """Base schema allowing legacy/extra fields used by existing tests.

    Attributes:
        model_config (Any): The model config value.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)


def normalize_input(input_data: Any, model_type: type[TModel]) -> TModel:
    """Accept either a model instance or a plain dict.

    FastMCP hands a tool a validated model, but tools are also called directly
    with dicts — from tests, from the agent harness, and from other tools.
    Without this, ``getattr`` on the dict returns ``None`` for every field, and
    the tool either rejects valid input or raises
    ``'dict' object has no attribute ...``.

    Three tool modules had each grown their own private copy of this and three
    more had none at all, which is how the bug kept reappearing.

    Args:
        input_data (Any): The incoming payload.
        model_type (type[TModel]): The Pydantic model to coerce to.

    Returns:
        TModel: An instance of ``model_type``.
    """
    if input_data is None:
        return model_type()
    if isinstance(input_data, model_type):
        return input_data
    if hasattr(input_data, "model_dump"):
        return model_type.model_validate(input_data.model_dump())
    return model_type.model_validate(input_data)

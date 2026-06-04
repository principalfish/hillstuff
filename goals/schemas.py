from typing import Any

from pydantic import BaseModel, Field, field_validator

from goals.calc import GOAL_TYPES
from goals.models import ACTIVITY_TYPES


class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    goal_type: str
    activity_types: list[str]
    target: float = Field(gt=0)

    @field_validator('name', mode='before')
    @classmethod
    def strip_name(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else v

    @field_validator('goal_type')
    @classmethod
    def valid_goal_type(cls, v: str) -> str:
        if v not in GOAL_TYPES:
            raise ValueError(f'must be one of {", ".join(GOAL_TYPES)}')
        return v

    @field_validator('activity_types')
    @classmethod
    def valid_activity_types(cls, v: list[str]) -> list[str]:
        # Keep canonical order and drop anything unrecognised / duplicated.
        cleaned = [a for a in ACTIVITY_TYPES if a in v]
        if not cleaned:
            raise ValueError('select at least one activity type')
        return cleaned


class MilestoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target: str | None = None
    result: str | None = None
    achieved: bool = False

    @field_validator('name', mode='before')
    @classmethod
    def strip_name(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else v

    @field_validator('target', 'result', mode='before')
    @classmethod
    def empty_to_none(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class ActivityTotalUpdate(BaseModel):
    distance_km: float = Field(ge=0)
    ascent_m: float = Field(ge=0)
    time_hours: float = Field(ge=0)

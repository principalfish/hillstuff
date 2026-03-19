from pydantic import BaseModel, Field, field_validator


class RouteForm(BaseModel):
    name: str = Field(min_length=1)
    latitude: float = Field(default=56.8, ge=-90, le=90)
    longitude: float = Field(default=-5.1, ge=-180, le=180)


class LegForm(BaseModel):
    leg_num: int = Field(ge=1)
    location: str = Field(min_length=1)
    distance_km: float = Field(ge=0)
    ascent_m: float = Field(ge=0)
    descent_m: float = Field(default=0, ge=0)
    notes: str = ''

    @field_validator('distance_km')
    @classmethod
    def round_distance(cls, v: float) -> float:
        return round(v, 1)

    @field_validator('ascent_m', 'descent_m')
    @classmethod
    def round_elevation(cls, v: float) -> float:
        return round(v)


class SettingsForm(BaseModel):
    start_time: str | None = None
    start_date: str | None = None

    @field_validator('start_time', 'start_date', mode='before')
    @classmethod
    def empty_to_none(cls, v: str | None) -> str | None:
        if isinstance(v, str) and not v.strip():
            return None
        return v.strip() if isinstance(v, str) else v


class PaceTierForm(BaseModel):
    up_to_minutes: float | None = None
    flat_pace_min_per_km: float = Field(gt=0)
    ascent_pace_min_per_150m: float = Field(ge=0, default=0)
    descent_pace_min_per_450m: float = Field(ge=0, default=0)


class LegUpdateForm(BaseModel):
    distance_km: float = Field(ge=0)
    ascent_m: float = Field(ge=0)
    descent_m: float = Field(ge=0)
    notes: str = ''
    override_minutes: float | None = None

    @field_validator('distance_km')
    @classmethod
    def round_distance(cls, v: float) -> float:
        return round(v, 1)

    @field_validator('ascent_m', 'descent_m')
    @classmethod
    def round_elevation(cls, v: float) -> float:
        return round(v)

    @field_validator('override_minutes', mode='before')
    @classmethod
    def empty_to_none(cls, v: str | float | None) -> float | None:
        if isinstance(v, str):
            v = v.strip()
            return float(v) if v else None
        return v


class AttemptForm(BaseModel):
    name: str = Field(min_length=1)
    date: str | None = None
    notes: str | None = None

    @field_validator('date', 'notes', mode='before')
    @classmethod
    def empty_to_none(cls, v: str | None) -> str | None:
        if isinstance(v, str) and not v.strip():
            return None
        return v.strip() if isinstance(v, str) else v

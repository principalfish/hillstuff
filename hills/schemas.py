from pydantic import BaseModel, field_validator


class HillForm(BaseModel):
    name: str
    height_m: int
    rank: int | None = None
    region: str = ''
    hill_type: str

    @field_validator('hill_type')
    @classmethod
    def validate_hill_type(cls, v: str) -> str:
        if v not in ('munro', 'corbett', 'wainwright'):
            raise ValueError('Must be munro, corbett, or wainwright')
        return v


class AscentForm(BaseModel):
    date: str

    @field_validator('date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not v:
            raise ValueError('Date is required')
        return v

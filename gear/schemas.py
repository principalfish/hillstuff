from pydantic import BaseModel, Field, field_validator


class LoadoutCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator('name', mode='before')
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v


class LoadoutItemWeightUpdate(BaseModel):
    weight_g: int = Field(ge=0, le=100_000)


class LoadoutItemCreate(BaseModel):
    category: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    weight_g: int = Field(ge=0, le=100_000)
    owned: bool = False
    worn: bool = False

    @field_validator('category', 'name', mode='before')
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

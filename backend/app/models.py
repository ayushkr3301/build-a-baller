"""Request/response schemas for the API."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from .data.attributes import ERAS, POSITIONS


class CreateRun(BaseModel):
    player_name: str = Field(default="Your Player", max_length=28)
    position: str
    era: str

    @field_validator("position")
    @classmethod
    def _pos(cls, v: str) -> str:
        if v not in POSITIONS:
            raise ValueError(f"position must be one of {list(POSITIONS)}")
        return v

    @field_validator("era")
    @classmethod
    def _era(cls, v: str) -> str:
        if v not in ERAS:
            raise ValueError(f"era must be one of {list(ERAS)}")
        return v

    @field_validator("player_name")
    @classmethod
    def _name(cls, v: str) -> str:
        cleaned = " ".join(v.split()).strip()
        return cleaned or "Your Player"


class TakeAttribute(BaseModel):
    attribute: str


class VetoClubs(BaseModel):
    club_ids: list[str]

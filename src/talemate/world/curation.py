"""Curation settings: the knobs a world keeps for curation, stored in its
`meta` table under `curation` (`World.curation`, `World.set_curation`)."""

from pydantic import BaseModel, Field


class CurationSettings(BaseModel):
    """The world's curation knobs."""

    # how far out: steps through links
    reach: int = Field(default=2, ge=1, le=3)
    # how many entries a prompt brings in
    entries: int = Field(default=12, ge=0)
    # how many facts per entry
    facts_per_entry: int = Field(default=6, ge=0)
    # word overlap at which a new fact reads as a repeat
    repeat_threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    # how far out a timeline gathers lines from
    timeline_reach: int = Field(default=2, ge=0, le=3)

"""Curation settings: the knobs a world keeps for curation, stored in its
`meta` table under `curation` (`World.curation`, `World.set_curation`)."""

from pydantic import BaseModel, Field


class CurationSettings(BaseModel):
    """The world's curation knobs."""

    # how far out: steps through links (reach 1 for create: the curation
    # probe's lean, 81% of facts on topic against 65-77% further out)
    reach: int = Field(default=1, ge=1, le=3)
    # how many entries a prompt brings in
    entries: int = Field(default=12, ge=0)
    # how many facts per entry
    facts_per_entry: int = Field(default=6, ge=0)
    # word overlap at which a new fact reads as a repeat
    repeat_threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    # word overlap at which a repeat arrives unticked; below it, a repeat
    # is shown with its match but stays ticked (tuned on the curation
    # probe's runs: at 0.4 the detector unticked 56 of 176 good facts, at
    # 0.7 it unticks 7, nearly all copies of a line already written)
    repeat_untick_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    # word overlap at which two dated facts with different years read as
    # disagreeing on a timeline (and for pick_date); the merge's
    # contradiction pairs keep repeat_threshold (ruling C14). At 0.4 the
    # old acceptance world flagged 18 pairs, about 13 false; at 0.5, 7,
    # every true one kept (ruling C31)
    date_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    # how far out a timeline gathers lines from
    timeline_reach: int = Field(default=2, ge=0, le=3)

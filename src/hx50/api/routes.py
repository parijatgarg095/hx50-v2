"""Read endpoints plus the live mandate rebuild. Handlers translate HTTP <-> service calls and nothing else.

Domain objects are converted with Schema.model_validate rather than returned raw: FastAPI would flatten
dataclasses with asdict() and silently drop computed properties such as turnover or rebalance_day.
"""
from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from ..domain import Variant
from ..service import IndexService
from .schemas import (
    CompositionOut,
    ErrorOut,
    LevelPointOut,
    MandateIn,
    RebalanceOut,
    RebuildOut,
    RunOut,
    ScorecardOut,
)

router = APIRouter(prefix="/api", tags=["index"])


def get_service(request: Request) -> IndexService:
    return request.app.state.service


def date_range(start: dt.date | None = None, end: dt.date | None = None) -> tuple[str | None, str | None]:
    if start and end and start > end:
        raise HTTPException(422, "start must not be after end")
    return (start.isoformat() if start else None, end.isoformat() if end else None)


Service = Annotated[IndexService, Depends(get_service)]
Period = Annotated[tuple[str | None, str | None], Depends(date_range)]


@router.get("/run", response_model=RunOut, summary="Current run manifest and mandate")
def run(service: Service) -> RunOut:
    return RunOut.model_validate(service.reader.manifest())


@router.get("/levels", response_model=list[LevelPointOut], summary="Daily index level")
def levels(service: Service, period: Period, variant: Variant = Variant.STABILISED) -> list[LevelPointOut]:
    return [LevelPointOut.model_validate(p) for p in service.reader.levels(variant, *period)]


@router.get(
    "/composition",
    response_model=CompositionOut,
    responses={404: {"model": ErrorOut}},
    summary="Constituents and weights at a close; non-trading dates resolve to the prior trading day",
)
def composition(service: Service, date: dt.date, variant: Variant = Variant.STABILISED) -> CompositionOut:
    found = service.reader.composition(variant, date.isoformat())
    if found is None:
        raise HTTPException(404, "date is before the start of the index")
    return CompositionOut.model_validate(found)


@router.get("/rebalances", response_model=list[RebalanceOut], summary="Rebalance history with turnover attribution")
def rebalances(service: Service, period: Period, variant: Variant = Variant.STABILISED) -> list[RebalanceOut]:
    return [RebalanceOut.model_validate(r) for r in service.reader.rebalances(variant, *period)]


@router.get("/scorecard", response_model=list[ScorecardOut], summary="Stabilised vs unstabilised comparison")
def scorecard(service: Service) -> list[ScorecardOut]:
    return [ScorecardOut.model_validate(s) for s in service.reader.scorecards()]


@router.post(
    "/rebuild",
    response_model=RebuildOut,
    responses={409: {"model": ErrorOut}, 422: {"model": ErrorOut}},
    summary="Rebuild under a new mandate; atomic, so the previous run keeps serving on failure",
)
def rebuild(service: Service, mandate: MandateIn) -> RebuildOut:
    manifest, scorecards = service.rebuild(**mandate.model_dump())
    return RebuildOut(
        run=RunOut.model_validate(manifest),
        scorecard=[ScorecardOut.model_validate(s) for s in scorecards],
    )

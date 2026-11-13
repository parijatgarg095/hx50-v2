"""Command line:  hx50 build | serve | dedupe | fetch   (hx50 <command> --help for options)."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import date, timedelta

from .config import Settings
from .domain import Mandate, Scorecard

DEFAULTS = Mandate()
HISTORY_DAYS = 215


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="hx50", description="HX-50 index tooling")
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="build both index variants from data/*.csv")
    build.add_argument("--size", type=int, default=DEFAULTS.size, help="number of constituents")
    build.add_argument("--exclude-top", type=int, default=DEFAULTS.exclude_top, help="largest names excluded")
    build.add_argument("--buffer", type=int, default=DEFAULTS.buffer, help="retention buffer in ranks")
    build.add_argument("--top-buffer", type=int, default=DEFAULTS.top_buffer, help="buffer at the top edge (0 = strict)")
    build.add_argument("--base-level", type=float, default=DEFAULTS.base_level)
    build.add_argument("--cost-bps", type=float, default=DEFAULTS.cost_bps, help="assumed one-way cost per side")
    build.set_defaults(handler=_build)

    serve = commands.add_parser("serve", help="serve the API and dashboard")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    serve.set_defaults(handler=_serve)

    dedupe = commands.add_parser("dedupe", help="regenerate data/excluded_classes.csv")
    dedupe.set_defaults(handler=_dedupe)

    fetch = commands.add_parser("fetch", help="download fresh inputs (needs the `fetch` extra)")
    fetch.add_argument("--start", default=(date.today() - timedelta(days=HISTORY_DAYS)).isoformat())
    fetch.add_argument("--end", default=date.today().isoformat())
    fetch.set_defaults(handler=_fetch)

    args = parser.parse_args(argv)
    args.handler(args, Settings.from_env())


def _build(args: argparse.Namespace, settings: Settings) -> None:
    from .pipeline.build import build_index

    mandate = Mandate(size=args.size, exclude_top=args.exclude_top, buffer=args.buffer,
                      top_buffer=args.top_buffer, base_level=args.base_level, cost_bps=args.cost_bps)
    manifest, scorecards = build_index(settings.sources, mandate, settings.db_path)
    print(f"run {manifest.run_id}  {manifest.first_date} -> {manifest.last_date}  "
          f"({manifest.trading_days} trading days, {manifest.universe_size} names)\n")
    print(_scorecard_table(scorecards))


def _serve(args: argparse.Namespace, _: Settings) -> None:
    import uvicorn

    uvicorn.run("hx50.api:create_app", factory=True, host=args.host, port=args.port, reload=args.reload)


def _dedupe(_: argparse.Namespace, settings: Settings) -> None:
    import pandas as pd

    from .pipeline.share_classes import secondary_share_classes

    sources = settings.sources
    excluded = secondary_share_classes(pd.read_csv(sources.shares), pd.read_csv(sources.prices))
    excluded.to_csv(sources.excluded_classes, index=False)
    print(excluded.to_string(index=False) if len(excluded) else "no secondary share classes found")


def _fetch(args: argparse.Namespace, settings: Settings) -> None:
    from .pipeline.fetch import fetch_all
    from .pipeline.share_classes import secondary_share_classes

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    result = fetch_all(args.start, args.end)
    sources = settings.sources
    result.universe.to_csv(settings.universe_csv, index=False)
    result.prices.to_csv(sources.prices, index=False)
    result.shares.to_csv(sources.shares, index=False)
    secondary_share_classes(result.shares, result.prices).to_csv(sources.excluded_classes, index=False)
    print(f"universe {len(result.universe)} · prices {len(result.prices)} rows · shares {len(result.shares)} tickers")


def _scorecard_table(scorecards: list[Scorecard]) -> str:
    rows = [
        ("Rebalances", "rebalances", "{:d}"),
        ("Avg one-way turnover", "avg_turnover", "{:.2%}"),
        ("Total one-way turnover", "total_turnover", "{:.2%}"),
        ("  membership", "membership_turnover", "{:.2%}"),
        ("  reweight", "reweight_turnover", "{:.2%}"),
        ("Names added", "names_added", "{:d}"),
        ("Re-entries", "reentries", "{:d}"),
        ("Gross return", "gross_return", "{:.2%}"),
        ("Est. cost drag", "cost_drag", "{:.2%}"),
        ("Net return", "net_return", "{:.2%}"),
        ("Final level", "final_level", "{:,.2f}"),
    ]
    header = f"{'':<26}" + "".join(f"{s.variant.value:>14}" for s in scorecards)
    lines = [f"{label:<26}" + "".join(f"{fmt.format(getattr(s, key)):>14}" for s in scorecards)
             for label, key, fmt in rows]
    return "\n".join([header, *lines])


if __name__ == "__main__":
    main()

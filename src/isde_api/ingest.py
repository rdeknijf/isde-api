"""Download, validate, then publish the complete current dataset."""

import os
from pathlib import Path

import click

from isde_api.parsers import parse_workbook
from isde_api.sources import fetch_sources
from isde_api.storage import publish


@click.command()
@click.option(
    "--database",
    type=click.Path(path_type=Path),
    default=lambda: os.environ.get("DATABASE_PATH", "data/isde.db"),
    show_default="data/isde.db",
)
@click.option(
    "--raw-dir",
    type=click.Path(path_type=Path),
    default=Path("data/raw"),
    show_default=True,
)
def main(database: Path, raw_dir: Path) -> None:
    """Refresh all five categories. A failed refresh preserves the previous data."""
    try:
        fetched = fetch_sources(raw_dir)
        products = [
            p for source, content in fetched for p in parse_workbook(content, source)
        ]
        changed = publish(database, products, [s for s, _ in fetched])
    except Exception as exc:
        raise click.ClickException(
            f"Import failed; previous data retained: {exc}"
        ) from exc
    click.echo(
        f"Validated {len(products)} records across {len(fetched)} categories. "
        f"Source content {'changed' if changed else 'unchanged'}."
    )


if __name__ == "__main__":
    main()

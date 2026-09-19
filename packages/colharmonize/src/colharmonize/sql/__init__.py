"""Packaged DuckDB SQL modules."""

from importlib import resources


def read_sql(name: str) -> str:
    return resources.files(__package__).joinpath(name).read_text(encoding="utf-8")


__all__ = ["read_sql"]

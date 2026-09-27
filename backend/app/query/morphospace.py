"""Read the precomputed dorso-ventral morphospaces.

The tables are written offline by `morphospace integrate` (packages/morphospace)
and only read here. Every method returns None when the tables have not been
integrated, or when the scope or species is not in them, and the router turns
that into a 404.

Points go out column-wise. A family holds thousands of species seen from two
sides, and one JSON object per point would spend most of the payload
repeating key names.
"""

import logging
import math
from typing import Literal

from ..configs.config import MorphospaceConfig
from ..database.duckdb import DuckDBClient
from ..services.species_pages import SpeciesPageResolver

logger = logging.getLogger(__name__)

ScopeRank = Literal["all", "family", "genus"]
SIDES = ("dorsal", "ventral")

# Four decimals is well under a pixel on any plot these feed, and roughly
# halves the payload against full doubles.
_DECIMALS = 4

_POINT_COLUMNS = (
    "accepted_species",
    "page_key",
    "genus_key",
    "side",
    "n_images",
    "pc1",
    "pc2",
    "pc3",
    "ell_x",
    "ell_y",
    "ell_sx",
    "ell_sy",
    "ell_rho",
    "img_id",
)

_POINT_KEYS = {
    "accepted_species": "species",
    "page_key": "pageKey",
    "genus_key": "genus",
    "side": "side",
    "n_images": "nImages",
    "pc1": "pc1",
    "pc2": "pc2",
    "pc3": "pc3",
    "ell_x": "ellX",
    "ell_y": "ellY",
    "ell_sx": "ellSx",
    "ell_sy": "ellSy",
    "ell_rho": "ellRho",
    "img_id": "imgId",
}


def _clean(value):
    """Round floats and turn NaN into null, which JSON cannot carry."""
    if isinstance(value, float):
        return None if math.isnan(value) else round(value, _DECIMALS)
    return value


def normalize_scope_name(name: str) -> str:
    return " ".join(name.strip().lower().replace("_", " ").split())


def _species_key(name: str) -> str:
    return "_".join(name.strip().lower().replace("_", " ").split())


class MorphospaceQuery:
    def __init__(self, duckdb_client: DuckDBClient):
        self.db = duckdb_client
        self.config = MorphospaceConfig()
        self.pages = SpeciesPageResolver(duckdb_client)

    def available(self) -> bool:
        tables = (
            self.config.scope_table,
            self.config.points_table,
            self.config.species_table,
            self.config.disparity_table,
            self.config.extremes_table,
        )
        return not self.db.missing_tables(list(tables))

    def _rows(self, query: str, params: list) -> list[dict]:
        # Fetched as a frame so the rows are materialized under the client's
        # lock, not read off a shared cursor after it has been released.
        return self.db.execute_prepared_to_pl(query, params).to_dicts()

    # ------------------------------------------------------------------ scope

    def get_scope(self, rank: ScopeRank, name: str) -> dict | None:
        if not self.available():
            return None
        key = "all" if rank == "all" else normalize_scope_name(name)
        scopes = self._rows(
            f"SELECT * FROM {self.config.scope_table} WHERE scope_rank = ? AND scope_key = ?",
            [rank, key],
        )
        if not scopes:
            return None
        scope = scopes[0]
        params = [rank, key]
        points = self._rows(
            f"""
            SELECT {", ".join(_POINT_COLUMNS)}
            FROM {self.config.points_table}
            WHERE scope_rank = ? AND scope_key = ?
            ORDER BY accepted_species, side
            """,
            params,
        )
        extremes = self._rows(
            f"""
            SELECT axis, "end", accepted_species, page_key, side, img_id, value
            FROM {self.config.extremes_table}
            WHERE scope_rank = ? AND scope_key = ?
            ORDER BY axis, "end"
            """,
            params,
        )
        disparity = self._disparity("scope_rank = ? AND scope_key = ?", params).get(
            key, {}
        )
        payload = {
            "scope": self._scope_summary(scope),
            "disparity": disparity,
            "points": {
                _POINT_KEYS[column]: [_clean(row[column]) for row in points]
                for column in _POINT_COLUMNS
            },
            "extremes": [
                {
                    "axis": row["axis"],
                    "end": row["end"],
                    "species": row["accepted_species"],
                    "pageKey": row["page_key"],
                    "side": row["side"],
                    "imgId": row["img_id"],
                    "value": _clean(row["value"]),
                }
                for row in extremes
            ],
            "children": self._children(scope) if rank == "family" else [],
        }
        return payload

    def _scope_summary(self, row: dict) -> dict:
        return {
            "rank": row["scope_rank"],
            "key": row["scope_key"],
            "name": row["scope_name"],
            "parentFamily": row["parent_family"],
            "nSpecies": row["n_species"],
            "nSpeciesBoth": row["n_species_both"],
            "basis": row["basis"],
            "explained": [
                _clean(row["explained_pc1"]),
                _clean(row["explained_pc2"]),
                _clean(row["explained_pc3"]),
            ],
            "integration": {
                "n": row["dv_mantel_n"],
                "r": _clean(row["dv_mantel_r"]),
                "p": _clean(row["dv_mantel_p"]),
            },
            "runId": row["run_id"],
        }

    def _disparity(self, where: str, params: list) -> dict[str, dict]:
        """Disparity rows keyed by scope, then by side."""
        rows = self._rows(
            f"""
            SELECT scope_key, side, n_species, sum_var, rarefied_mean,
                   rarefied_low, rarefied_high, rarefy_k
            FROM {self.config.disparity_table}
            WHERE {where}
            """,
            params,
        )
        out: dict[str, dict] = {}
        for row in rows:
            out.setdefault(row["scope_key"], {})[row["side"]] = {
                "nSpecies": row["n_species"],
                "sumVar": _clean(row["sum_var"]),
                "rarefiedMean": _clean(row["rarefied_mean"]),
                "rarefiedLow": _clean(row["rarefied_low"]),
                "rarefiedHigh": _clean(row["rarefied_high"]),
                "rarefyK": row["rarefy_k"],
            }
        return out

    def _children(self, family: dict) -> list[dict]:
        """The genus scopes of a family, for comparing their disparity."""
        genera = self._rows(
            f"""
            SELECT * FROM {self.config.scope_table}
            WHERE scope_rank = 'genus' AND lower(parent_family) = ?
            ORDER BY scope_name
            """,
            [family["scope_key"]],
        )
        if not genera:
            return []
        disparity = self._disparity(
            f"""scope_rank = 'genus' AND scope_key IN (
                SELECT scope_key FROM {self.config.scope_table}
                WHERE scope_rank = 'genus' AND lower(parent_family) = ?)""",
            [family["scope_key"]],
        )
        return [
            {
                **self._scope_summary(row),
                "disparity": disparity.get(row["scope_key"], {}),
            }
            for row in genera
        ]

    # ---------------------------------------------------------------- species

    def get_species(self, name: str) -> dict | None:
        if not self.available():
            return None
        row = self._species_row(_species_key(name))
        if row is None and self.pages.available():
            # A slug that is not the page key itself (a synonym, another
            # spelling) is resolved to the page it redirects to.
            page = self.pages.page_keys_for_species([name]).get(name)
            if page:
                row = self._species_row(_species_key(page))
        if row is None:
            return None
        return {
            "species": row["accepted_species"],
            "pageKey": row["page_key"],
            "genus": self._scope_ref("genus", row["genus_key"], row["genus_name"]),
            "family": self._scope_ref("family", row["family_key"], row["family_name"]),
            "sides": {
                side: None
                if row[f"{side}_n"] is None
                else {
                    "nImages": row[f"{side}_n"],
                    "dispersion": _clean(row[f"{side}_dispersion"]),
                    "imgId": row[f"{side}_img_id"],
                    "percentile": {
                        "genus": _clean(row[f"{side}_pct_genus"]),
                        "family": _clean(row[f"{side}_pct_family"]),
                    },
                }
                for side in SIDES
            },
            "dvDivergence": _clean(row["dv_divergence"]),
            "dvDivergencePercentile": {
                "genus": _clean(row["dv_pct_genus"]),
                "family": _clean(row["dv_pct_family"]),
            },
        }

    def _species_row(self, key: str) -> dict | None:
        """One species with its percentiles among the species of its genus and family.

        Percentiles are over species measured on the same side, so a species
        with no ventral photographs does not rank others' ventral spread.
        """
        table = self.config.species_table

        def rank(column: str, partition: str) -> str:
            # A species measured alone in its scope ranks against nothing, so
            # it has no percentile rather than percent_rank's 0.
            window = f"(PARTITION BY {partition}, {column} IS NULL)"
            return (
                f"CASE WHEN {column} IS NULL OR count(*) OVER {window} < 2 THEN NULL "
                f"ELSE percent_rank() OVER "
                f"(PARTITION BY {partition}, {column} IS NULL ORDER BY {column}) END"
            )

        rows = self._rows(
            f"""
            WITH ranked AS (
                SELECT *,
                       {rank("dorsal_dispersion", "genus_key")} AS dorsal_pct_genus,
                       {rank("dorsal_dispersion", "family_key")} AS dorsal_pct_family,
                       {rank("ventral_dispersion", "genus_key")} AS ventral_pct_genus,
                       {rank("ventral_dispersion", "family_key")} AS ventral_pct_family,
                       {rank("dv_divergence", "genus_key")} AS dv_pct_genus,
                       {rank("dv_divergence", "family_key")} AS dv_pct_family
                FROM {table}
                WHERE genus_key = (SELECT genus_key FROM {table} WHERE lower(page_key) = ?)
                   OR family_key = (SELECT family_key FROM {table} WHERE lower(page_key) = ?)
            )
            SELECT * FROM ranked WHERE lower(page_key) = ?
            """,
            [key, key, key],
        )
        return rows[0] if rows else None

    def _scope_ref(self, rank: str, key: str | None, name: str | None) -> dict | None:
        if not key:
            return None
        found = self._rows(
            f"SELECT n_species FROM {self.config.scope_table} "
            "WHERE scope_rank = ? AND scope_key = ?",
            [rank, key],
        )
        return {
            "key": key,
            "name": name,
            "available": bool(found),
            "nSpecies": found[0]["n_species"] if found else None,
        }

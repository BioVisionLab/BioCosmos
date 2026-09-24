"""Species recorded in a country and, optionally, one of its ADM1 regions.

The agent search's location filter. Places are taken GADM-first:

* An image whose coordinate `geoharmonize integrate` placed in exactly one
  GADM region is filed under that region's country (GID_0) and ADM1 name,
  whatever the collector wrote. A specimen recorded as Brazil whose
  coordinate falls in Peru counts for Peru.
* Every other image falls back to its recorded locality fields, so coverage
  is never narrower than the raw country filter this replaces.

ADM1 names are matched with `harmonize_core.places.normalize_adm1`, the same
normalization geoharmonize validates against GADM with, so "Sao Paulo State"
finds "São Paulo". The match runs in Python over the distinct names within
the country -- a few dozen values -- rather than as a DuckDB UDF.
"""

import pycountry
from harmonize_core.places import normalize_adm1

from ..configs.config import ImageMetaConfig, LocalityConfig
from ..database.duckdb import DuckDBClient


class LocalitySpecies:
    """Resolve a country and optional ADM1 region to species names.

    The locality table is rebuilt only at startup and the coordinate table
    only with the backend stopped, so the ADM1 names per country are cached
    for the life of the instance.
    """

    def __init__(self, duckdb_client: DuckDBClient):
        self.db_client = duckdb_client
        self.images_table = ImageMetaConfig().table
        locality = LocalityConfig()
        self.locality_table = locality.table
        self.coordinates_table = locality.coordinates_table
        self._adm1_names: dict[str, list[str]] = {}

    def available(self) -> bool:
        return not self.db_client.missing_tables(
            [self.images_table, self.locality_table]
        )

    def _coordinates_available(self) -> bool:
        return not self.db_client.missing_tables([self.coordinates_table])

    def _source(self) -> tuple[str, str, str, bool]:
        """FROM clause, country predicate, ADM1 expression, and whether GADM joins."""
        source = (
            f"{self.images_table} AS i"
            f" JOIN {self.locality_table} AS l ON l.img_id = i.img_id"
        )
        if not self._coordinates_available():
            return source, "upper(l.country_code) = ?", "l.state_province", False
        source += f" LEFT JOIN {self.coordinates_table} AS c ON c.source_id = i.img_id"
        country = (
            "CASE WHEN c.reference_gid_0 IS NOT NULL"
            " THEN c.reference_gid_0 = ? ELSE upper(l.country_code) = ? END"
        )
        adm1 = (
            "CASE WHEN c.reference_gid_0 IS NOT NULL"
            " THEN c.reference_adm1 ELSE l.state_province END"
        )
        return source, country, adm1, True

    @staticmethod
    def _country_params(code: str, gadm: bool) -> list[str]:
        if not gadm:
            return [code]
        country = pycountry.countries.get(alpha_2=code)
        # An alpha-2 code with no ISO entry can still be a recorded code
        # (e.g. XK); GADM never uses it, so the reference branch just misses.
        alpha_3 = country.alpha_3 if country else ""
        return [alpha_3, code]

    def _matching_adm1(self, code: str, state_province: str) -> list[str]:
        """Recorded or GADM ADM1 names in the country that match the request."""
        wanted = normalize_adm1(state_province)
        if wanted is None:
            return []
        if code not in self._adm1_names:
            source, country, adm1, gadm = self._source()
            result = self.db_client.execute_prepared_to_pl(
                f"""
                SELECT DISTINCT {adm1} AS adm1
                FROM {source}
                WHERE {country} AND {adm1} IS NOT NULL
                """,
                self._country_params(code, gadm),
            )
            self._adm1_names[code] = [
                str(name) for name in result["adm1"].to_list() if name
            ]
        return [
            name for name in self._adm1_names[code] if normalize_adm1(name) == wanted
        ]

    def species(
        self,
        country_code: str,
        state_province: str | None = None,
        limit: int = 500,
    ) -> list[str]:
        """Distinct species in the country, narrowed to one ADM1 when given.

        Empty when the ADM1 name matches nothing recorded in that country:
        the filter is a hard constraint, and widening it silently to the whole
        country would answer a different question.
        """
        code = (country_code or "").strip().upper()
        if len(code) != 2 or not code.isalpha():
            raise ValueError("A two-letter country code is required.")

        source, country, adm1, gadm = self._source()
        where = [country, "i.species IS NOT NULL"]
        params = self._country_params(code, gadm)
        if state_province is not None:
            names = self._matching_adm1(code, state_province)
            if not names:
                return []
            where.append(f"{adm1} IN ({', '.join('?' for _ in names)})")
            params += names

        result = self.db_client.execute_prepared_to_pl(
            f"""
            SELECT DISTINCT i.species AS species
            FROM {source}
            WHERE {" AND ".join(where)}
            ORDER BY species
            LIMIT ?
            """,
            [*params, int(limit)],
        )
        if result.is_empty():
            return []
        return [
            str(species).strip()
            for species in result["species"].to_list()
            if species and str(species).strip()
        ]

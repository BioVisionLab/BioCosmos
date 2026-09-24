"""Georeferenced specimens of one species, for the distribution map.

One point per specimen, not per image: a specimen photographed dorsally and
ventrally shares one occurrence (`uuid`), and plotting both would stack two
markers on the same coordinate and double the count in the legend. Images
without an occurrence ID stand on their own.

Optional tables ride along when they exist: the GADM validation from
`geoharmonize integrate` and the recorded locality, so the map can show a
coordinate's recorded locality beside where it actually falls, and the
provenance and institution directory, for the specimen's catalog number and
holding museum. Before any of
them exists its columns are NULL, so the payload keeps one shape.
"""

from pydantic import BaseModel

from ..configs.config import (
    ImageMetaConfig,
    InstitutionConfig,
    LocalityConfig,
    ProvenanceConfig,
)
from ..database.duckdb import DuckDBClient

# Enough for every species in the collection today, and a ceiling on what one
# map will ever try to draw.
MAX_POINTS = 5000


class SpeciesCoordinatePoint(BaseModel):
    imgId: str
    lat: float
    lon: float
    imageCount: int
    # The views photographed, e.g. ["dorsal", "ventral"].
    sides: list[str] = []
    sourceDb: str | None = None
    sex: str | None = None
    catalogNumber: str | None = None
    institutionCode: str | None = None
    institutionName: str | None = None
    validationStatus: str | None = None
    # The locality as the record states it, which the coordinate was checked
    # against, and the GADM region the coordinate actually falls in.
    recordedCountry: str | None = None
    recordedAdm1: str | None = None
    referenceCountry: str | None = None
    referenceAdm1: str | None = None


class SpeciesCoordinatesPayload(BaseModel):
    species: str
    total: int
    truncated: bool
    points: list[SpeciesCoordinatePoint]


def _normalize(name: str) -> str:
    """`Danaus plexippus`, `danaus_plexippus` and `Danaus  plexippus` alike."""
    return "_".join(name.strip().lower().replace("_", " ").split())


def specimen_detail_joins(
    db_client: DuckDBClient, image_alias: str = "i"
) -> tuple[str, str]:
    """The optional per-image joins behind a specimen card, and their columns.

    Validation status, the locality as recorded and as GADM places the
    coordinate, catalog number, and the holding
    museum's name. Each table is joined only when it exists and its columns
    are NULL otherwise, so every caller gets one shape. Shared by the
    distribution map and the specimens tab's cluster map, whose cards show the
    same record.
    """

    def has(table: str) -> bool:
        return not db_client.missing_tables([table])

    locality_config = LocalityConfig()
    locality_table = locality_config.table
    coordinates_table = locality_config.coordinates_table
    provenance_table = ProvenanceConfig().table
    institution_table = InstitutionConfig().table
    joins: list[str] = []
    columns: list[str] = []

    coordinates = has(coordinates_table)
    if coordinates:
        joins.append(
            f"LEFT JOIN {coordinates_table} AS c ON c.source_id = {image_alias}.img_id"
        )
        columns.append("c.validation_status, c.reference_country, c.reference_adm1")
    else:
        columns.append(
            "NULL AS validation_status, NULL AS reference_country,"
            " NULL AS reference_adm1"
        )

    # The locality as recorded, worded as the Image Metadata panel words it:
    # the locality table's country name, since the validation table keeps the
    # source's own value, which is often a bare ISO code.
    recorded_country: list[str] = []
    recorded_adm1: list[str] = []
    if has(locality_table):
        joins.append(
            f"LEFT JOIN {locality_table} AS l ON l.img_id = {image_alias}.img_id"
        )
        recorded_country.append("l.country")
        recorded_adm1.append("l.state_province")
    if coordinates:
        recorded_country.append("c.recorded_country")
        recorded_adm1.append("c.recorded_adm1")
    columns.append(
        f"{_first_of(recorded_country)} AS recorded_country, "
        f"{_first_of(recorded_adm1)} AS recorded_adm1"
    )

    provenance = has(provenance_table)
    if provenance:
        # Collapsed per image, so a duplicated row cannot double a count.
        joins.append(
            "LEFT JOIN (SELECT img_id, any_value(institution_code) AS"
            " institution_code, any_value(catalog_number) AS catalog_number"
            f" FROM {provenance_table} GROUP BY img_id) AS p"
            f" ON p.img_id = {image_alias}.img_id"
        )
        columns.append("p.institution_code, p.catalog_number")
    else:
        columns.append("NULL AS institution_code, NULL AS catalog_number")

    if provenance and has(institution_table):
        joins.append(
            "LEFT JOIN (SELECT code, any_value(name) AS name"
            f" FROM {institution_table} WHERE name IS NOT NULL"
            " GROUP BY code) AS d ON d.code = p.institution_code"
        )
        columns.append("d.name AS institution_name")
    else:
        columns.append("NULL AS institution_name")

    return "\n".join(joins), ", ".join(columns)


class SpeciesCoordinates:
    def __init__(self, duckdb_client: DuckDBClient, limit: int = MAX_POINTS):
        self.db_client = duckdb_client
        self.images_table = ImageMetaConfig().table
        self.limit = limit

    def get(self, species: str) -> dict | None:
        """The species' specimens with a usable coordinate, or None if none."""
        name = _normalize(species or "")
        if not name:
            return None

        join, extra = specimen_detail_joins(self.db_client)

        result = self.db_client.execute_prepared_to_pl(
            f"""
            WITH located AS (
                SELECT
                    i.img_id, i.lat, i.lon, i.source_db, i.sex, i.class_dv,
                    {extra},
                    coalesce(nullif(trim(i.uuid), ''), i.img_id) AS specimen
                FROM {self.images_table} AS i
                {join}
                WHERE regexp_replace(lower(trim(i.species)), '[ _]+', '_', 'g') = ?
                  AND i.lat IS NOT NULL AND i.lon IS NOT NULL
                  AND i.lat BETWEEN -90 AND 90 AND i.lon BETWEEN -180 AND 180
                  AND isfinite(i.lat) AND isfinite(i.lon)
            ),
            sides AS (
                -- Every view the specimen was photographed in, not just the
                -- representative image's.
                SELECT specimen,
                    list_sort(list_distinct(list(lower(trim(class_dv))))) AS sides
                FROM located
                WHERE nullif(trim(class_dv), '') IS NOT NULL
                GROUP BY specimen
            ),
            ranked AS (
                SELECT *,
                    count(*) OVER (PARTITION BY specimen) AS image_count,
                    row_number() OVER (
                        PARTITION BY specimen
                        ORDER BY lower(coalesce(class_dv, '')) = 'dorsal' DESC, img_id
                    ) AS rn
                FROM located
            )
            SELECT img_id, lat, lon, image_count, source_db, sex, s.sides,
                validation_status, recorded_country, recorded_adm1,
                reference_country, reference_adm1,
                institution_code, catalog_number, institution_name,
                count(*) OVER () AS total
            FROM ranked
            LEFT JOIN sides AS s USING (specimen)
            WHERE rn = 1
            ORDER BY img_id
            LIMIT ?
            """,
            [name, int(self.limit)],
        )
        if result.is_empty():
            return None

        rows = result.to_dicts()
        total = int(rows[0]["total"])
        points = [
            SpeciesCoordinatePoint(
                imgId=str(row["img_id"]),
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                imageCount=int(row["image_count"]),
                sides=list(row["sides"] or []),
                sourceDb=_text(row["source_db"]),
                sex=_text(row["sex"]),
                catalogNumber=_text(row["catalog_number"]),
                institutionCode=_text(row["institution_code"]),
                institutionName=_text(row["institution_name"]),
                validationStatus=_text(row["validation_status"]),
                recordedCountry=_text(row["recorded_country"]),
                recordedAdm1=_text(row["recorded_adm1"]),
                referenceCountry=_text(row["reference_country"]),
                referenceAdm1=_text(row["reference_adm1"]),
            )
            for row in rows
        ]
        return SpeciesCoordinatesPayload(
            species=name,
            total=total,
            truncated=total > len(points),
            points=points,
        ).model_dump()


def _first_of(expressions: list[str]) -> str:
    if not expressions:
        return "NULL"
    if len(expressions) == 1:
        return expressions[0]
    return f"coalesce({', '.join(expressions)})"


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

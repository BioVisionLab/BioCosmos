"""Tests for ImagePersistData (services/images.py)."""

import numpy as np
import polars as pl
import pytest
from unittest.mock import MagicMock, patch

from tests.conftest import FakeLanceDB, FakeLanceTable, FakeDuckDBClient


class TestImagePersistData:
    """Unit tests for ImagePersistData search and filter methods."""

    def _make_instance(self, lance_table=None, duckdb=None):
        """Create an ImagePersistData with fakes, patching ImageConfig."""
        table = lance_table or FakeLanceTable()
        lance = FakeLanceDB(table)
        duck = duckdb or FakeDuckDBClient()

        with patch("app.services.images.ImageConfig") as MockCfg:
            MockCfg.return_value.table = "nymphalidae"
            from app.services.images import ImagePersistData

            return ImagePersistData(lance_db=lance, duckdb=duck)

    # ------------------------------------------------------------------
    # get_img_path_by_id
    # ------------------------------------------------------------------

    def test_get_img_path_by_id_found(self):
        df = pl.DataFrame({"img_id": ["img-001"], "img_path": ["/data/img-001.webp"]})
        table = FakeLanceTable(df)
        persist = self._make_instance(lance_table=table)
        result = persist.get_img_path_by_id("img-001")
        assert result == "/data/img-001.webp"

    def test_get_img_path_by_id_not_found(self):
        table = FakeLanceTable(pl.DataFrame())
        persist = self._make_instance(lance_table=table)
        result = persist.get_img_path_by_id("missing")
        assert result is None

    # ------------------------------------------------------------------
    # fetch_image_path
    # ------------------------------------------------------------------

    def test_fetch_image_path_success(self):
        df = pl.DataFrame({"img_id": ["img-001"], "img_path": ["/data/img-001.webp"]})
        table = FakeLanceTable(df)

        with patch("app.services.images.ImageMetaService") as MockMeta:
            MockMeta.return_value.get_image_ids_by_species.return_value = ["img-001"]
            persist = self._make_instance(lance_table=table)
            result = persist.fetch_image_path("danaus plexippus")

        assert result == "/data/img-001.webp"

    def test_fetch_image_path_no_ids(self):
        with patch("app.services.images.ImageMetaService") as MockMeta:
            MockMeta.return_value.get_image_ids_by_species.return_value = []
            persist = self._make_instance()
            result = persist.fetch_image_path("nonexistent")

        assert result is None

    # ------------------------------------------------------------------
    # _filter_by_species
    # ------------------------------------------------------------------

    def test_filter_by_species_keeps_best_per_species(self):
        df = pl.DataFrame(
            {
                "imgId": ["img-001", "img-002", "img-003"],
                "species": ["species_a", "species_a", "species_b"],
                "distance": [0.5, 0.3, 0.1],
            }
        )
        persist = self._make_instance()
        result = persist._filter_by_species(df)

        assert len(result) == 2
        # species_a should keep the one with lower distance (0.3)
        species_a = result.filter(pl.col("species") == "species_a")
        assert species_a["distance"][0] == 0.3

    def test_filter_by_species_links_the_binomial_without_a_run(self):
        """No harmonization loaded: the recorded binomial is the page."""
        df = pl.DataFrame(
            {
                "imgId": ["ssp", "sp", "genus"],
                "species": ["vanessa_cardui_cardui", "vanessa_cardui", "vanessa"],
                "distance": [0.1, 0.2, 0.3],
            }
        )
        persist = self._make_instance()
        result = persist._filter_by_species(df)

        # The subspecies record and the species record share a page.
        assert result["imgId"].to_list() == ["ssp", "genus"]
        assert result["speciesKey"].to_list() == ["vanessa_cardui", None]

    def test_filter_by_species_drops_images_without_a_page(self):
        df = pl.DataFrame(
            {
                "imgId": ["typo", "good", "orphan"],
                "species": ["vanessa_carduii", "vanessa_cardui", "bogus_name"],
                "distance": [0.1, 0.2, 0.3],
            }
        )
        persist = self._make_instance()
        with patch("app.services.images.SpeciesPageResolver") as MockPages:
            MockPages.return_value.available.return_value = True
            MockPages.return_value.page_keys_for_images.return_value = {
                "typo": "vanessa_cardui",
                "good": "vanessa_cardui",
            }
            result = persist._filter_by_species(df)

        # The misspelling links to the species page and, being nearer, stands
        # for it; the unresolved record has no page and is gone.
        assert result["imgId"].to_list() == ["typo"]
        assert result["speciesKey"].to_list() == ["vanessa_cardui"]

    def test_filter_by_species_handles_none(self):
        persist = self._make_instance()
        result = persist._filter_by_species(None)
        assert result is None

    # ------------------------------------------------------------------
    # _query_embedding with distance filter
    # ------------------------------------------------------------------

    def test_query_embedding_distance_filter(self):
        """Results above max_distance should be filtered out."""
        df = pl.DataFrame(
            {
                "img_id": ["img-001", "img-002", "img-003"],
                "_distance": [0.1, 0.5, 1.5],
            }
        )
        table = FakeLanceTable(df)
        persist = self._make_instance(lance_table=table)

        result = persist._query_embedding(
            query_vector=np.zeros(512),
            vector_column_name="clip_embeddings",
            limit=10,
            max_distance=0.8,
        )
        assert result is not None
        assert len(result) == 2  # only 0.1 and 0.5

    def test_query_embedding_no_distance_filter(self):
        """Without max_distance, all results should pass."""
        df = pl.DataFrame(
            {
                "img_id": ["img-001", "img-002"],
                "_distance": [0.1, 1.9],
            }
        )
        table = FakeLanceTable(df)
        persist = self._make_instance(lance_table=table)

        result = persist._query_embedding(
            query_vector=np.zeros(512),
            vector_column_name="clip_embeddings",
            limit=10,
        )
        assert result is not None
        assert len(result) == 2

    def test_query_embedding_deduplicates_by_img_id(self):
        """Duplicate img_ids should be removed."""
        df = pl.DataFrame(
            {
                "img_id": ["img-001", "img-001"],
                "_distance": [0.1, 0.2],
            }
        )
        table = FakeLanceTable(df)
        persist = self._make_instance(lance_table=table)

        result = persist._query_embedding(
            query_vector=np.zeros(512),
            vector_column_name="clip_embeddings",
            limit=10,
        )
        assert len(result) == 1

    # ------------------------------------------------------------------
    # SpeciesImage model
    # ------------------------------------------------------------------

    def test_species_image_to_dict(self):
        from app.services.images import SpeciesImage

        si = SpeciesImage(species="danaus_plexippus", imageIds=["img-001", "img-002"])
        d = si.to_dict()
        assert d["species"] == "danaus_plexippus"
        assert len(d["imageIds"]) == 2


class RecordingSearch:
    """Search builder that records filters and serves canned rows per call."""

    def __init__(self, table, data: pl.DataFrame):
        self.table = table
        self.data = data
        self.where_clause = None
        self.limit_value = None
        self.nprobes_value = None
        self.refine_factor_value = None

    def distance_type(self, _dtype):
        return self

    def nprobes(self, n):
        self.nprobes_value = n
        return self

    def refine_factor(self, n):
        self.refine_factor_value = n
        return self

    def select(self, columns):
        self.table.selects.append(columns)
        return self

    def where(self, clause, prefilter=False):
        self.where_clause = clause
        return self

    def limit(self, n):
        self.limit_value = n
        return self

    def to_polars(self):
        self.table.searches.append(self)
        self.table.calls.append((self.where_clause, self.limit_value))
        data = self.data
        if self.where_clause and " IN (" in self.where_clause:
            listed = self.where_clause.split("IN (", 1)[1].rstrip(")")
            ids = [token.strip().strip("'") for token in listed.split(",")]
            data = data.filter(pl.col("img_id").is_in(ids))
        return data.head(self.limit_value) if self.limit_value else data


class RecordingTable:
    def __init__(self, data: pl.DataFrame):
        self.data = data
        self.calls: list[tuple[str | None, int | None]] = []
        self.selects: list[list[str]] = []
        self.searches: list["RecordingSearch"] = []

    def search(self, query=None, vector_column_name=None):
        return RecordingSearch(self, self.data)


class TestAnnSearchParameters:
    """Every vector search asks for the index to be probed and re-ranked.

    Both calls are no-ops while the column is unindexed, which is why they can
    be set unconditionally -- but if they were ever dropped, the day an IVF-PQ
    index is built the endpoint would quietly start returning a *different*
    set of neighbours rather than the same set faster, because product
    quantization changes the ranking it is not refined against.
    """

    def test_search_sets_nprobes_and_refine_factor(self):
        from app.services.images import (
            NPROBES,
            REFINE_FACTOR,
            ImagePersistData,
        )

        table = RecordingTable(
            pl.DataFrame({"img_id": ["a", "b"], "_distance": [0.1, 0.2]})
        )
        persist = ImagePersistData.__new__(ImagePersistData)
        persist.db_table = table
        persist.logger = MagicMock()

        persist._vector_search(
            query_vector=np.zeros(4),
            vector_column_name="unicom_embeddings",
            limit=10,
        )

        assert len(table.searches) == 1
        search = table.searches[0]
        assert search.nprobes_value == NPROBES
        assert search.refine_factor_value == REFINE_FACTOR


class TestAllowlistedVectorSearch:
    """Allowlists must never become one unbounded `IN (...)` filter."""

    def _make(self, table):
        from app.services.images import ImagePersistData

        persist = ImagePersistData.__new__(ImagePersistData)
        persist.db_table = table
        persist.logger = MagicMock()
        return persist

    def _ranked_table(self, n: int) -> RecordingTable:
        return RecordingTable(
            pl.DataFrame(
                {
                    "img_id": [f"img-{i:05d}" for i in range(n)],
                    "_distance": [i / n for i in range(n)],
                }
            )
        )

    def test_small_allowlist_is_prefiltered_in_bounded_chunks(self):
        from app.services.images import PREFILTER_CHUNK_SIZE

        table = self._ranked_table(1_000)
        allowed = [f"img-{i:05d}" for i in range(0, 1_000, 2)]  # 500 ids
        result = self._make(table)._query_embedding(
            np.zeros(4), "clip_embeddings", limit=10, filter_img_ids=allowed
        )

        assert len(table.calls) == -(-len(allowed) // PREFILTER_CHUNK_SIZE)
        assert all(
            clause.count(",") < PREFILTER_CHUNK_SIZE for clause, _ in table.calls
        )
        assert result.sort("distance")["imgId"].to_list() == allowed[:10]

    def test_large_allowlist_is_postfiltered_without_in_clause(self):
        from app.services.images import POSTFILTER_POOL_SIZES, PREFILTER_MAX_IDS

        table = self._ranked_table(60_000)
        # Every 20th image: a 5k pool holds only 250 matches, so it must grow.
        allowed = [f"img-{i:05d}" for i in range(0, 60_000, 20)]
        assert len(allowed) > PREFILTER_MAX_IDS

        result = self._make(table)._query_embedding(
            np.zeros(4), "clip_embeddings", limit=500, filter_img_ids=allowed
        )

        assert all(clause is None for clause, _ in table.calls)
        assert [limit for _, limit in table.calls] == list(POSTFILTER_POOL_SIZES)
        assert result.height == 500
        assert result.sort("distance")["imgId"].to_list() == allowed[:500]

    def test_vector_search_projects_only_the_image_id(self):
        table = self._ranked_table(10)
        self._make(table)._query_embedding(np.zeros(4), "clip_embeddings", limit=5)
        assert table.selects == [["img_id"]]

    def test_unicom_embeddings_are_fetched_in_one_projected_read(self):
        table = RecordingTable(
            pl.DataFrame(
                {
                    "img_id": ["a", "b", "c"],
                    "img_path": ["/a.webp", "/b.webp", "/c.webp"],
                    "unicom_embeddings": [[1.0, 0.0], [0.0, 1.0], [5.0, 5.0]],
                }
            )
        )
        embeddings = self._make(table)._query_unicom_embeddings(["a", "b", "a"])

        assert len(table.calls) == 1
        assert table.selects == [["img_id", "unicom_embeddings"]]
        assert embeddings.shape == (2, 2)
        np.testing.assert_allclose(embeddings.mean(axis=0), [0.5, 0.5])


class TestFindSimilarImagesPoolGrowth:
    """A prolific reference species must not crowd out every neighbour."""

    def test_pool_widens_past_the_reference_species(self):
        from app.services.images import ImagePersistData

        persist = ImagePersistData.__new__(ImagePersistData)
        persist.logger = MagicMock()
        persist._query_unicom_embeddings = MagicMock(return_value=np.ones((2, 4)))
        pools = []

        def query_embedding(query_vector, vector_column_name, limit, filter_img_ids):
            pools.append(limit)
            # The nearest 500 images all belong to the reference species.
            n_other = 0 if limit <= 500 else 30
            return pl.DataFrame(
                {
                    "imgId": [f"img-{i}" for i in range(500 + n_other)],
                    "distance": [i / 1000 for i in range(500 + n_other)],
                }
            )

        def merge(results):
            species = ["danaus_plexippus"] * 499 + ["danaus_plexippus_plexippus"]
            species += [f"other_{i}" for i in range(results.height - 500)]
            return results.with_columns(pl.Series("species", species))

        persist._query_embedding = query_embedding
        persist._merge_result_with_metadata = merge

        result = persist.find_similar_images(
            ["ref"], 500, exclude_species="Danaus plexippus", min_species=20
        )

        assert pools == [500, 5_000]
        assert result.height == 30
        assert all(name.startswith("other_") for name in result["species"])

    def test_excludes_multiple_references_and_their_subspecies(self):
        from app.services.images import ImagePersistData

        persist = ImagePersistData.__new__(ImagePersistData)
        persist.logger = MagicMock()
        persist._query_unicom_embeddings = MagicMock(return_value=np.ones((2, 4)))
        persist._query_embedding = MagicMock(
            return_value=pl.DataFrame(
                {
                    "imgId": ["a", "b", "c", "d"],
                    "distance": [0.1, 0.2, 0.3, 0.4],
                }
            )
        )
        persist._merge_result_with_metadata = lambda rows: rows.with_columns(
            pl.Series(
                "species",
                [
                    "danaus_plexippus",
                    "Danaus erippus",
                    "danaus_erippus_subspecies",
                    "vanessa_cardui",
                ],
            )
        )
        result = persist.find_similar_images(
            ["ref-a", "ref-b"],
            exclude_species=["Danaus plexippus", "danaus_erippus"],
            raise_on_error=True,
        )
        assert result["species"].to_list() == ["vanessa_cardui"]

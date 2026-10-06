"""Does visual similarity recover published mimicry pairs?

Every species in the collection is ranked the way the species pages' "similar species"
list ranks them: the mean of a species' normalized UNICOM image embeddings on one side,
re-normalized, is the query, and each species scores its nearest image on either side,
as `similarity run` does.

Unlike the stored `species_similarity` table, which keeps the top ten, ranks here
cover every species, so a partner outside the top ten still has a measured rank.
Species are accepted names, so subspecies and synonyms do not split a species.
Only the Lance table and DuckDB are read; nothing is written outside `analyses/`.
"""

from __future__ import annotations

import gc
import os
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

import lancedb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import yaml
from dotenv import dotenv_values
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.patches import Patch
from PIL import Image

from analyses.helpers.morphospace import image_directory, square_image
from analyses.helpers.publication import (
    AnalysisError,
    Settings,
    connect,
    image_table,
    project_root,
    table,
    text,
    unique_key,
)

SIDES = ("dorsal", "ventral")
VISUAL_COLUMN = "unicom_embeddings"
# Hardcoded in the backend (backend/app/query/precomputed_similarity.py).
SIMILARITY_TABLE = "species_similarity"
READ_BATCH_SIZE = 50_000
PAIR_COLUMNS = {
    "Species 1": "species_a",
    "Species 2": "species_b",
    "Mimicry type": "mimicry_type",
    "Notes": "notes",
    "Key publication(s)": "publications",
    "DOI(s)": "dois",
}
# Recorded in the pairs table for readers; the notebook recomputes it from the collection.
AVAILABILITY_COLUMN = "Availability"
AVAILABILITY = ("Available", "Unavailable")
SIDE_COLORS = {"dorsal": "#1b9e77", "ventral": "#d95f02"}
# The site lists a species' ten most similar species.
SITE_TOP = 10
HIGHLIGHT = "#fff1c2"
# Representative images beside each pair label, in points; pixels kept for print.
THUMBNAIL = 54
THUMBNAIL_GAP = 6
THUMBNAIL_PIXELS = 320


@dataclass(frozen=True)
class LanceSource:
    database: Path
    table: str


@dataclass(frozen=True)
class Retrieval:
    """Scores of every collection species (columns) for each query species (rows)."""

    mode: str
    queries: tuple[str, ...]
    species: np.ndarray
    scores: np.ndarray


def load_pairs(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = set(PAIR_COLUMNS) - set(frame.columns)
    if missing:
        raise AnalysisError(f"{path.name} is missing columns: {sorted(missing)}")
    recorded = (
        frame[AVAILABILITY_COLUMN].str.strip()
        if AVAILABILITY_COLUMN in frame
        else pd.Series(pd.NA, index=frame.index, dtype="string")
    )
    if recorded.notna().any() and not recorded.dropna().isin(AVAILABILITY).all():
        raise AnalysisError(f"{AVAILABILITY_COLUMN} must be one of {AVAILABILITY}.")
    frame = frame.rename(columns=PAIR_COLUMNS)[list(PAIR_COLUMNS.values())]
    frame["recorded_availability"] = recorded.to_numpy()
    for column in PAIR_COLUMNS.values():
        frame[column] = frame[column].str.strip()
    if (frame[["species_a", "species_b"]] == "").any().any():
        raise AnalysisError(f"{path.name} has a pair with a blank species.")
    if (frame["species_a"] == frame["species_b"]).any():
        raise AnalysisError(f"{path.name} pairs a species with itself.")
    key = frame[["species_a", "species_b"]].apply(sorted, axis=1).str.join("|")
    if key.duplicated().any():
        raise AnalysisError(f"{path.name} lists a pair twice: {sorted(key[key.duplicated()])}")
    frame.insert(0, "pair", [pair_label(row) for row in frame.itertuples()])
    return frame


def abbreviate(species: str) -> str:
    genus, _, epithet = species.partition(" ")
    return f"{genus[0]}. {epithet}"


def type_code(mimicry_type: str) -> str:
    kind = mimicry_type.lower()
    code = "M" if kind.startswith("müll") else "B" if kind.startswith("bates") else "?"
    return f"{code}*" if "context" in kind else code


def pair_label(row) -> str:
    return (
        f"{abbreviate(row.species_a)} – {abbreviate(row.species_b)} ({type_code(row.mimicry_type)})"
    )


def lance_source(root: Path | None = None) -> LanceSource:
    """Resolve the backend's Lance image table without importing backend code."""
    root = project_root(root)
    backend = root / "backend"
    env = {**dotenv_values(backend / ".env"), **os.environ}
    with (backend / "app/configs/config.yaml").open() as handle:
        config = yaml.safe_load(handle)
    directory = env.get("LANCE_DIR")
    if not directory:
        raise AnalysisError("Set LANCE_DIR in backend/.env or the kernel environment.")
    path = Path(directory).expanduser()
    if not path.is_absolute():
        path = backend / path
    return LanceSource((path / config["db"]["lance"]["file"]).resolve(), config["images"]["table"])


def open_lance(source: LanceSource):
    """Open the image table at its current version; never create or modify it."""
    if not source.database.is_dir():
        raise AnalysisError(f"Lance database not found: {source.database}")
    lance = lancedb.connect(str(source.database)).open_table(source.table)
    lance.checkout(lance.version)
    return lance


def species_images(settings: Settings) -> pd.DataFrame:
    """One row per dorsal or ventral image with a MATCHED accepted species.

    Species use `accepted_species_name`, falling back to `accepted_name` only at
    species rank, as the composition figures do. `recorded` keeps the image's own
    species name, lowercased, to resolve published names the accepted taxonomy
    renamed. Reading `image_meta` keeps the excluded families out.
    """
    with connect(settings) as connection:
        images = image_table(connection, settings, ("class_dv", "species"))
        taxonomy = table(
            connection,
            settings,
            "taxonomy",
            ("img_id", "update_status", "accepted_species_name", "accepted_rank", "accepted_name"),
        )
        unique_key(connection, taxonomy, "img_id")
        frame = connection.execute(
            f"""
            SELECT img_id, t.species, lower({text("i.class_dv")}) AS side,
                lower(replace({text("i.species")}, '_', ' ')) AS recorded
            FROM {images} i JOIN (
                SELECT img_id, coalesce(
                    {text("accepted_species_name")},
                    CASE WHEN lower(accepted_rank) = 'species'
                        THEN {text("accepted_name")} END
                ) AS species
                FROM {taxonomy} WHERE update_status = 'MATCHED'
            ) t USING (img_id)
            WHERE t.species IS NOT NULL AND lower({text("i.class_dv")}) IN ('dorsal', 'ventral')
            ORDER BY img_id
            """
        ).df()
    if frame.empty:
        raise AnalysisError("No dorsal or ventral images have a matched accepted species.")
    frame["genus"] = frame["species"].str.split(" ").str[0]
    return frame


def resolve_species(name: str, images: pd.DataFrame) -> tuple[str | None, str]:
    """The accepted species a published name stands for in the collection.

    A published name that is itself accepted stands for itself. Otherwise the
    accepted species of images recorded under that name (subspecies included)
    stand in, but only when they agree on one.
    """
    if (images["species"] == name).any():
        return name, "accepted name"
    recorded = images["recorded"].fillna("")
    lowered = name.lower()
    matches = images.loc[
        (recorded == lowered) | recorded.str.startswith(f"{lowered} "), "species"
    ].unique()
    if len(matches) == 1:
        return str(matches[0]), "recorded name → accepted species"
    if len(matches) > 1:
        return None, f"recorded name, ambiguous: {', '.join(sorted(matches))}"
    return None, "not in collection"


def coverage(pairs: pd.DataFrame, images: pd.DataFrame) -> pd.DataFrame:
    """Accepted species and images per side for every pair member.

    A pair is tested only when both members resolve to distinct species with images.
    """
    counts = images.groupby(["species", "side"]).size().unstack(fill_value=0)
    counts = counts.reindex(columns=list(SIDES), fill_value=0)
    rows = []
    for pair in pairs.itertuples():
        for member, published in (("A", pair.species_a), ("B", pair.species_b)):
            accepted, resolution = resolve_species(published, images)
            sides = counts.loc[accepted] if accepted is not None else None
            rows.append(
                {
                    "pair": pair.pair,
                    "member": member,
                    "published_species": published,
                    "accepted_species": accepted,
                    "resolution": resolution,
                    **{
                        f"{side}_images": 0 if sides is None else int(sides[side]) for side in SIDES
                    },
                }
            )
    frame = pd.DataFrame(rows)
    frame["in_collection"] = frame["accepted_species"].notna()
    distinct = frame.groupby("pair")["accepted_species"].transform("nunique") == 2
    frame["pair_tested"] = frame.groupby("pair")["in_collection"].transform("all") & distinct
    return frame


def tested_pairs(pairs: pd.DataFrame, covered: pd.DataFrame) -> pd.DataFrame:
    """Tested pairs with each member's accepted species as `accepted_a`/`accepted_b`."""
    tested = covered.loc[covered["pair_tested"]]
    accepted = tested.pivot(index="pair", columns="member", values="accepted_species")
    accepted = accepted.rename(columns={"A": "accepted_a", "B": "accepted_b"})
    return pairs.merge(accepted, left_on="pair", right_index=True).reset_index(drop=True)


def availability(pairs: pd.DataFrame, covered: pd.DataFrame) -> pd.Series:
    """ "Available" when both members resolve to distinct species with images."""
    tested = pairs["pair"].isin(covered.loc[covered["pair_tested"], "pair"])
    return pd.Series(np.where(tested, *AVAILABILITY), index=pairs.index)


def load_embeddings(lance, column: str, img_ids: pd.Series) -> np.ndarray:
    """L2-normalized embeddings aligned to `img_ids`; every image must have a vector."""
    if column not in lance.schema.names:
        raise AnalysisError(f"The Lance table has no {column} column.")
    position = pd.Index(img_ids)
    if not position.is_unique:
        raise AnalysisError("Image IDs must be unique.")
    out: np.ndarray | None = None
    filled = np.zeros(len(position), dtype=bool)
    query = lance.search().select(["img_id", column]).limit(None)
    for batch in query.to_batches(READ_BATCH_SIZE):
        if batch.num_rows == 0:
            continue
        index = position.get_indexer(batch.column("img_id").to_pylist())
        keep = index >= 0
        if not keep.any():
            continue
        values = batch.column(column)
        width = values.type.list_size
        if out is None:
            out = np.zeros((len(position), width), dtype=np.float32)
        vectors = values.flatten().to_numpy(zero_copy_only=False).reshape(-1, width)
        if filled[index[keep]].any():
            raise AnalysisError(f"The Lance table repeats image IDs in {column}.")
        out[index[keep]] = vectors[keep]
        filled[index[keep]] = True
    if out is None or not filled.all():
        raise AnalysisError(
            f"{int((~filled).sum()):,} images have no {column} vector in the Lance table."
        )
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    if not np.isfinite(out).all() or (norms == 0).any():
        raise AnalysisError(f"{column} holds zero or non-finite vectors.")
    out /= norms
    return out


def species_codes(images: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Sorted collection species and each image's index into them."""
    codes, species = pd.factorize(images["species"], sort=True)
    return np.asarray(species, dtype=object), codes


def nearest_image_scores(
    queries: np.ndarray, embeddings: np.ndarray, codes: np.ndarray, n_species: int
) -> np.ndarray:
    """Each query's highest cosine similarity to any image of each species (Q × S)."""
    order = np.argsort(codes, kind="stable")
    sorted_codes = codes[order]
    if not np.array_equal(np.unique(sorted_codes), np.arange(n_species)):
        raise AnalysisError("Every collection species needs at least one image.")
    starts = np.flatnonzero(np.r_[True, np.diff(sorted_codes) != 0])
    similarity = (embeddings @ queries.T)[order]
    return np.maximum.reduceat(similarity, starts, axis=0).T


def visual_retrieval(images: pd.DataFrame, embeddings: np.ndarray, side: str, queries) -> Retrieval:
    """Rank all species against each query species' centroid on one side."""
    species, codes = species_codes(images)
    rows = []
    for name in queries:
        mask = (images["species"] == name).to_numpy() & (images["side"] == side).to_numpy()
        if not mask.any():
            raise AnalysisError(f"{name} has no {side} images to form a centroid.")
        centroid = embeddings[mask].mean(axis=0)
        rows.append(centroid / np.linalg.norm(centroid))
    scores = nearest_image_scores(np.stack(rows), embeddings, codes, len(species))
    return Retrieval(f"Visual ({side})", tuple(queries), species, scores)


def representatives(
    images: pd.DataFrame,
    embeddings: np.ndarray,
    species,
    root: Path | None = None,
    side: str = "dorsal",
) -> pd.DataFrame:
    """Each species' image nearest its own centroid on `side`, with a file on disk.

    Images are tried from nearest outward, so a missing processed file falls back
    to the next most typical image rather than failing the figure.
    """
    directory, extension = image_directory(project_root(root))
    rows = []
    for name in species:
        mask = (images["species"] == name).to_numpy() & (images["side"] == side).to_numpy()
        if not mask.any():
            raise AnalysisError(f"{name} has no {side} images to represent it.")
        vectors = embeddings[mask]
        centroid = vectors.mean(axis=0)
        similarity = vectors @ (centroid / np.linalg.norm(centroid))
        candidates = images.loc[mask, "img_id"].to_numpy()[np.argsort(-similarity)]
        found = next(
            (
                str(img_id)
                for img_id in candidates
                if (directory / f"{img_id}.{extension}").is_file()
                or (directory / "thumbnails" / f"{img_id}_thumbnail.{extension}").is_file()
            ),
            None,
        )
        if found is None:
            raise AnalysisError(f"No {side} image of {name} is on disk under {directory}.")
        rows.append({"species": name, "side": side, "img_id": found})
    return pd.DataFrame(rows)


def thumbnail(img_id: str, root: Path | None = None) -> np.ndarray:
    """A representative image on a transparent square, downsampled for print."""
    directory, extension = image_directory(project_root(root))
    image = Image.fromarray(square_image(img_id, directory, extension))
    if image.width > THUMBNAIL_PIXELS:
        image = image.resize((THUMBNAIL_PIXELS, THUMBNAIL_PIXELS), Image.Resampling.LANCZOS)
    return np.asarray(image)


def recovered_pairs(ranks: pd.DataFrame, top: int = SITE_TOP) -> pd.DataFrame:
    """Pairs whose members are in each other's top `top` on at least one side.

    Requiring both directions keeps one-sided hits, such as a common species that
    appears near many queries, from counting as recovery.
    """
    within = ranks.assign(within=ranks["partner_rank"] <= top)
    mutual = within.groupby(["pair", "mode"])["within"].all().unstack("mode")
    mutual.columns = [
        f"mutual_top{top}_{column.removeprefix('Visual (').removesuffix(')')}"
        for column in mutual.columns
    ]
    mutual["recovered"] = mutual.any(axis=1)
    order = pd.unique(ranks["pair"])
    return mutual.reindex(order).reset_index()


def percentile_matrix(retrieval: Retrieval) -> np.ndarray:
    """Each species' percentile among the query's other species: 1 is the nearest.

    The query species itself is NaN. Rank r of n others maps to 1 - (r - 1) / (n - 1).
    """
    lookup = {name: index for index, name in enumerate(retrieval.species)}
    n_others = len(retrieval.species) - 1
    out = np.empty(retrieval.scores.shape, dtype=float)
    for row, query in enumerate(retrieval.queries):
        scores = retrieval.scores[row].astype(float).copy()
        scores[lookup[query]] = -np.inf
        ranks = np.empty(len(scores))
        ranks[np.argsort(-scores, kind="stable")] = np.arange(1, len(scores) + 1)
        out[row] = 1 - (ranks - 1) / (n_others - 1)
        out[row, lookup[query]] = np.nan
    return out


def directions(pairs: pd.DataFrame) -> pd.DataFrame:
    """Both query directions of every pair, as accepted species."""
    forward = pairs.assign(direction="A→B", query=pairs["accepted_a"], partner=pairs["accepted_b"])
    reverse = pairs.assign(direction="B→A", query=pairs["accepted_b"], partner=pairs["accepted_a"])
    return pd.concat([forward, reverse], ignore_index=True)[
        ["pair", "mimicry_type", "direction", "query", "partner"]
    ]


def partner_ranks(retrieval: Retrieval, pairs: pd.DataFrame) -> pd.DataFrame:
    """The partner's score, rank among the query's other species, and percentile."""
    lookup = {name: index for index, name in enumerate(retrieval.species)}
    rows = directions(pairs)
    n_others = len(retrieval.species) - 1
    records = []
    for row in rows.itertuples():
        scores = retrieval.scores[retrieval.queries.index(row.query)]
        query, partner = lookup[row.query], lookup[row.partner]
        others = np.delete(scores, query)
        rank = 1 + int((others > scores[partner]).sum())
        records.append(
            {
                "mode": retrieval.mode,
                "partner_score": float(scores[partner]),
                "partner_rank": rank,
                "species_compared": n_others,
                "partner_percentile": 1 - (rank - 1) / (n_others - 1),
            }
        )
    return pd.concat([rows, pd.DataFrame(records)], axis=1)


def site_listed(settings: Settings, ranks: pd.DataFrame) -> pd.Series:
    """Whether the site's stored top-ten similar species list holds the partner.

    The stored table keys species by the recorded name, lowercased with underscores;
    NA when the table is absent or the mode is not visual.
    """
    with connect(settings) as connection:
        exists = connection.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
            [SIMILARITY_TABLE],
        ).fetchone()[0]
        stored = (
            connection.execute(
                f"SELECT species, side, lower(replace(similar_species, ' ', '_')) AS similar "
                f"FROM {SIMILARITY_TABLE}"
            ).df()
            if exists
            else None
        )
    if stored is None:
        return pd.Series(pd.NA, index=ranks.index, dtype="boolean")
    listed = set(stored.itertuples(index=False, name=None))
    values = []
    for row in ranks.itertuples():
        side = row.mode.removeprefix("Visual (").removesuffix(")")
        if side not in SIDES:
            values.append(pd.NA)
            continue
        key = (
            row.query.lower().replace(" ", "_"),
            side,
            row.partner.lower().replace(" ", "_"),
        )
        values.append(key in listed)
    return pd.Series(values, index=ranks.index, dtype="boolean")


def null_pools(retrieval: Retrieval, rows: pd.DataFrame, null: str) -> list[np.ndarray]:
    """Candidate partners each row's null draws from.

    "Random": any other collection species. "Congeners": for a pair within one genus,
    the query's other congeners, since related species look alike regardless of
    mimicry; a pair across genera keeps the random pool.
    """
    genus = np.array([name.split(" ")[0] for name in retrieval.species])
    lookup = {name: index for index, name in enumerate(retrieval.species)}
    everyone = np.arange(len(retrieval.species))
    pools = []
    for row in rows.itertuples():
        query = lookup[row.query]
        pool = everyone
        if null == "Congeners" and row.query.split(" ")[0] == row.partner.split(" ")[0]:
            pool = np.flatnonzero(genus == genus[query])
        pools.append(pool[pool != query])
    return pools


def permutation_test(
    retrieval: Retrieval,
    ranks: pd.DataFrame,
    n_permutations: int = 10_000,
    seed: int = 0,
    nulls: tuple[str, ...] = ("Random", "Congeners"),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Mean partner percentile against partners drawn from each null pool.

    Each permutation keeps every query and replaces its partner with a species drawn
    from that row's pool. The one-sided p-value counts null means at least as high as
    the observed mean, with the observed arrangement counted once.
    """
    rows = ranks.loc[ranks["mode"] == retrieval.mode].reset_index(drop=True)
    percentiles = percentile_matrix(retrieval)
    observed = float(rows["partner_percentile"].mean())
    rng = np.random.default_rng(seed)
    summaries, distributions = [], []
    for null in nulls:
        draws = np.empty((len(rows), n_permutations))
        for index, (row, pool) in enumerate(
            zip(rows.itertuples(), null_pools(retrieval, rows, null), strict=True)
        ):
            row_percentiles = percentiles[retrieval.queries.index(row.query)]
            draws[index] = row_percentiles[rng.choice(pool, size=n_permutations)]
        means = draws.mean(axis=0)
        summaries.append(
            {
                "mode": retrieval.mode,
                "null": null,
                "query_rows": len(rows),
                "congeneric_rows": int(
                    sum(r.query.split(" ")[0] == r.partner.split(" ")[0] for r in rows.itertuples())
                ),
                "observed_mean_percentile": observed,
                "null_mean": float(means.mean()),
                "null_low_2_5": float(np.quantile(means, 0.025)),
                "null_high_97_5": float(np.quantile(means, 0.975)),
                "p_value": (1 + int((means >= observed).sum())) / (n_permutations + 1),
                "permutations": n_permutations,
                "seed": seed,
            }
        )
        distributions.append(pd.DataFrame({"mode": retrieval.mode, "null": null, "mean": means}))
    return pd.DataFrame(summaries), pd.concat(distributions, ignore_index=True)


@dataclass(frozen=True)
class MimicryResults:
    """Everything the mimicry figures draw and export."""

    pairs: pd.DataFrame
    # Members of tested pairs only; `untested` holds the pairs left out and why.
    coverage: pd.DataFrame
    untested: pd.DataFrame
    tested: pd.DataFrame
    ranks: pd.DataFrame
    recovery: pd.DataFrame
    permutations: pd.DataFrame
    representatives: pd.DataFrame
    n_species: int
    n_images: int
    lance_version: int

    def counts(self) -> pd.DataFrame:
        """How many published pairs and species were tested, against the collection."""
        published = set(self.pairs["species_a"]) | set(self.pairs["species_b"])
        tested = set(self.tested["accepted_a"]) | set(self.tested["accepted_b"])
        return pd.DataFrame(
            [
                ("Published pairs", len(self.pairs)),
                ("Tested pairs", len(self.tested)),
                ("Published species", len(published)),
                ("Tested species (accepted names)", len(tested)),
                ("Species ranked in the collection", self.n_species),
                ("Images ranked", self.n_images),
            ],
            columns=["count", "value"],
        )

    def exports(self) -> dict[str, pd.DataFrame]:
        return {
            "counts": self.counts(),
            "coverage": self.coverage,
            "ranks": self.ranks,
            "recovery": self.recovery,
            "permutations": self.permutations,
            "representatives": self.representatives,
        }

    def recovered(self) -> set[str]:
        return set(self.recovery.loc[self.recovery["recovered"], "pair"])

    def pictures(self, root: Path | None = None) -> dict[str, np.ndarray]:
        return {
            row.species: thumbnail(row.img_id, root) for row in self.representatives.itertuples()
        }


def mimicry_results(
    settings: Settings,
    root: Path | None = None,
    n_permutations: int = 10_000,
    seed: int = 0,
) -> MimicryResults:
    """Rank, test, and pick representative images for every testable published pair."""
    pairs = load_pairs(project_root(root) / "analyses/data/mimicry_pairs.csv")
    images = species_images(settings)
    covered = coverage(pairs, images)
    tested = tested_pairs(pairs, covered)
    pairs["availability"] = availability(pairs, covered)
    in_collection = covered["pair_tested"]
    untested = covered.loc[~in_collection]
    queries = sorted(set(tested["accepted_a"]) | set(tested["accepted_b"]))
    lance = open_lance(lance_source(root))
    embeddings = load_embeddings(lance, VISUAL_COLUMN, images["img_id"])
    retrievals = [visual_retrieval(images, embeddings, side, queries) for side in SIDES]
    # Each species' dorsal image nearest its own centroid, drawn beside the pair labels.
    examples = representatives(images, embeddings, queries, root)
    del embeddings
    gc.collect()
    ranks = pd.concat(
        [partner_ranks(retrieval, tested) for retrieval in retrievals], ignore_index=True
    )
    ranks["site_listed"] = site_listed(settings, ranks)
    permutations = pd.concat(
        [permutation_test(retrieval, ranks, n_permutations, seed)[0] for retrieval in retrievals],
        ignore_index=True,
    )
    return MimicryResults(
        pairs,
        covered.loc[in_collection].drop(columns=["in_collection", "pair_tested"]),
        untested.drop(columns=["pair_tested"]),
        tested,
        ranks,
        recovered_pairs(ranks),
        permutations,
        examples,
        len(retrievals[0].species),
        len(images),
        lance.version,
    )


def describe(results: MimicryResults) -> str:
    """Counts, the members not in the collection, and any stale recorded availability."""
    counts = dict(results.counts().itertuples(index=False, name=None))
    lines = [
        f"{counts['Tested pairs']} of {counts['Published pairs']} pairs tested, covering "
        f"{counts['Tested species (accepted names)']} species (of "
        f"{counts['Published species']} published names); ranked among "
        f"{results.n_species:,} species and {results.n_images:,} images; "
        f"Lance version {results.lance_version}"
    ]
    for pair, members in results.untested.groupby("pair", sort=False):
        missing = members.loc[~members["in_collection"]]
        reason = (
            "; ".join(f"{row.published_species}: {row.resolution}" for row in missing.itertuples())
            if len(missing)
            else "both members are one accepted species"
        )
        lines.append(f"Not tested: {pair} ({reason})")
    pairs = results.pairs
    stale = pairs.loc[
        pairs["recorded_availability"].notna()
        & (pairs["recorded_availability"] != pairs["availability"])
    ]
    for row in stale.itertuples():
        lines.append(
            f"WARNING: mimicry_pairs.csv records {row.pair} as {row.recorded_availability}, "
            f"but it is {row.availability} in this collection."
        )
    return "\n".join(lines)


def rank_panel(
    ax,
    ranks: pd.DataFrame,
    pairs: pd.DataFrame,
    series,
    n_species: int,
    recovered: Collection[str] = (),
) -> None:
    """Partner rank (log scale, 1 = nearest) per pair; `series` gives (mode, offset, color, label).

    Filled markers query with the first species of the pair, hollow ones with the second.
    Rows in `recovered` are shaded and their labels bold.
    """
    positions = {pair: index for index, pair in enumerate(pairs["pair"])}
    for pair, position in positions.items():
        if pair in recovered:
            ax.axhspan(position - 0.5, position + 0.5, color=HIGHLIGHT, zorder=0, linewidth=0)
    for mode, offset, color, _ in series:
        subset = ranks.loc[ranks["mode"] == mode]
        for direction, face in (("A→B", color), ("B→A", "white")):
            rows = subset.loc[subset["direction"] == direction]
            ax.scatter(
                rows["partner_rank"],
                rows["pair"].map(positions) + offset,
                s=90,
                marker="o",
                facecolor=face,
                edgecolor=color,
                linewidth=1.8,
                zorder=3,
            )
    ax.axvline(10, color="0.3", linestyle="--", linewidth=1.2, zorder=1)
    ax.axvline(n_species / 2, color="0.6", linestyle=":", linewidth=1.5, zorder=1)
    ax.set_xscale("log")
    ax.set_xlim(0.7, n_species * 1.4)
    ax.set_yticks(range(len(positions)), list(positions))
    for label in ax.get_yticklabels():
        if label.get_text() in recovered:
            label.set_fontweight("bold")
    ax.set_ylim(len(positions) - 0.5, -0.5)
    ax.set_xlabel("Partner rank among all species (log)")
    ax.grid(axis="y", color="0.92", linewidth=1)
    sns.despine(ax=ax)


def pair_images(ax, pairs: pd.DataFrame, pictures: dict[str, np.ndarray]) -> None:
    """Both species' representative images between each pair label and the axis.

    The first species sits farther from the axis, matching its place in the label.
    """
    for position, row in enumerate(pairs.itertuples()):
        for slot, name in enumerate((row.accepted_b, row.accepted_a)):
            pixels = pictures[name]
            ax.add_artist(
                AnnotationBbox(
                    OffsetImage(pixels, zoom=THUMBNAIL / pixels.shape[1]),
                    (0, position),
                    xycoords=("axes fraction", "data"),
                    xybox=(-THUMBNAIL_GAP - slot * (THUMBNAIL + THUMBNAIL_GAP), 0),
                    boxcoords="offset points",
                    box_alignment=(1, 0.5),
                    frameon=False,
                    annotation_clip=False,
                )
            )
    ax.tick_params(axis="y", length=0, pad=2 * (THUMBNAIL + THUMBNAIL_GAP) + THUMBNAIL_GAP)


def rank_legend(series) -> list:
    handles = [
        Line2D([], [], marker="o", linestyle="", markersize=10, color=color, label=label)
        for _, _, color, label in series
    ]
    handles += [
        Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            markersize=10,
            markerfacecolor="black",
            markeredgecolor="black",
            label="Query: first species",
        ),
        Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            markersize=10,
            markerfacecolor="white",
            markeredgecolor="black",
            label="Query: second species",
        ),
    ]
    handles += [
        Line2D([], [], color="0.3", linestyle="--", label="Site's top 10"),
        Line2D([], [], color="0.6", linestyle=":", label="Chance (median)"),
        Patch(facecolor=HIGHLIGHT, label=f"Mutual top {SITE_TOP}"),
    ]
    return handles


def p_label(p_value: float, permutations: int) -> str:
    """A p-value at the permutation floor, 1 / (n + 1), reads as a bound."""
    floor = 1 / (permutations + 1)
    return f"p ≤ {floor:.1g}" if p_value <= floor else f"p = {p_value:.2g}"


def permutation_panel(ax, summary: pd.DataFrame) -> None:
    """Observed mean partner percentile against each null's 95% interval."""
    labels = [f"{row.mode}\n{row.null}" for row in summary.itertuples()]
    y = np.arange(len(summary))
    ax.hlines(y, summary["null_low_2_5"], summary["null_high_97_5"], color="0.55", linewidth=4)
    ax.scatter(summary["null_mean"], y, color="0.55", s=60, zorder=3, label="Null mean, 95%")
    ax.scatter(
        summary["observed_mean_percentile"],
        y,
        marker="D",
        s=110,
        color="black",
        zorder=4,
        label="Observed mean",
    )
    for row, position in zip(summary.itertuples(), y, strict=True):
        ax.annotate(
            p_label(row.p_value, row.permutations),
            (1.02, position),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            fontsize=15,
            annotation_clip=False,
        )
    ax.set_yticks(y, labels)
    ax.set_ylim(len(summary) - 0.5, -0.5)
    ax.set_xlim(min(0.3, float(summary["null_low_2_5"].min()) - 0.05), 1.02)
    ax.set_xlabel("Mean partner percentile (1 = nearest)")
    ax.grid(axis="y", color="0.92", linewidth=1)
    sns.despine(ax=ax)


VISUAL_SERIES = (
    ("Visual (dorsal)", -0.17, SIDE_COLORS["dorsal"], "Dorsal centroid"),
    ("Visual (ventral)", 0.17, SIDE_COLORS["ventral"], "Ventral centroid"),
)
# Legends below a panel clear its tick labels and axis title whatever its height.
LEGEND_BELOW = {
    "loc": "upper center",
    "bbox_to_anchor": (0.5, 0),
    "borderaxespad": 4.6,
    "ncol": 2,
    "fontsize": 14,
}


def pairs_panel(
    ax,
    results: MimicryResults,
    pictures: dict[str, np.ndarray],
    title: str = "A) Mimicry pairs",
    legend: bool = True,
) -> list:
    """Partner ranks from the dorsal and ventral centroids, with representative images.

    Pairs that are mutual top ten are highlighted. Returns the legend handles, so a
    caller drawing `legend=False` can place the legend elsewhere.
    """
    rank_panel(
        ax, results.ranks, results.tested, VISUAL_SERIES, results.n_species, results.recovered()
    )
    pair_images(ax, results.tested, pictures)
    ax.set_title(title, loc="left")
    handles = rank_legend(VISUAL_SERIES)
    if legend:
        ax.legend(handles=handles, **LEGEND_BELOW)
    return handles


def tests_panel(ax, results: MimicryResults, title: str = "B) Permutation tests") -> None:
    """Observed mean partner percentile against each null's 95% interval."""
    permutation_panel(ax, results.permutations)
    ax.set_title(title, loc="left")
    ax.legend(**LEGEND_BELOW)


def recovery_figure(results: MimicryResults, pictures: dict[str, np.ndarray]):
    """A) partner ranks from the dorsal and ventral centroids, B) permutation tests."""
    fig = plt.figure(figsize=(21, 14), layout="constrained")
    grid = fig.add_gridspec(1, 2, width_ratios=(1, 0.75))
    pairs_panel(fig.add_subplot(grid[0]), results, pictures)
    tests_panel(fig.add_subplot(grid[1]), results)
    return fig

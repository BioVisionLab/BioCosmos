"""Does visual similarity recover published mimicry pairs?

Dorsal against dorsal: each tested species' dorsal UNICOM centroid (the mean of its
normalized dorsal embeddings, re-normalized) queries the dorsal images of every species
in the collection, and each species scores its nearest dorsal image, as `similarity run`
scores the site's list. Ventral images are neither queries nor candidates.

The site's list scores candidates on both sides and keeps the top ten, so these ranks
are not the site's list. Every species is ranked, so a partner outside the top ten
still has a measured rank. Species are accepted names, so subspecies and synonyms do
not split a species. Only the Lance table and DuckDB are read; nothing is written
outside `analyses/`.
"""

from __future__ import annotations

import gc
import os
from collections.abc import Collection, Sequence
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

# Queries and candidates are both dorsal images.
SIDE = "dorsal"
VISUAL_COLUMN = "unicom_embeddings"
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
# How a candidate species is scored against a query centroid.
NEAREST = "Nearest dorsal image"
NULLS = ("Random", "Query congeners", "Partner congeners")
# The site lists a species' ten most similar species.
SITE_TOP = 10
HIGHLIGHT = "#fff1c2"
# Representative images beside each pair label, in points; pixels kept for print.
THUMBNAIL = 54
THUMBNAIL_GAP = 6
THUMBNAIL_PIXELS = 320
# Exports the combined search figure carries; the tests stay with `mimicry_recovery`.
PANEL_EXPORTS = ("counts", "coverage", "ranks", "recovery", "representatives")


@dataclass(frozen=True)
class LanceSource:
    database: Path
    table: str


@dataclass(frozen=True)
class DorsalSpace:
    """Dorsal embeddings grouped by species, with each species' centroid.

    Images are sorted by species, so species `i` owns rows `starts[i]:stops[i]`.
    """

    species: np.ndarray
    starts: np.ndarray
    stops: np.ndarray
    centroids: np.ndarray
    embeddings: np.ndarray


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
    """One row per dorsal image with a MATCHED accepted species, sorted by species.

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
            SELECT img_id, t.species,
                lower(replace({text("i.species")}, '_', ' ')) AS recorded
            FROM {images} i JOIN (
                SELECT img_id, coalesce(
                    {text("accepted_species_name")},
                    CASE WHEN lower(accepted_rank) = 'species'
                        THEN {text("accepted_name")} END
                ) AS species
                FROM {taxonomy} WHERE update_status = 'MATCHED'
            ) t USING (img_id)
            WHERE t.species IS NOT NULL AND lower({text("i.class_dv")}) = '{SIDE}'
            """
        ).df()

    if frame.empty:
        raise AnalysisError(f"No {SIDE} images have a matched accepted species.")

    frame = frame.sort_values(["species", "img_id"], kind="stable", ignore_index=True)
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

    return None, f"no {SIDE} images in the collection"


def coverage(pairs: pd.DataFrame, images: pd.DataFrame) -> pd.DataFrame:
    """Accepted species and dorsal images for every pair member.

    A pair is tested only when both members resolve to distinct species with dorsal
    images to form a centroid.
    """

    counts = images.groupby("species").size()
    rows = []

    for pair in pairs.itertuples():
        for member, published in (("A", pair.species_a), ("B", pair.species_b)):
            accepted, resolution = resolve_species(published, images)
            rows.append(
                {
                    "pair": pair.pair,
                    "member": member,
                    "published_species": published,
                    "accepted_species": accepted,
                    "resolution": resolution,
                    f"{SIDE}_images": 0 if accepted is None else int(counts.get(accepted, 0)),
                }
            )

    frame = pd.DataFrame(rows)
    frame["in_collection"] = frame["accepted_species"].notna()
    frame["queryable"] = frame[f"{SIDE}_images"] > 0
    distinct = frame.groupby("pair")["accepted_species"].transform("nunique") == 2
    frame["pair_tested"] = frame.groupby("pair")["queryable"].transform("all") & distinct

    return frame


def tested_pairs(pairs: pd.DataFrame, covered: pd.DataFrame) -> pd.DataFrame:
    """Tested pairs with each member's accepted species as `accepted_a`/`accepted_b`."""

    tested = covered.loc[covered["pair_tested"]]
    accepted = tested.pivot(index="pair", columns="member", values="accepted_species")
    accepted = accepted.rename(columns={"A": "accepted_a", "B": "accepted_b"})

    return pairs.merge(accepted, left_on="pair", right_index=True).reset_index(drop=True)


def availability(pairs: pd.DataFrame, covered: pd.DataFrame) -> pd.Series:
    """ "Available" when both members resolve to distinct species with dorsal images."""

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


def dorsal_space(images: pd.DataFrame, embeddings: np.ndarray) -> DorsalSpace:
    """Group the species-sorted embeddings and compute every species' centroid."""

    codes, species = pd.factorize(images["species"], sort=True)

    if (np.diff(codes) < 0).any():
        raise AnalysisError("Images must be sorted by species.")

    starts = np.flatnonzero(np.r_[True, np.diff(codes) != 0])
    stops = np.r_[starts[1:], len(codes)]
    sums = np.add.reduceat(embeddings, starts, axis=0)
    centroids = sums / np.linalg.norm(sums, axis=1, keepdims=True)

    return DorsalSpace(np.asarray(species, dtype=object), starts, stops, centroids, embeddings)


def nearest_scores(space: DorsalSpace, queries: np.ndarray) -> np.ndarray:
    """Each query centroid's highest cosine similarity to any dorsal image of every
    collection species (Q × S)."""

    return np.maximum.reduceat(space.embeddings @ queries.T, space.starts, axis=0).T


def species_index(space: DorsalSpace) -> dict[str, int]:
    return {name: index for index, name in enumerate(space.species)}


def query_retrieval(space: DorsalSpace, queries: Sequence[str]) -> Retrieval:
    """Rank all species against each query species' dorsal centroid."""

    lookup = species_index(space)
    missing = [name for name in queries if name not in lookup]

    if missing:
        raise AnalysisError(f"No {SIDE} images to form a centroid: {missing}")

    centroids = space.centroids[[lookup[name] for name in queries]]

    return Retrieval(NEAREST, tuple(queries), space.species, nearest_scores(space, centroids))


def representatives(
    images: pd.DataFrame,
    space: DorsalSpace,
    ranks: pd.DataFrame,
    root: Path | None = None,
) -> pd.DataFrame:
    """For each query direction, the partner's dorsal image nearest the query centroid.

    That image sets the partner's score, so each pair shows the two images that
    matched: the first species' image nearest the second's centroid, and the second's
    nearest the first's. Its processed file must be on disk; no other image stands in.
    """

    directory, extension = image_directory(project_root(root))
    lookup = species_index(space)
    img_ids = images["img_id"].to_numpy()
    rows = []

    for row in ranks.itertuples():
        partner = lookup[row.partner]
        start, stop = space.starts[partner], space.stops[partner]
        similarity = space.embeddings[start:stop] @ space.centroids[lookup[row.query]]
        best = int(np.argmax(similarity))

        if not np.isclose(similarity[best], row.partner_score):
            raise AnalysisError(f"{row.partner}'s nearest image does not match its score.")

        img_id = str(img_ids[start + best])

        if not (
            (directory / f"{img_id}.{extension}").is_file()
            or (directory / "thumbnails" / f"{img_id}_thumbnail.{extension}").is_file()
        ):
            raise AnalysisError(
                f"{row.partner}'s nearest {SIDE} image to {row.query}, {img_id}, "
                f"is not on disk under {directory}."
            )

        rows.append(
            {
                "pair": row.pair,
                "species": row.partner,
                "query": row.query,
                "side": SIDE,
                "img_id": img_id,
                "similarity": float(similarity[best]),
            }
        )

    return pd.DataFrame(rows)


def thumbnail(img_id: str, root: Path | None = None) -> np.ndarray:
    """A pair's image on a transparent square, downsampled for print."""

    directory, extension = image_directory(project_root(root))
    image = Image.fromarray(square_image(img_id, directory, extension))

    if image.width > THUMBNAIL_PIXELS:
        image = image.resize((THUMBNAIL_PIXELS, THUMBNAIL_PIXELS), Image.Resampling.LANCZOS)

    return np.asarray(image)


def recovered_pairs(ranks: pd.DataFrame, top: int = SITE_TOP) -> pd.DataFrame:
    """Pairs whose members are in each other's top `top`.

    Requiring both directions keeps one-sided hits, such as a common species that
    appears near many queries, from counting as recovery.
    """

    within = ranks.assign(within=ranks["partner_rank"] <= top)
    mutual = within.groupby("pair", sort=False)["within"].all()

    return mutual.rename("recovered").reset_index()


def rank_matrix(retrieval: Retrieval) -> np.ndarray:
    """Each species' rank among the query's other species: 1 is the nearest.

    Ties share the best rank (1 + the number of strictly higher scores). The query
    species itself is NaN.
    """

    lookup = {name: index for index, name in enumerate(retrieval.species)}
    out = np.empty(retrieval.scores.shape, dtype=float)

    for row, query in enumerate(retrieval.queries):
        values = retrieval.scores[row].astype(float).copy()
        values[lookup[query]] = -np.inf
        descending = np.sort(-values)
        out[row] = np.searchsorted(descending, -values, side="left") + 1
        out[row, lookup[query]] = np.nan

    return out


def percentiles(ranks: np.ndarray, n_others: int) -> np.ndarray:
    """Rank r of n others maps to 1 - (r - 1) / (n - 1): 1 is nearest, 0.5 chance."""

    return 1 - (ranks - 1) / (n_others - 1)


def percentile_matrix(retrieval: Retrieval) -> np.ndarray:
    return percentiles(rank_matrix(retrieval), len(retrieval.species) - 1)


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
    ranks = rank_matrix(retrieval)
    rows = directions(pairs)
    n_others = len(retrieval.species) - 1
    records = []

    for row in rows.itertuples():
        query, partner = retrieval.queries.index(row.query), lookup[row.partner]
        rank = int(ranks[query, partner])
        records.append(
            {
                "mode": retrieval.mode,
                "partner_score": float(retrieval.scores[query, partner]),
                "partner_rank": rank,
                "species_compared": n_others,
                "partner_percentile": float(percentiles(np.float64(rank), n_others)),
            }
        )

    return pd.concat([rows, pd.DataFrame(records)], axis=1)


def null_pools(retrieval: Retrieval, rows: pd.DataFrame, null: str) -> list[np.ndarray]:
    """Candidate partners each row's null draws from; the query is never a candidate.

    "Random": any other collection species. "Query congeners": for a pair within one
    genus, the query's other congeners, since related species look alike regardless
    of mimicry; a pair across genera keeps the random pool. "Partner congeners": the
    partner's other congeners, asking whether the query resembles its partner more
    than the partner's relatives; empty when the partner's genus has no other species.
    """

    genus = np.array([name.split(" ")[0] for name in retrieval.species])
    lookup = {name: index for index, name in enumerate(retrieval.species)}
    everyone = np.arange(len(retrieval.species))
    pools = []

    for row in rows.itertuples():
        query, partner = lookup[row.query], lookup[row.partner]

        if null == "Random":
            pool = everyone
        elif null == "Query congeners":
            same_genus = genus[query] == genus[partner]
            pool = np.flatnonzero(genus == genus[query]) if same_genus else everyone
        elif null == "Partner congeners":
            pool = np.flatnonzero(genus == genus[partner])
            pool = pool[pool != partner]
        else:
            raise AnalysisError(f"Unknown null: {null}")

        pools.append(pool[pool != query])

    return pools


def permutation_test(
    retrieval: Retrieval,
    ranks: pd.DataFrame,
    n_permutations: int = 10_000,
    seed: int = 0,
    nulls: tuple[str, ...] = NULLS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Mean partner percentile against partners drawn from each null pool.

    Each permutation keeps every query and replaces its partner with a species drawn
    from that row's pool. Rows with an empty pool are left out of that null, and the
    observed mean is taken over the same rows. The one-sided p-value counts null means
    at least as high as the observed mean, with the observed arrangement counted once.
    """

    rows = ranks.loc[ranks["mode"] == retrieval.mode].reset_index(drop=True)
    matrix = percentile_matrix(retrieval)
    rng = np.random.default_rng(seed)
    summaries, distributions = [], []

    for null in nulls:
        pools = null_pools(retrieval, rows, null)
        used = np.array([len(pool) > 0 for pool in pools])

        if not used.any():
            raise AnalysisError(f"No row has a candidate under the {null} null.")

        observed = float(rows.loc[used, "partner_percentile"].mean())
        draws = np.empty((int(used.sum()), n_permutations))
        kept = [(row, pool) for row, pool, use in zip(rows.itertuples(), pools, used) if use]

        for index, (row, pool) in enumerate(kept):
            row_percentiles = matrix[retrieval.queries.index(row.query)]
            draws[index] = row_percentiles[rng.choice(pool, size=n_permutations)]

        means = draws.mean(axis=0)
        summaries.append(
            {
                "mode": retrieval.mode,
                "null": null,
                "query_rows": len(rows),
                "rows_used": int(used.sum()),
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


def pair_tests(
    retrieval: Retrieval, ranks: pd.DataFrame, nulls: tuple[str, ...] = NULLS
) -> pd.DataFrame:
    """One row per pair and null: both directions' percentiles and exact p-values.

    A direction's p-value is the share of its null candidates, plus the partner
    itself, whose percentile is at least the partner's: the chance that a partner
    drawn from that pool sits as near the query. Pairs are the unit of inference;
    the pooled permutation statistic equals the mean of `mean_percentile`.
    """

    rows = ranks.loc[ranks["mode"] == retrieval.mode].reset_index(drop=True)
    matrix = percentile_matrix(retrieval)
    lookup = {name: index for index, name in enumerate(retrieval.species)}
    records = []

    for null in nulls:
        for row, pool in zip(rows.itertuples(), null_pools(retrieval, rows, null), strict=True):
            row_percentiles = matrix[retrieval.queries.index(row.query)]
            p_value = np.nan

            if len(pool):
                candidates = np.union1d(pool, [lookup[row.partner]])
                observed = row_percentiles[lookup[row.partner]]
                p_value = float((row_percentiles[candidates] >= observed).mean())

            records.append(
                {
                    "pair": row.pair,
                    "mode": retrieval.mode,
                    "null": null,
                    "direction": row.direction,
                    "percentile": row.partner_percentile,
                    "p": p_value,
                }
            )

    frame = pd.DataFrame(records).pivot_table(
        index=["pair", "mode", "null"],
        columns="direction",
        values=["percentile", "p"],
        dropna=False,
    )
    frame.columns = [
        f"{value}_{direction.replace('→', '_to_')}" for value, direction in frame.columns
    ]
    frame["mean_percentile"] = frame[["percentile_A_to_B", "percentile_B_to_A"]].mean(axis=1)
    frame = frame.reset_index()
    # Keep the pairs table's pair order and the declared null order.
    frame["pair"] = pd.Categorical(frame["pair"], pd.unique(rows["pair"]), ordered=True)
    frame["null"] = pd.Categorical(frame["null"], nulls, ordered=True)
    frame = frame.sort_values(["null", "pair"]).astype({"pair": str, "null": str})

    return frame[
        [
            "pair",
            "mode",
            "null",
            "percentile_A_to_B",
            "percentile_B_to_A",
            "mean_percentile",
            "p_A_to_B",
            "p_B_to_A",
        ]
    ].reset_index(drop=True)


def shared_species(tested: pd.DataFrame) -> list[str]:
    """Species in more than one tested pair, whose pairs are not independent."""

    members = pd.concat([tested["accepted_a"], tested["accepted_b"]])
    counts = members.value_counts()

    return sorted(counts.index[counts > 1])


def leave_one_out(
    retrieval: Retrieval,
    ranks: pd.DataFrame,
    tested: pd.DataFrame,
    n_permutations: int = 10_000,
    seed: int = 0,
) -> pd.DataFrame:
    """Permutation tests without every pair holding each species shared by pairs."""

    frames = []

    for name in shared_species(tested):
        kept = tested.loc[(tested["accepted_a"] != name) & (tested["accepted_b"] != name), "pair"]
        subset = ranks.loc[ranks["pair"].isin(kept)]
        summary = permutation_test(retrieval, subset, n_permutations, seed)[0]
        summary.insert(0, "dropped_species", name)
        summary.insert(1, "pairs_left", len(kept))
        frames.append(summary)

    return pd.concat(frames, ignore_index=True)


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
    pair_tests: pd.DataFrame
    leave_one_out: pd.DataFrame
    # The images drawn beside each pair: each partner's image nearest the query.
    representatives: pd.DataFrame
    n_species: int
    n_images: int
    lance_version: int

    def counts(self) -> pd.DataFrame:
        """The tested pairs and species, against the dorsal collection they rank in."""

        tested = set(self.tested["accepted_a"]) | set(self.tested["accepted_b"])

        return pd.DataFrame(
            [
                ("Pairs tested", len(self.tested)),
                ("Species tested (accepted names)", len(tested)),
                ("Species ranked", self.n_species),
                (f"{SIDE.capitalize()} images ranked", self.n_images),
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
            "pair_tests": self.pair_tests,
            "leave_one_out": self.leave_one_out,
            "representatives": self.representatives,
        }

    def recovered(self) -> set[str]:
        return set(self.recovery.loc[self.recovery["recovered"], "pair"])

    def image_counts(self) -> dict[str, int]:
        """Dorsal images (N) of each tested species."""

        return dict(
            self.coverage[["accepted_species", f"{SIDE}_images"]].itertuples(index=False, name=None)
        )

    def pictures(self, root: Path | None = None) -> dict[tuple[str, str], np.ndarray]:
        """Each pair's matched images, keyed by (pair, species)."""

        return {
            (row.pair, row.species): thumbnail(row.img_id, root)
            for row in self.representatives.itertuples()
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
    space = dorsal_space(images, load_embeddings(lance, VISUAL_COLUMN, images["img_id"]))
    retrieval = query_retrieval(space, queries)
    ranks = partner_ranks(retrieval, tested)
    # The images that set each partner's score, drawn beside the pair labels.
    examples = representatives(images, space, ranks, root)
    n_species = len(space.species)
    del space
    gc.collect()

    return MimicryResults(
        pairs,
        covered.loc[in_collection].drop(columns=["in_collection", "queryable", "pair_tested"]),
        untested.drop(columns=["pair_tested"]),
        tested,
        ranks,
        recovered_pairs(ranks),
        permutation_test(retrieval, ranks, n_permutations, seed)[0],
        pair_tests(retrieval, ranks),
        leave_one_out(retrieval, ranks, tested, n_permutations, seed),
        examples,
        n_species,
        len(images),
        lance.version,
    )


def describe(results: MimicryResults) -> str:
    """Counts, the members not in the collection, and any stale recorded availability."""

    counts = dict(results.counts().itertuples(index=False, name=None))
    lines = [
        f"{counts['Pairs tested']} pairs tested, covering "
        f"{counts['Species tested (accepted names)']} species; ranked among "
        f"{results.n_species:,} species and {results.n_images:,} {SIDE} images; "
        f"Lance version {results.lance_version}"
    ]

    for pair, members in results.untested.groupby("pair", sort=False):
        missing = members.loc[~members["queryable"]]
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

        # Directions sit just apart, so equal ranks do not hide one another.
        for direction, face, nudge in (("A→B", color, -0.1), ("B→A", "white", 0.1)):
            rows = subset.loc[subset["direction"] == direction]
            ax.scatter(
                rows["partner_rank"],
                rows["pair"].map(positions) + offset + nudge,
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


def pair_images(
    ax,
    pairs: pd.DataFrame,
    pictures: dict[tuple[str, str], np.ndarray],
    counts: dict[str, int],
) -> None:
    """Both species' matched images between each pair label and the axis, with N.

    Each image is that species' dorsal image nearest the other species' centroid; N
    below it is the species' dorsal image count. The first species sits farther from
    the axis, matching its place in the label.
    """

    for position, row in enumerate(pairs.itertuples()):
        for slot, name in enumerate((row.accepted_b, row.accepted_a)):
            pixels = pictures[(row.pair, name)]
            x = -THUMBNAIL_GAP - slot * (THUMBNAIL + THUMBNAIL_GAP) - THUMBNAIL / 2
            ax.add_artist(
                AnnotationBbox(
                    OffsetImage(pixels, zoom=THUMBNAIL / pixels.shape[1]),
                    (0, position),
                    xycoords=("axes fraction", "data"),
                    xybox=(x, 0),
                    boxcoords="offset points",
                    box_alignment=(0.5, 0.5),
                    frameon=False,
                    annotation_clip=False,
                )
            )
            ax.annotate(
                f"N = {counts[name]:,}",
                (0, position),
                xycoords=("axes fraction", "data"),
                xytext=(x, -THUMBNAIL / 2 + 2),
                textcoords="offset points",
                ha="center",
                va="top",
                fontsize=10,
                annotation_clip=False,
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

    labels = list(summary["null"])
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


# (mode, vertical offset, color, legend label): ColorBrewer Dark2.
VISUAL_SERIES = ((NEAREST, 0.0, "#1b9e77", "Scored by nearest dorsal image"),)
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
    pictures: dict[tuple[str, str], np.ndarray],
    title: str = "A) Mimicry pairs",
    legend: bool = True,
) -> list:
    """Partner ranks by nearest dorsal image, with each pair's matched images and N.

    Pairs that are mutual top ten are highlighted. Returns the legend handles, so a
    caller drawing `legend=False` can place the legend elsewhere.
    """

    rank_panel(
        ax, results.ranks, results.tested, VISUAL_SERIES, results.n_species, results.recovered()
    )
    pair_images(ax, results.tested, pictures, results.image_counts())
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


def recovery_figure(results: MimicryResults, pictures: dict[tuple[str, str], np.ndarray]):
    """A) partner ranks by nearest dorsal image, B) permutation tests."""

    fig = plt.figure(figsize=(21, 15), layout="constrained")
    grid = fig.add_gridspec(1, 2, width_ratios=(1, 0.75))
    pairs_panel(fig.add_subplot(grid[0]), results, pictures)
    tests_panel(fig.add_subplot(grid[1]), results)

    return fig

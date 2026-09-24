"""Payloads for the order, family and genus pages.

The repository in `app/services/higher_taxa.py` returns one flat row per
member. This module turns those rows into the nested tree the page renders,
adds the taxon's own Catalogue of Life classification, and derives the header
counts without going back to the database.

A family page's tree bottoms out at genus and a genus page's at species, so
on both of them every node that links somewhere is a leaf and every node that
has children links nowhere. That is what lets the frontend render the whole
thing as nested `<details>` without a link ever sitting inside a summary.
"""

import json
import logging
import re
from collections import OrderedDict

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ..database.duckdb import DuckDBClient
from ..database.model import subgenus_name
from ..services.higher_taxa import HigherTaxonRepository, Scope
from .taxon_data import FamilySearch, GenusSearch, OrderSearch

logger = logging.getLogger(__name__)

# The ranks that group members on each page, coarsest first. Both lists are
# ragged in practice: CoL populates subfamily for most butterfly genera, tribe
# for many, and subtribe for almost none, so a level with nothing in it is
# omitted rather than rendered empty.
_ORDER_GROUPING_RANKS = ("suborder", "superfamily")
_FAMILY_GROUPING_RANKS = ("subfamily", "tribe", "subtribe")
_GENUS_GROUPING_RANKS = ("subgenus",)

# Where genera CoL cannot place, or places in another family, are collected.
# A first-class node rather than a silent omission: dropping them would make
# the tree's counts disagree with the header's.
UNPLACED_KEY = "unplaced"
UNPLACED_LABEL = "Unplaced in this classification"

DEFAULT_IMAGE_LIMIT = 20


class TaxonNode(BaseModel):
    """One row of the expand/collapse tree."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    key: str
    name: str
    # Set only when the collection records this taxon under a different name
    # than the one Catalogue of Life accepts, so the page can show the rename
    # without implying the two are separate taxa.
    recorded_name: str | None = None
    rank: str
    authorship: str | None = None
    # Only the ranks that have a page of their own carry one.
    href: str | None = None
    col_id: str | None = None
    col_link: str | None = None
    family_count: int | None = None
    genus_count: int | None = None
    species_count: int = 0
    image_count: int = 0
    placed: bool = True
    children: list["TaxonNode"] = Field(default_factory=list)


TaxonNode.model_rebuild()


class TaxonImage(BaseModel):
    """One tile of the representative image strip."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    img_id: str
    # The recorded species key, which is what /species/{name} resolves on.
    species: str
    display_name: str


class HigherTaxonCounts(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    # Set only on an order page. There it counts the families the collection
    # has images of, not every family the tree lists.
    family_count: int | None = None
    # None on a genus page, where there is no rank between it and species.
    genus_count: int | None = None
    species_count: int = 0
    image_count: int = 0


class HigherTaxonPayload(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    key: str
    name: str
    rank: str
    # The full Catalogue of Life lineage, dumped by alias so `class` arrives
    # under the key the frontend reads. None when the backbone is absent.
    classification: dict | None = None
    counts: HigherTaxonCounts
    tree: list[TaxonNode] = Field(default_factory=list)
    images: list[TaxonImage] = Field(default_factory=list)
    # Which optional tables answered, so the page can say why a tree is flat
    # rather than implying CoL has no subfamilies.
    sources: dict[str, bool] = Field(default_factory=dict)


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _optional(value: object) -> str | None:
    return _text(value) or None


def _int(value: object) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


class _Group:
    """A grouping node under construction, before counts are rolled up."""

    __slots__ = ("children", "groups", "key", "name", "rank")

    def __init__(self, key: str, name: str, rank: str):
        self.key = key
        self.name = name
        self.rank = rank
        self.children: list[TaxonNode] = []
        self.groups: dict[str, _Group] = {}


def _group_path(row: dict, ranks: tuple[str, ...]) -> list[tuple[str, str]]:
    """The populated grouping ranks for one member, coarsest first.

    Unpopulated ranks are skipped rather than rendered as an empty level, so
    a genus CoL places in a subfamily but no tribe hangs directly off the
    subfamily instead of under a nameless node.
    """
    path: list[tuple[str, str]] = []
    for rank in ranks:
        value = _optional(row.get(rank))
        if not value:
            continue
        # CoL writes a zoological subgenus as `Genus (Subgenus)`; only the
        # parenthesised part names it, and the genus has its own node.
        if rank == "subgenus":
            value = subgenus_name(value)
        path.append((rank, value))
    return path


_PARENTHETICAL = re.compile(r"\([^)]*\)")


def _is_rename(accepted: str, recorded: str) -> bool:
    """Whether a species is filed under a name different from its accepted one.

    Compared canonically: lowercased, because the recorded key is stored that
    way, and with any parenthesised subgenus dropped, because Catalogue of
    Life writes `Danaus (Salatura) genutia` for a collection that only ever
    wrote `danaus_genutia`. Without that, every species in a genus with
    subgenera would claim to have been renamed.
    """
    if not recorded or not accepted:
        return False

    def canonical(value: str) -> str:
        return " ".join(_PARENTHETICAL.sub(" ", value).split()).lower()

    return canonical(accepted) != canonical(recorded)


def _leaf_from_order_row(row: dict) -> TaxonNode:
    key = _text(row.get("family_key"))
    images = _int(row.get("image_count"))
    genera = _int(row.get("genus_count"))
    return TaxonNode(
        key=key,
        name=_text(row.get("family_name")) or key.capitalize(),
        rank="family",
        authorship=_optional(row.get("authorship")),
        # A family the collection has no images of has no page to link to:
        # its family route would answer 404.
        href=f"/family/{key}" if images else None,
        col_id=_optional(row.get("col_id")),
        col_link=_optional(row.get("col_link")),
        genus_count=genera or None,
        species_count=_int(row.get("species_count")),
        image_count=images,
    )


def _leaf_from_family_row(row: dict) -> TaxonNode:
    key = _text(row.get("genus_key"))
    return TaxonNode(
        key=key,
        name=_text(row.get("genus_name")) or key.capitalize(),
        rank="genus",
        authorship=_optional(row.get("authorship")),
        href=f"/genus/{key}",
        col_id=_optional(row.get("col_id")),
        col_link=_optional(row.get("col_link")),
        species_count=_int(row.get("species_count")),
        image_count=_int(row.get("image_count")),
    )


def _species_href(key: str) -> str:
    """The species route takes a binomial, so a recorded trinomial is trimmed.

    That is the convention the rest of the site already links by, and the
    species page itself only parses two parts. The key is still the recorded
    one, never the accepted name: it is what the page resolves its images on.
    """
    parts = [part for part in key.split("_") if part]
    return "/species/" + "_".join(parts[:2])


def _leaf_from_genus_row(row: dict) -> TaxonNode:
    key = _text(row.get("species_key"))
    name = _text(row.get("species_name"))
    recorded = _text(row.get("recorded_name"))
    return TaxonNode(
        key=key,
        name=name or recorded,
        # Only worth stating when the two name different taxa.
        recorded_name=recorded if _is_rename(name, recorded) else None,
        rank="species",
        authorship=_optional(row.get("authorship")),
        href=_species_href(key),
        col_id=_optional(row.get("col_id")),
        col_link=_optional(row.get("col_link")),
        species_count=1,
        image_count=_int(row.get("image_count")),
    )


def _is_unplaced(row: dict, scope_key: str) -> bool:
    """Whether CoL fails to place this genus inside the family being rendered.

    Two ways that happens: the backbone has no accepted usage for the name at
    all, or it has one that belongs to a different family. Hanging the second
    kind under a subfamily would file it under a subfamily of some other
    family, which is worse than admitting we cannot place it.
    """
    if not _optional(row.get("col_id")):
        return True
    col_family = _optional(row.get("col_family"))
    return bool(col_family) and col_family.lower() != scope_key


def _by_name(node: TaxonNode) -> str:
    """Sort key for tree siblings: alphabetical, case-insensitively.

    A classification is a reference list, so a reader looks names up in it.
    The rows arrive from the database in whatever order suited the query —
    for a family, most-photographed first — which is useful for choosing
    images and useless for finding a genus.
    """
    return node.name.casefold()


def _collapse(group: _Group) -> TaxonNode:
    """Turn a group and everything under it into a node, rolling counts up."""
    # Grouping ranks first, then the members that hang off this node
    # directly, each run alphabetical. Interleaving the two would sort a
    # tribe in among the genera that are not in one, which reads as a flat
    # list that has lost its structure.
    children = sorted(
        (_collapse(child) for child in group.groups.values()), key=_by_name
    )
    children.extend(sorted(group.children, key=_by_name))
    node = TaxonNode(
        key=group.key,
        name=group.name,
        rank=group.rank,
        children=children,
        placed=group.key != UNPLACED_KEY,
    )
    _accumulate(node)
    return node


def _accumulate(node: TaxonNode) -> None:
    """Sum a node's descendants into its own counts.

    Species and image counts are additive because a species belongs to
    exactly one genus here — membership is decided by its accepted name, so
    it cannot be counted under two.
    """
    if not node.children:
        return
    node.species_count = sum(child.species_count for child in node.children)
    node.image_count = sum(child.image_count for child in node.children)
    # Only families with images count, matching the header: a family is a
    # family of the collection once something in it has been photographed.
    families = sum(
        (1 if child.image_count else 0)
        if child.rank == "family"
        else (child.family_count or 0)
        for child in node.children
    )
    node.family_count = families or None
    genera = sum(
        1 if child.rank == "genus" else (child.genus_count or 0)
        for child in node.children
    )
    node.genus_count = genera or None


def build_tree(rows: list[dict], *, scope: Scope, scope_key: str) -> list[TaxonNode]:
    """Nest flat member rows under the ranks Catalogue of Life places them in.

    Pure: no request, no database. The tree a family page shows is entirely a
    function of its member rows, which makes it the one part of this feature
    that can be tested without either.
    """
    if scope == "order":
        ranks = _ORDER_GROUPING_RANKS
        leaf_of = _leaf_from_order_row
    elif scope == "family":
        ranks = _FAMILY_GROUPING_RANKS
        leaf_of = _leaf_from_family_row
    else:
        ranks = _GENUS_GROUPING_RANKS
        leaf_of = _leaf_from_genus_row

    root = _Group("", "", "")
    unplaced: _Group | None = None

    for row in rows:
        leaf = leaf_of(row)
        if not leaf.key:
            continue
        if scope == "family" and _is_unplaced(row, scope_key):
            if unplaced is None:
                unplaced = _Group(UNPLACED_KEY, UNPLACED_LABEL, "unplaced")
            # The flag describes the genus, not only the bucket holding it, so
            # a client rendering one node in isolation still knows.
            leaf.placed = False
            unplaced.children.append(leaf)
            continue

        cursor = root
        for rank, value in _group_path(row, ranks):
            key = value.lower()
            group = cursor.groups.get(key)
            if group is None:
                group = _Group(key, value, rank)
                cursor.groups[key] = group
            cursor = group
        cursor.children.append(leaf)

    tree = sorted((_collapse(group) for group in root.groups.values()), key=_by_name)
    # Members CoL places at no intermediate rank sit directly under the root.
    tree.extend(sorted(root.children, key=_by_name))
    if unplaced is not None:
        # Always last: it is a remainder, not a peer of the real ranks.
        tree.append(_collapse(unplaced))
    return tree


def build_order_tree(
    rows: list[dict], *, order_key: str, order_name: str
) -> list[TaxonNode]:
    """The order's classification under a single root node for the order.

    The family and genus pages start their trees one rank down, because the
    header already names the taxon. An order's first rank is suborder, which
    CoL leaves empty for most Lepidoptera, so without a root the tree would
    open on a mixed list of suborders and superfamilies. The root also gives
    the page one node to highlight, and gives the counts one place to total.
    """
    # Built directly rather than through `_collapse`, which would re-sort the
    # children and file the superfamilies in among the families beside them.
    root = TaxonNode(
        key=order_key,
        name=order_name,
        rank="order",
        children=build_tree(rows, scope="order", scope_key=order_key),
    )
    _accumulate(root)
    return [root]


class HigherTaxonOverview:
    """Assemble everything one higher-taxon page needs.

    Two queries and one classification lookup. The header counts are summed
    from the member rows rather than queried separately: a genus key is a
    prefix of its species keys, so the sums are exact, and a third scan of
    `image_meta` would only create a way for the header and the tree to
    disagree.
    """

    rank: Scope = "family"

    def __init__(self, request: Request, name: str = ""):
        self.request = request
        self.name = " ".join((name or "").replace("_", " ").split())
        self.key = self.name.lower()

    async def overview(self, limit: int = DEFAULT_IMAGE_LIMIT) -> dict | None:
        """Return the page payload, or None when the taxon has no members."""
        if not self.key:
            return None

        duck_db = self.request.app.state.duck_db
        memoized = PAYLOAD_CACHE.get(duck_db, self.rank, self.key, limit)
        if memoized is not None:
            return memoized

        repository = HigherTaxonRepository(duck_db)
        if not repository.harmonized_available():
            return None

        if self.rank == "order":
            rows = repository.order_members(self.key)
        elif self.rank == "family":
            rows = repository.family_members(self.key)
        else:
            rows = repository.genus_members(self.key)
        # An order's rows include families with nothing in them, so rows alone
        # do not mean the collection holds any of it.
        if not any(_int(row.get("image_count")) for row in rows):
            return None

        images = repository.representative_images(self.rank, self.key, limit)
        classification = await self._classification()
        if self.rank == "order":
            tree = build_order_tree(
                rows,
                order_key=self.key,
                order_name=self._display_name(classification),
            )
        else:
            tree = build_tree(rows, scope=self.rank, scope_key=self.key)

        payload = HigherTaxonPayload(
            key=self.key,
            name=self._display_name(classification),
            rank=self.rank,
            classification=classification,
            counts=self._counts(rows),
            tree=tree,
            images=[
                TaxonImage(
                    img_id=_text(row.get("img_id")),
                    species=_text(row.get("species")),
                    display_name=_text(row.get("display_name")),
                )
                for row in images
            ],
            sources={
                "colTaxonomy": repository.col_available(),
                "harmonizedTaxonomy": True,
            },
        ).model_dump(by_alias=True)
        PAYLOAD_CACHE.put(duck_db, self.rank, self.key, limit, payload)
        return payload

    def _counts(self, rows: list[dict]) -> HigherTaxonCounts:
        if self.rank == "order":
            return HigherTaxonCounts(
                family_count=sum(1 for row in rows if _int(row.get("image_count"))),
                genus_count=sum(_int(row.get("genus_count")) for row in rows),
                species_count=sum(_int(row.get("species_count")) for row in rows),
                image_count=sum(_int(row.get("image_count")) for row in rows),
            )
        species = sum(_int(row.get("species_count", 1)) for row in rows)
        images = sum(_int(row.get("image_count")) for row in rows)
        return HigherTaxonCounts(
            genus_count=len(rows) if self.rank == "family" else None,
            species_count=species if self.rank == "family" else len(rows),
            image_count=images,
        )

    def _display_name(self, classification: dict | None) -> str:
        """CoL's own casing when we have it, the capitalized key otherwise."""
        if classification:
            name = _text(classification.get("scientificName"))
            if name:
                return name
        return self.key.capitalize()

    async def _classification(self) -> dict | None:
        """The taxon's own lineage, for the header and the breadcrumb."""
        search = {
            "order": OrderSearch,
            "family": FamilySearch,
            "genus": GenusSearch,
        }[self.rank]
        results = await search(
            request=self.request, query=self.name
        ).get_classification()
        if not results:
            return None
        return results[0].get("classification") or None


class OrderOverview(HigherTaxonOverview):
    """An order page: members are families, drawn from the backbone."""

    rank: Scope = "order"


class FamilyOverview(HigherTaxonOverview):
    """A family page: members are genera."""

    rank: Scope = "family"


class GenusOverview(HigherTaxonOverview):
    """A genus page: members are species."""

    rank: Scope = "genus"


class _PayloadCache:
    """A bounded, process-lifetime memo of serialized payloads.

    Higher-taxon data changes only inside `run_data_ingestion`, which finishes
    during lifespan startup before the first request is served, so process
    lifetime is data lifetime and no expiry is needed. Entries are stored as
    JSON text rather than dicts so a handler cannot mutate a shared payload,
    and the map is bounded because the genus keys number in the thousands.

    Keyed on the database's identity as well as the taxon: there is one
    DuckDBClient per process today, and keying on it means a second one could
    never be served another's rows.
    """

    def __init__(self, maxsize: int = 512):
        self.maxsize = maxsize
        self._entries: OrderedDict[tuple, str] = OrderedDict()

    def get(
        self, duck_db: DuckDBClient, rank: str, key: str, limit: int
    ) -> dict | None:
        cache_key = (id(duck_db), rank, key, limit)
        stored = self._entries.get(cache_key)
        if stored is None:
            return None
        self._entries.move_to_end(cache_key)
        return json.loads(stored)

    def put(
        self, duck_db: DuckDBClient, rank: str, key: str, limit: int, payload: dict
    ) -> None:
        cache_key = (id(duck_db), rank, key, limit)
        self._entries[cache_key] = json.dumps(payload)
        self._entries.move_to_end(cache_key)
        while len(self._entries) > self.maxsize:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()


PAYLOAD_CACHE = _PayloadCache()

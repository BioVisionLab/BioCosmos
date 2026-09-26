"""Response caching for the higher-taxon endpoints.

Set per handler, by constructing the response with the header, rather than
through a dependency or middleware. A dependency would silently do nothing:
FastAPI merges an injected `Response`'s headers into the result only when the
handler returns a non-`Response`, and every handler in this application
returns a `JSONResponse`. Middleware would have to match paths by prefix,
which would put the policy somewhere no one reading the router will find it
and would sweep in `/family/{name}/classification` by accident.
"""

from fastapi.responses import JSONResponse

# Thirty days. A family's composition changes only when Catalogue of Life cuts
# a release and the backend re-ingests it, which is far rarer than a page
# view, and the ETag below gives a shared cache a way to notice sooner.
HIGHER_TAXON_MAX_AGE = 60 * 60 * 24 * 30
HIGHER_TAXON_CACHE_CONTROL = (
    f"public, max-age={HIGHER_TAXON_MAX_AGE}, "
    f"s-maxage={HIGHER_TAXON_MAX_AGE}, stale-while-revalidate=86400"
)

# One day. Visually similar species come off a precomputed table that is
# regenerated on its own schedule, with no fingerprint to hang an ETag on, so
# the only way a cache entry retires is by ageing out. A month would be too
# long to wait for a recomputed neighbourhood to reach a reader.
SIMILARITY_MAX_AGE = 60 * 60 * 24
SIMILARITY_CACHE_CONTROL = (
    f"public, max-age={SIMILARITY_MAX_AGE}, "
    f"s-maxage={SIMILARITY_MAX_AGE}, stale-while-revalidate=3600"
)

# One day for morphospaces, for the same reason as similarity: the tables are
# rebuilt offline by `morphospace integrate`, with nothing to hang an ETag on
# beyond the run id, so a cached scope retires by ageing out.
MORPHOSPACE_MAX_AGE = 60 * 60 * 24
MORPHOSPACE_CACHE_CONTROL = (
    f"public, max-age={MORPHOSPACE_MAX_AGE}, "
    f"s-maxage={MORPHOSPACE_MAX_AGE}, stale-while-revalidate=86400"
)

# One day for a complete literature list: CrossRef itself is cached for a week
# in the backend, so this only bounds how long a browser or CDN holds the
# assembled page. A list missing some results because CrossRef failed is held
# for five minutes, long enough to absorb a burst but not to outlive an outage.
LITERATURE_MAX_AGE = 60 * 60 * 24
LITERATURE_CACHE_CONTROL = (
    f"public, max-age={LITERATURE_MAX_AGE}, "
    f"s-maxage={LITERATURE_MAX_AGE}, stale-while-revalidate=86400"
)
LITERATURE_PARTIAL_CACHE_CONTROL = "public, max-age=300, s-maxage=300"

# One day for a complete genetics summary: NCBI's answers are cached for a
# week in the backend, so this only bounds how long a browser or CDN holds
# the assembled payload. A summary missing counts because an NCBI request
# failed or timed out is held for five minutes, as for literature.
GENETICS_MAX_AGE = 60 * 60 * 24
GENETICS_CACHE_CONTROL = (
    f"public, max-age={GENETICS_MAX_AGE}, "
    f"s-maxage={GENETICS_MAX_AGE}, stale-while-revalidate=86400"
)
GENETICS_PARTIAL_CACHE_CONTROL = "public, max-age=300, s-maxage=300"

# Errors are not cached at all. A month-long cache entry for a typo'd family
# name would outlive several ingestions and there would be no way to clear it
# from the browser that holds it.
NO_STORE = "no-store"


def cached_json(
    payload: dict | list,
    *,
    etag: str | None = None,
    cache_control: str = HIGHER_TAXON_CACHE_CONTROL,
) -> JSONResponse:
    """A 200 that may be cached — for thirty days unless told otherwise."""
    headers = {"Cache-Control": cache_control}
    if etag:
        # Weak: the bytes are only guaranteed equivalent, not identical, across
        # serializations of the same ingestion.
        headers["ETag"] = f'W/"{etag}"'
    return JSONResponse(content=payload, status_code=200, headers=headers)

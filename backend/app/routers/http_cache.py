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

# Errors are not cached at all. A month-long cache entry for a typo'd family
# name would outlive several ingestions and there would be no way to clear it
# from the browser that holds it.
NO_STORE = "no-store"


def cached_json(payload: dict | list, *, etag: str | None = None) -> JSONResponse:
    """A 200 that may be cached for thirty days."""
    headers = {"Cache-Control": HIGHER_TAXON_CACHE_CONTROL}
    if etag:
        # Weak: the bytes are only guaranteed equivalent, not identical, across
        # serializations of the same ingestion.
        headers["ETag"] = f'W/"{etag}"'
    return JSONResponse(content=payload, status_code=200, headers=headers)

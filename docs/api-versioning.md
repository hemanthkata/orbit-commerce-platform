# API design & versioning

## Versioning strategy

The API is versioned in the URL path (`/api/v1/...`) via DRF's
`URLPathVersioning`, configured in `config/settings/base.py`
(`DEFAULT_VERSIONING_CLASS`, `ALLOWED_VERSIONS`). Path versioning was chosen
over header/Accept versioning because it's the most discoverable option for
API consumers browsing Swagger/Redoc, and it plays cleanly with HTTP
caching (`cache_page`) and CDNs, which key on the URL.

When a breaking change is needed (removing a field, changing a status code,
altering write semantics), it ships as `/api/v2/...` with the old version
kept running until consumers migrate, rather than mutating `v1` in place. A
non-breaking change (new optional field, new endpoint, new filter) lands in
the current version directly - see the checklist below.

## What counts as breaking

Breaking (needs a new version):
- Removing or renaming a response field or endpoint.
- Changing a field's type or meaning.
- Making an optional request field required.
- Changing default pagination/ordering behavior consumers may rely on.

Non-breaking (safe to add to the current version):
- New optional request fields with a sensible default.
- New response fields (consumers should ignore unknown fields).
- New endpoints, new filter/ordering options.
- New error `code` values in the `{"error": {"detail", "code"}}` envelope.

## Contracts

- Every endpoint is documented via `drf-spectacular` (OpenAPI 3) at
  `/api/schema/`, browsable at `/api/docs/` (Swagger UI) and `/api/redoc/`.
- Errors always use one envelope, `{"error": {"detail": ..., "code": ...}}`
  (see `apps.common.exceptions.api_exception_handler`), so clients can
  branch on `code` without parsing DRF's default per-exception shapes.
- List endpoints are paginated (`PageNumberPagination`, `page_size` query
  param) and filterable via `django-filter` - see
  `apps.catalog.filters.ProductFilter` for the pattern.

## Auth on every version

JWT (`/api/v1/auth/token/`) and OAuth2 (`/api/v1/auth/oauth2/`) both work as
DRF authentication classes on every versioned endpoint - versioning the API
doesn't mean re-deriving auth per version.

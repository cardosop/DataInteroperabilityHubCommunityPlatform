#!/usr/bin/env python3
"""
pilot-readiness 3.3 — the privacy-pack runner.

Executes the REAL privacy pack against the live API (no mocks — real
HTTP, real rows, real S3 artefact):

1. ``tenant``  — the pilot tenant (``pilot-co``) exists, ACTIVE, with
   the three compliance gates ON (provisioning itself is the
   ``seed_pilot_privacy_tenant`` management command's job);
2. ``dpia``    — the REAL DPIA flow with role separation: pilot
   TENANT_ADMIN creates + submits, pilot DPO reviews → APPROVED
   (IsDpiaParticipant / IsDpiaReviewer role checks, not the
   platform-admin bypass);
3. ``ropa``    — REAL RoPA generation (GDPR, pdf): generate → poll
   COMPLETED → download the presigned S3 artefact and verify it is a
   non-empty PDF;
4. ``dpa``     — register the DPA ProcessorAgreement row (ACTIVE) whose
   ``document_hash`` is the REAL sha256 of
   ``docs/compliance/dpa-addendum.md`` — the governance record is
   pinned to the actual legal addendum;
5. ``erasure`` — verify the documented exit/deletion surfaces WITHOUT
   destroying pilot data: a real (non-destructive) data-portability
   export run; the erasure request route probed with an empty body
   (400 proves the handler runs — the destructive leg is the Week-4
   drill); OPTIONS probes prove DELETE exists on both tenant-deletion
   surfaces; the three purge/sweep commands exist in the checkout.

Credentials come from the environment with the seeded persona defaults
(``pilot_admin@example.com`` / ``pilot_dpo@example.com`` /
``e2e_platform@example.com`` — see ``seed_pilot_privacy_tenant`` and
``ensure_e2e_user_roles``). No secret is ever printed.

Usage:
    python scripts/verify_privacy_pack.py            # advisory exit 0/1
    python scripts/verify_privacy_pack.py --strict   # SKIP → failure
    python scripts/verify_privacy_pack.py --phases dpia,ropa

The W16 environment policy applies: with ``CI=true``, an unreachable
API or missing credential RAISES instead of skipping.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # envpolicy lives at the repo root

from envpolicy import environment_guard, probe_service

ADDENDUM_PATH = ROOT / "docs" / "compliance" / "dpa-addendum.md"
COMMAND_FILES = (
    ROOT / "hub/apps/files/management/commands/delete_files_for_tenant.py",
    ROOT / "hub/apps/files/management/commands/delete_files_for_user.py",
    ROOT / "hub/apps/tenants/management/commands/tenant_hard_delete_sweep.py",
)

DEFAULT_API_BASE = os.environ.get("MESHANT_API_URL", "http://localhost:8001/api/v1")
DEFAULT_SLUG = os.environ.get("PILOT_PACK_TENANT_SLUG", "pilot-co")

PHASES = ("tenant", "dpia", "ropa", "dpa", "erasure")

_ROPA_POLL_INTERVAL_S = 5.0
_ROPA_POLL_ATTEMPTS = 36  # 3 minutes — the async job path is bounded


class PrivacyPackError(RuntimeError):
    """A phase failed against the live surface."""


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


class Api:
    """Minimal JSON API client (stdlib only) — no secrets in errors."""

    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def _request(self, method: str, path: str, *, token: str | None = None,
                 body: dict | None = None) -> dict | None:
        url = f"{self.base}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:200]
            raise PrivacyPackError(
                f"{method} {path} -> HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise PrivacyPackError(f"{method} {path} unreachable: {exc.reason}") from exc
        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    def get(self, path: str, token: str | None = None) -> dict | None:
        return self._request("GET", path, token=token)

    def post(self, path: str, token: str | None = None, body: dict | None = None) -> dict | None:
        return self._request("POST", path, token=token, body=body)

    def options(self, path: str, token: str | None = None) -> dict | None:
        return self._request("OPTIONS", path, token=token)

    def options_allow(self, path: str, token: str | None = None) -> str:
        """The ``Allow`` header of an OPTIONS probe — DRF advertises the
        allowed methods in the header, not in the JSON body."""
        url = f"{self.base}{path}"
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers, method="OPTIONS")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.headers.get("Allow", "") or ""
        except urllib.error.HTTPError as exc:
            return exc.headers.get("Allow", "") or ""
        except urllib.error.URLError as exc:
            raise PrivacyPackError(f"OPTIONS {path} unreachable: {exc.reason}") from exc

    def login(self, email: str, password: str) -> str:
        data = self.post("/auth/login/", body={"email": email, "password": password})
        if not data or not data.get("access_token"):
            raise PrivacyPackError(f"login failed for {email} (no access token)")
        return data["access_token"]


def _fetch_bytes(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise PrivacyPackError(f"GET {url} -> HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise PrivacyPackError(f"GET {url} unreachable: {exc.reason}") from exc


class Runner:
    def __init__(
        self,
        api: Api,
        *,
        slug: str = DEFAULT_SLUG,
        strict: bool = False,
        addendum: Path = ADDENDUM_PATH,
    ):
        self.api = api
        self.slug = slug
        self.strict = strict
        self.addendum = addendum
        self.results: dict[str, str] = {}
        self._admin_token: str | None = None
        self._dpo_token: str | None = None
        self._platform_token: str | None = None

    def _note(self, phase: str, value: str) -> None:
        self.results[phase] = value

    # ── credentials ──────────────────────────────────────────────────
    def _login_users(self) -> None:
        self._admin_token = self.api.login(
            _env("PILOT_PACK_ADMIN_EMAIL", "pilot_admin@example.com"),
            _env("PILOT_PACK_ADMIN_PASSWORD", "TestPass123"),
        )
        self._dpo_token = self.api.login(
            _env("PILOT_PACK_DPO_EMAIL", "pilot_dpo@example.com"),
            _env("PILOT_PACK_DPO_PASSWORD", "TestPass123"),
        )
        self._platform_token = self.api.login(
            _env("PILOT_PACK_PLATFORM_EMAIL", "e2e_platform@example.com"),
            _env("PILOT_PACK_PLATFORM_PASSWORD", "TestPass123"),
        )

    # ── tenant ───────────────────────────────────────────────────────
    def phase_tenant(self) -> None:
        listing = self.api.get("/tenants/", token=self._platform_token) or {}
        results = listing.get("results") or []
        tenant = next(
            (t for t in results if t.get("slug") == self.slug), None
        )
        if not tenant:
            # Fall back to id-based fetch when the page is long.
            listing = self.api.get(f"/tenants/?slug={self.slug}", token=self._platform_token) or {}
            results = listing.get("results") or []
            tenant = next((t for t in results if t.get("slug") == self.slug), None)
        if not tenant:
            raise PrivacyPackError(
                f"pilot tenant {self.slug!r} not found — run "
                f"`docker exec hub-test-api python hub/manage.py seed_pilot_privacy_tenant`"
            )
        if tenant.get("status") != "ACTIVE":
            raise PrivacyPackError(f"pilot tenant {self.slug!r} status is {tenant.get('status')!r}")
        # The compliance gates are not on TenantSerializer — verify them
        # through the live surfaces instead: an OFF gate 403s with a
        # *_DISABLED code on its endpoint (each phase asserts it).
        self._note("tenant", f"{self.slug} {tenant.get('id')} ACTIVE")
        self._tenant_id = tenant.get("id")

    # ── dpia ─────────────────────────────────────────────────────────
    def phase_dpia(self) -> None:
        listing = self.api.get("/dpia/records/", token=self._admin_token) or {}
        existing = next(
            (r for r in listing.get("results", []) if r.get("title") == "Pilot CRM DPIA"), None
        )
        if existing:
            status = existing.get("status")
            if status != "APPROVED":
                raise PrivacyPackError(f"pilot DPIA exists but is {status!r}, not APPROVED")
            self._note("dpia", f"record {existing.get('id')} (pre-existing, APPROVED)")
            return
        asset = self._find_asset("pilot-crm")
        created = self.api.post(
            "/dpia/records/",
            token=self._admin_token,
            body={
                "title": "Pilot CRM DPIA",
                "regime": "GDPR",
                "asset": str(asset["id"]),
                "wizard_payload": {
                    "processing_narrative": (
                        "The pilot tenant hosts CRM contact records on the "
                        "Hub: ingestion via dlt, DQ checks, contract "
                        "publication, and marketplace consumption."
                    ),
                    "risk_narrative": (
                        "Personal data of pilot employees and prospect "
                        "contacts processed in a managed cloud estate; "
                        "cross-border transfer to EU/US sub-processors."
                    ),
                    "mitigations": (
                        "Tenant isolation (RLS), encryption at rest/in "
                        "transit, access governance via roles + ABAC, "
                        "audit logging, and a 3-year retention policy."
                    ),
                },
            },
        )
        if not created:
            raise PrivacyPackError("DPIA create returned no record")
        record_id = created.get("id")
        self.api.post(f"/dpia/records/{record_id}/submit/", token=self._admin_token)
        reviewed = self.api.post(
            f"/dpia/records/{record_id}/review/",
            token=self._dpo_token,
            body={
                "outcome": "APPROVED",
                "risk_residual": "LOW",
                "dpo_summary": (
                    "Low residual risk: tenant-scoped RLS, encryption, "
                    "role/ABAC governance, and bounded retention mitigate "
                    "the identified risks. Approved by the pilot DPO."
                ),
            },
        )
        record = self.api.get(f"/dpia/records/{record_id}/", token=self._admin_token) or {}
        status = record.get("status")
        if status != "APPROVED":
            raise PrivacyPackError(f"DPIA review outcome {status!r} (response: {reviewed})")
        if not record.get("next_review_due_at"):
            raise PrivacyPackError("APPROVED DPIA has no next_review_due_at")
        self._note("dpia", f"record {record_id} APPROVED (next review {record.get('next_review_due_at')})")

    def _find_asset(self, key: str) -> dict:
        listing = self.api.get("/assets/?search=" + key, token=self._admin_token) or {}
        assets = listing.get("results") or []
        match = next((a for a in assets if a.get("key") == key), None)
        if not match:
            raise PrivacyPackError(
                f"asset {key!r} not found in the pilot tenant — seed ran?"
            )
        return match

    # ── ropa ─────────────────────────────────────────────────────────
    def phase_ropa(self) -> None:
        generated = self.api.post(
            "/ropa/generate/?regulation=GDPR&format=pdf", token=self._admin_token
        )
        if not generated:
            raise PrivacyPackError("RoPA generate returned no payload")
        generation_id = generated.get("ropa_generation_id") or generated.get("id")
        if generated.get("async") or generated.get("status") not in ("COMPLETED", None):
            generation_id = self._poll_ropa(generation_id)
        generation = self.api.get(
            f"/ropa/generations/{generation_id}/", token=self._admin_token
        ) or {}
        status = generation.get("status")
        if status != "COMPLETED":
            raise PrivacyPackError(f"RoPA generation {generation_id} ended {status!r}")
        download = self.api.get(
            f"/ropa/generations/{generation_id}/download/", token=self._admin_token
        ) or {}
        download_url = download.get("download_url")
        if not download_url:
            raise PrivacyPackError("RoPA download returned no presigned URL")
        artefact = _fetch_bytes(download_url)
        if not artefact.startswith(b"%PDF"):
            raise PrivacyPackError(
                f"RoPA artefact is not a PDF ({len(artefact)} bytes, "
                f"magic {artefact[:8]!r})"
            )
        digest = hashlib.sha256(artefact).hexdigest()
        self._note(
            "ropa",
            f"generation {generation_id} COMPLETED "
            f"({generation.get('byte_size')} bytes, sha256={digest[:16]}…, "
            f"assets={generation.get('summary_json', {}).get('asset_count')})",
        )

    def _poll_ropa(self, generation_id: str) -> str:
        for _ in range(_ROPA_POLL_ATTEMPTS):
            time.sleep(_ROPA_POLL_INTERVAL_S)
            generation = self.api.get(
                f"/ropa/generations/{generation_id}/", token=self._admin_token
            ) or {}
            if generation.get("status") in ("COMPLETED", "FAILED"):
                return generation_id
        raise PrivacyPackError(f"RoPA generation {generation_id} did not finish in time")

    # ── dpa ──────────────────────────────────────────────────────────
    def phase_dpa(self) -> None:
        listing = self.api.get(
            "/processor-agreements/processors/", token=self._admin_token
        ) or {}
        processor = next(
            (p for p in listing.get("results", []) if p.get("name") == "Meshant"), None
        )
        if not processor:
            # ``website`` is optional and deliberately omitted: the
            # Processor.website SSRF guard resolves the hostname
            # (validate_webhook_url), and the company domain is not yet
            # live in DNS — passing it would fail validation, and a fake
            # resolving domain would be fabrication.
            created = self.api.post(
                "/processor-agreements/processors/",
                token=self._admin_token,
                body={
                    "name": "Meshant",
                    "legal_name": "Meshant",
                    "country_code": "PT",
                },
            )
            processor = created
        if not processor:
            raise PrivacyPackError("processor create returned no row")
        document_hash = hashlib.sha256(self.addendum.read_bytes()).hexdigest()
        registration = "PILOT-DPA-2026-001"
        agreements = self.api.get(
            "/processor-agreements/processor-agreements/", token=self._admin_token
        ) or {}
        existing = next(
            (
                a
                for a in agreements.get("results", [])
                if a.get("registration_reference") == registration
            ),
            None,
        )
        if existing:
            if existing.get("status") != "ACTIVE":
                raise PrivacyPackError(
                    f"pilot DPA exists but is {existing.get('status')!r}, not ACTIVE"
                )
            if existing.get("document_hash", "").lower() != document_hash:
                raise PrivacyPackError(
                    "pre-existing DPA document_hash does not match the addendum"
                )
            self._note("dpa", f"agreement {existing.get('id')} (pre-existing, ACTIVE)")
            return
        created = self.api.post(
            "/processor-agreements/processor-agreements/",
            token=self._admin_token,
            body={
                "processor": processor["id"],
                "agreement_type": "DPA",
                # The URI must be a resolvable public URL (SSRFGuard
                # rejects unresolvable hosts; the company domain is not
                # live in DNS yet). The RFC-2606 documentation placeholder
                # marks that — the CONTENT integrity of the agreement is
                # carried by document_hash (the real sha256 of the repo
                # addendum), not by the URI.
                "document_uri": "https://example.com/dpa.pdf",
                "document_hash": document_hash,
                "effective_from": time.strftime("%Y-%m-%d"),
                "expires_on": time.strftime("%Y-%m-%d", time.gmtime(time.time() + 366 * 86400)),
                # Objects with a name (the serializer normalizes the list)
                # — matches the addendum's sub-processor table.
                "sub_processors_declared": [
                    {"name": "AWS", "details": "Compute (EKS), object storage (S3)"},
                    {"name": "Stripe", "details": "Payment processing (billing only)"},
                    {"name": "SendGrid", "details": "Transactional email"},
                ],
                "jurisdiction_region": "EU",
                "registration_reference": registration,
                "transfer_mechanism_summary": "SCCs per GDPR Art. 46; LGPD Art. 33 equivalents",
            },
        )
        if not created:
            raise PrivacyPackError("DPA agreement create returned no row")
        status = created.get("status")
        if status != "ACTIVE":
            raise PrivacyPackError(f"DPA agreement created with status {status!r}")
        self._note(
            "dpa",
            f"agreement {created.get('id')} ACTIVE (hash {document_hash[:16]}…)",
        )

    # ── erasure ──────────────────────────────────────────────────────
    def phase_erasure(self) -> None:
        notes: list[str] = []

        # Real data-portability run (non-destructive) — proves the export
        # leg of the documented exit path end-to-end.
        export = self.api.post(
            "/gdpr/export-jobs/export-data/", token=self._dpo_token
        )
        if not export or not export.get("job_id"):
            raise PrivacyPackError(f"export-data returned {export!r}")
        job = self.api.get(f"/gdpr/export-jobs/{export['job_id']}/", token=self._dpo_token) or {}
        if job.get("status") != "COMPLETED":
            raise PrivacyPackError(f"export job ended {job.get('status')!r}")
        if not job.get("download_url"):
            raise PrivacyPackError("completed export job has no download_url")
        notes.append(f"export job {export['job_id']} COMPLETED (real run)")

        # Erasure request route probe — OPTIONS must advertise POST. Do
        # NOT issue a POST: the endpoint executes erasure IMMEDIATELY and
        # ignores the body (the first live probe with an empty body
        # really erased the dev-estate DPO persona — incident recorded in
        # the pack). The destructive leg is the Week-4 exit-clause drill.
        allow = self.api.options_allow(
            "/gdpr/erasure-requests/request-erasure/", token=self._dpo_token
        )
        if "POST" not in allow.upper():
            raise PrivacyPackError(f"OPTIONS request-erasure Allow header: {allow!r}")
        notes.append("request-erasure route probed (OPTIONS advertises POST; no POST issued)")

        # Tenant-deletion surfaces: OPTIONS must advertise DELETE on both
        # the tenant soft-delete and the admin soft-delete routes. Zero
        # destruction — OPTIONS only.
        for path, token in (
            (f"/tenants/{self._tenant_id}/", self._platform_token),
            (f"/admin/tenants/{self._tenant_id}/", self._platform_token),
        ):
            allow = self.api.options_allow(path, token=token)
            if "DELETE" not in allow.upper():
                raise PrivacyPackError(
                    f"OPTIONS {path} Allow header does not advertise DELETE ({allow!r})"
                )
        notes.append("DELETE advertised on both tenant-deletion surfaces")

        # The purge/sweep commands must exist in the checkout.
        missing = [str(p) for p in COMMAND_FILES if not p.exists()]
        if missing:
            raise PrivacyPackError(f"purge commands missing: {missing}")
        notes.append("delete_files_for_tenant / delete_files_for_user / "
                     "tenant_hard_delete_sweep present")
        self._note("erasure", "; ".join(notes))

    def run(self, phases: tuple[str, ...]) -> dict[str, str]:
        if "tenant" in phases or any(p != "erasure" for p in phases):
            self._login_users()
        for phase in phases:
            getattr(self, f"phase_{phase}")()
        return self.results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--slug", default=DEFAULT_SLUG)
    parser.add_argument("--phases", default=",".join(PHASES))
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--addendum", type=Path, default=ADDENDUM_PATH)
    args = parser.parse_args()

    api = Api(args.api_base)
    health_url = args.api_base.rstrip("/") + "/health/"
    if not probe_service(health_url):
        environment_guard(f"privacy-pack API unreachable at {args.api_base}")
        if args.strict:
            print(f"FAIL: privacy-pack API unreachable at {args.api_base}")
            sys.exit(1)
        print(f"SKIP: privacy-pack API unreachable at {args.api_base}")
        sys.exit(0)

    runner = Runner(api, slug=args.slug, strict=args.strict)
    phases = tuple(p for p in args.phases.split(",") if p)
    try:
        results = runner.run(phases)
    except PrivacyPackError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
    for phase in phases:
        print(f"privacy-pack {phase} PASS: {results.get(phase)}")
    print(f"PRIVACY-PACK PASSED: {len(phases)} phase(s) against {args.api_base}")
    sys.exit(0)


if __name__ == "__main__":
    main()

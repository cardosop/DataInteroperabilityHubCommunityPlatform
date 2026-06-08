# What is virus scanning?

When you upload a file to Meshant, we run an automated malware /
virus scan on the bytes before allowing anyone to download them.
This page explains what that means in plain terms — what's
happening, how long it takes, and what each status on your file's
detail page means.

> Phase 260.3.H.1 — customer-education content for the file-detail
> ``ScanStatusBanner``. Linked from the in-product banner via the
> "What is virus scanning?" CTA. Stable URL:
> ``/docs/concepts/virus-scanning``.

## What we scan and why

Every file is checked by an open-source malware scanner
(ClamAV) before its scan status flips to **Clean**. The check runs
once per upload — we don't re-scan files on every download.

Why we do this:

- Files in your tenant can be shared with co-workers, downloaded by
  the SDK, or published to the marketplace. If a file is
  compromised, the blast radius is everyone who downloads it.
- Compliance frameworks (SOC 2, ISO 27001, several public-sector
  standards) require an antivirus / anti-malware control on
  user-uploaded artefacts.
- Even when you trust the source of a file, mid-flight corruption
  can produce ambiguous binary content that downstream consumers
  shouldn't be expected to parse safely.

## How long does it take?

The typical scan finishes within these windows:

| File size | Typical wait |
|-----------|--------------|
| Under 100 MB | Up to 1 minute |
| 100 MB – 1 GB | Up to 3 minutes |
| 1 GB and up | Up to 6 minutes |

The customer-education banner on the file detail page shows you a
running estimate. If your scan exceeds the typical wait, the banner
switches to a **"taking longer than usual"** notice — operations is
automatically alerted and you can come back later. **Your file is
safely uploaded and stored**; only the *download* is gated until the
scan completes.

## What each status means

| Status | What's happening | What you can do |
|--------|------------------|-----------------|
| **Pending scan** | The scanner is checking the bytes. Downloads are temporarily disabled. | Wait — the file detail page polls automatically and updates without a refresh. |
| **Clean** | No malware was found. Downloads are enabled. | Download as normal. |
| **Infected** | The scanner flagged the file as malware. Downloads are permanently blocked. | If you believe this is a false positive, contact support with the file ID. We do not delete the file automatically — you can re-upload a known-good copy. |
| **Scan error** | The scanner ran but the result couldn't be persisted. | Try re-uploading the file. If the error persists across uploads, contact support. |
| **Scan unavailable** | The scanner service is temporarily down. | Wait and refresh; the platform retries automatically every few minutes. |

## Frequently asked questions

### Can I download a file that's still pending the scan?
No — downloads are disabled until the status reaches **Clean** so we
never serve un-scanned bytes. This protects everyone in your tenant
(and any marketplace consumer who has an entitlement to the file).

### Can I bypass the scan for a known-good file?
No. The scan runs on every upload, regardless of source. If you have
a workflow that needs to skip the scan for performance reasons,
contact support — there's a tenant-level scanning configuration for
edge cases like large pre-validated archives.

### What antivirus engine do you use?
ClamAV, the open-source standard. It runs in a sandboxed container
inside our deployment and is updated daily with the latest signature
database.

### Where does the scan run?
On our infrastructure, never on your machine. The bytes go from your
upload directly to S3 and the scanner reads them in-region — the
file never leaves the platform.

### Does the scan affect my upload speed?
No. The upload completes as soon as the bytes finish transferring to
S3. The scan runs *afterward*, in parallel; it only gates *downloads*
of the file.

## Related

- **API reference:** [Files endpoints](../api-reference/files.md)
- **Operational runbook:** [File virus-scan incident response](../../runbooks/file-virus-scan-incident.md)
- **Phase 260.3.H.1** — customer-education banner spec.

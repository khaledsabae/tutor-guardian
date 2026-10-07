# Publish the verified bundle at 100%

Khaled has authorized a completed production release for all users. This local
operator tool supplies the final publication stage after the hosted unsigned
build, local upload-key signing, signed-payload inspection and successful
validate-only Play edit described in `hosted-unsigned-aab.md`.

`scripts/release_play_publish.py` never builds or signs. It requires the explicit
`--publish-completed-production` switch, the same AAB, unsigned map, signed
inspection manifest, pinned bundletool and exact version-specific Arabic/English
notes, plus the successful `--validated-receipt`. Supply the existing local
service-account path with `--sa`, and a fresh private `--journal` path. Exact
`--source-sha`, `--version`, `--expected-aab-sha256` and
`--expected-upload-cert-sha256` are mandatory. These hashes identify the reviewed
artifact; none is a signing password. Passwords and private key files remain
local and must never enter GitHub secrets or command values.

Reuse an existing verified Python runtime that already provides `google-auth`
and `google-api-python-client`, including a bundled runtime when available.
Check imports of `google.oauth2.service_account`, `googleapiclient.discovery`
and `googleapiclient.http` offline before invoking the release helpers; an API
permission probe alone does not prove those local imports are available. No
package installation is needed when this check succeeds. Preserve the primary
project environment; if dependencies are unavailable, use a separate private,
lightweight environment. This import check neither signs nor uploads a bundle.

The tool freezes private read-only copies, re-inspects the signed AAB and binds
every validation-receipt field to the copied payload, certificate, source SHA,
unsigned-map hash and notes hash before contacting Play. It reserves a new
0600 journal before any API call. It never reads a checkout's pubspec or reuses
a versionCode solely because that version exists: any existing matching code
must have the exact validated AAB SHA256, or publication stops. This allows the
exact previously accepted bundle to be reused if Play retains it after the
validate-only edit, without accepting a different artifact with the same code.

Inside its own edit it stages `production`, `status: completed`, only the exact
versionCode, and no `userFraction` (100% rollout), then validates again. It
flushes `commit_attempted` to the private journal before its single commit call
with `changesNotSentForReview=false`. Failures before that call delete only our
own edit. If the response to commit is lost, it leaves
`commit_outcome_unknown`, stops, and does not retry or delete an edit that may
already have been committed. Inspect Play's actual state before any later run.

A `committed` journal means Play accepted the production submission. It does
**not** prove store availability: review and managed publication can still be
pending. Check the actual Console publication state and production version
before reporting the release live. A previous journal must never be overwritten.
No Play edit, signing operation or compilation is performed by the offline tests.

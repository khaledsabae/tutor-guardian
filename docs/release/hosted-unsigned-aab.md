# Hosted unsigned AAB and local upload-key boundary

This build-only workflow is based on main after PR60 merged as
`5d566611efb09808bb4b94f47ae7ea25b0abe4b2`. The user has authorized development,
PR merge, hosted build dispatch, local signing, upload and a full 100% Play rollout.
This worktree's current task is documentation correction, commit, push and PR
creation; dispatch, build, signing and upload remain separate execution steps.
The workflow does not publish to Play, contain production signing secrets, or
start a local build. No local emulator or APK/AAB compilation is authorized;
the production upload key must never be uploaded.

## Build and provenance

`Unsigned release bundle` tests its verifier on PRs. Its build job runs only on
a manual dispatch of main, checking out exactly `github.sha`. Its required
`approved_source_sha` input must be the full reviewed 40-character SHA and must
equal both `github.sha` and checkout HEAD; empty, abbreviated and different SHAs
fail before SDK setup or compilation. Tracked and untracked source changes also
fail. It accepts no alternate source ref. A later build needs an approved main
commit containing this implementation. All compilation runs on a GitHub-hosted runner.

The build is `flutter build appbundle --release`, Flutter 3.44.1 / Java17,
with no ABI restriction, Dart define, E2E helper or Analytics alteration. R8
and resource shrinking remain enabled. `TG_CI_UNSIGNED_AAB=true` is scoped to
that command and guarded against accidental use outside GitHub Actions. These
environment variables are not authentication; dispatch gating and SHA checks
provide the workflow boundary. Ordinary release signing
retains the existing upload-key/debug-fallback behavior when the flag is absent.
The workflow rejects local key files on the runner and never requests secrets.

Artifact `unsigned-release-<full SHA>` contains the unsigned AAB and
`unsigned-manifest.json`: source SHA, package, version, whole-AAB SHA256,
production manifest hash, pinned bundletool version/hash and every payload
entry's uncompressed SHA256 and size. The build records production API source
configuration hashes; that is provenance for the fixed build command, not an
independent extraction of API constants from compiled Dart code.

Bundletool 1.18.3 SHA256 is pinned to the release asset digest published by
Google's [official GitHub release](https://github.com/google/bundletool/releases/tag/1.18.3).
The release API's asset `digest` was independently checked on 2026-10-07 and equals
`sha256:a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29`.
Its digest is checked before `validate` and manifest
inspection. The verifier rejects package/version mismatch, debug/testOnly,
missing/old target SDK, E2E Analytics deactivation, duplicate ZIP entries and
any JAR signing envelope in an allegedly unsigned AAB. Every bundle must contain
nonempty `libapp.so` and `libflutter.so` for `armeabi-v7a`, `arm64-v8a` and
`x86_64`. An explicit false or resource-based Analytics collection setting is
rejected alongside the E2E deactivation marker.

## Later local signing, without local compilation

The production upload key and passwords stay local. Signing is a separate
operator-controlled step; these tools never sign. Passwords must not enter
command arguments, shell history, logs or GitHub secrets. JDK17 signing must use
only environment-backed password options: `-storepass:env TG_UPLOAD_STORE_PASSWORD`
and `-keypass:env TG_UPLOAD_KEY_PASSWORD`. Populate those process-local variables
through the existing private local credential channel without printing values or
recording them in shell history. Never use interactive password prompts or literal
password argument values. Never use a debug-signed E2E APK or bundle as a release.

After signing a copy, run `scripts/release_bundle.py signed` with the original
unsigned map, pinned bundletool, full source SHA, exact version, expected signed
AAB SHA256 and expected local upload certificate SHA256. This command performs
lightweight Java validation/signature inspection, not Flutter/Gradle compilation.
It can run in a small verification environment if local resources do not permit
bundletool. The unsigned map remains the authoritative payload baseline. Local signed verification
does not depend on a checkout pubspec; the version comes from that frozen map.

Only direct `META-INF/MANIFEST.MF`, `.SF`, `.RSA`, `.DSA`, `.EC`, and `SIG-*`
JAR envelope files are excluded from the signed-copy comparison. All other
entries, including nested META-INF resources, must have identical names,
sizes and hashes. The unsigned input must contain no such envelope, so no
original manifest content is discarded. `jarsigner -verify` must report a
verified JAR with no unsigned entries or verdict treating weak signatures as unsigned;
keytool's certificate fingerprint must
match the supplied fingerprint and must not be an Android Debug certificate.
Self-signed certificate warnings are expected for upload keys and do not alone
establish failure or Play acceptance.

## Play acceptance proof, with no commit

The Play Console upload certificate has **not** been read in this task. Matching
the local key's fingerprint only proves local consistency. Play acceptance of
the exact package/version/certificate is established only by a later successful
API upload and validation in our own temporary edit.

`scripts/release_play_validate.py` requires explicit paths to the AAB, signed
manifest, unsigned map, pinned bundletool, bilingual notes, existing local
service account and output receipt; it also requires explicit source SHA,
version, signed-AAB SHA256 and expected local certificate fingerprint. It
copies the AAB, unsigned map and notes into a private directory, makes those
copies read-only, and rechecks its digest, payload, manifest and signature
before any remote request. The entire signed report must match fresh inspection,
including the certificate and frozen unsigned-map hash. It never reads a dirty
checkout's pubspec113. Receipt hashes describe the frozen inputs actually used;
the receipt is created exclusively with private permissions and cannot overwrite
a concurrently created file.

It creates its own edit, always uploads this exact AAB, requires Play to return
the expected versionCode **and exact uploaded SHA256**, stages a completed production release inside that
uncommitted edit, calls `edits.validate`, then deletes its edit on success or
failure. **It has no commit call.** A cleanup failure is a failed run. A success
receipt records the exact artifact SHA and the successful upload/validate/delete;
it is not a published-release receipt. An app release already awaiting review,
permissions, version-code reuse, quotas or Play policy can still reject this
validation. The user reports a prior actual permission probe with request statuses
200/200/204 and production version113 completed. Its private
`tmp/tg-play-permission-probe/proof.json` was unavailable on this host during this
review, so those observations were not independently re-read or repeated. They
do not prove acceptance of version114 or its upload certificate; the later exact
AAB upload and validation must establish that.

The existing `scripts/play_upload.py --dry-run` only checks file existence and
notes; it is not validation. The legacy uploader/publishing workflow is unchanged.
For the authorized 100% publication, `scripts/release_play_publish.py` consumes
and rechecks the same validated artifact identity; versionCode reuse also requires
the exact AAB SHA256. Do not treat the validate-only receipt as permission to
publish a different artifact. The final publication stage and its private journal
are described in [verified-play-publication.md](verified-play-publication.md).

## Offline tests and scope

Tests use synthetic ZIP/XML and fake Play requests; no APK/AAB compilation,
real signing, Play request, credentials read, emulator, or model call is needed.
PR60's separate release-note fixture correction is already included in this
worktree's main baseline `5d566611`, without a separate test edit here. No
production keystore or service-account values were inspected.

Fresh baseline validation: 16 bundle/workflow tests and 6 Play lifecycle tests,
both exit0. After review, 22 bundle/workflow tests and 11 Play tests pass, both
exit0. New regressions failed before fixes for source approval, untracked source
changes, missing ABIs, disabled Analytics, missing Play digests, weak signatures,
signed-report tampering and mutable receipt inputs/receipt overwrite races.
Synthetic integration tests exercise the complete signed-inspection path and
validate-only CLI without running Java or contacting Play. Python AST, YAML,
Bash syntax checks and `git diff --check` exit0. These are offline tests only; no
hosted bundle or Play acceptance receipt exists yet.

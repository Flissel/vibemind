# Proxmox image pinning

## Scope and boundaries

This runbook describes how to resolve, apply, verify, and rotate the image
digest pins required by `docs/contracts/proxmox-image-determinism-v1.md`.

It is repository work. It does not perform or prove a runtime operation: it
performs no deployment, no `docker pull`, no stack update, no Proxmox action,
and no change to any running service. `deployment_proven=false` and
`golden_path_proven=false` remain true in every state described here. Applying
a pin changes what a *later*, separately authorized deployment would resolve;
it does not change what is running now.

## Preconditions

- A clean working tree. The determinism check fails closed on uncommitted or
  staged modifications to an in-scope manifest, so a dirty tree cannot be
  verified.
- Outbound HTTPS to the registry that hosts the image, for the resolution step
  only. Verification itself is fully offline.
- No Docker daemon, no Proxmox credentials, and no host access are required at
  any point. If a procedure seems to need them, stop — it is not this one.

## Resolving a digest

The digest of a tag is the SHA-256 of the raw manifest bytes the registry
returns for that tag. It is read with an ordinary HTTP GET; nothing is pulled,
stored, or mutated.

Pin the *manifest list* (index) digest, not a per-platform manifest digest. The
index digest is what `docker` resolves a tag to, and it stays correct across
architectures.

1. Get a pull token for the repository.

   - Docker Hub: `https://auth.docker.io/token?service=registry.docker.io&scope=repository:<repository>:pull`,
     where `<repository>` is `library/postgres` for an official image and
     `gitea/gitea` for a namespaced one.
   - Amazon ECR Public: `https://public.ecr.aws/token/?scope=repository:<repository>:pull`.

2. GET `https://<registry>/v2/<repository>/manifests/<tag>` with that token as
   `Authorization: Bearer <token>` and an `Accept` header listing
   `application/vnd.oci.image.index.v1+json`,
   `application/vnd.docker.distribution.manifest.list.v2+json`,
   `application/vnd.oci.image.manifest.v1+json`, and
   `application/vnd.docker.distribution.manifest.v2+json`. Omitting the index
   media types makes the registry return a single-platform manifest, whose
   digest is the wrong thing to pin.

3. Take the digest from the `Docker-Content-Digest` response header.

   Amazon ECR Public does not send that header. There, compute the digest as
   `sha256:` + the SHA-256 of the exact response body — that is the definition
   the header would otherwise report. Before relying on the computed value,
   confirm the method against a registry that *does* send the header: for the
   same request, `sha256(body)` and `Docker-Content-Digest` must be identical.
   If they are not, stop; something is rewriting the response.

4. Fetch twice and confirm the digest is identical both times. A tag that moves
   between two reads is being republished, and pinning mid-flight records a
   digest nobody reviewed.

Never write a digest that was not read from a registry in this way. A guessed,
remembered, or pattern-matched digest is worse than a floating tag: it fails at
pull time on the deployment host, after the manifest has already passed review.

## Applying a pin

Keep the existing tag and append the digest, so the reference reads
`<name>:<tag>@sha256:<digest>`. Do not change the tag in the same commit as the
pin — pinning the bits that a tag already resolves to is a no-op for what gets
deployed, while changing the tag is a version bump. Keeping them separate keeps
that distinction reviewable.

Apply the pin in `infra/swarm/vibemind-stack.yml` as well as in any
`infra/proxmox/*-docker-compose.yml` that carries the same reference. The phase
manifests are generated from the stack by `infra/proxmox/extract_compose.py`;
a pin that exists only in a generated manifest is lost at the next
regeneration. To confirm the two agree:

```
python infra/proxmox/extract_compose.py phase1 | grep 'image:'
```

The output must match the `image:` lines of the committed phase manifest.

## Verifying

```
python infra/proxmox/image_determinism.py --repo .
```

Exit 0 with `"ready": true` means every in-scope reference is deterministic or
admissibly waived. Exit 2 means blocked; each finding names the manifest and
line. Findings are: `image-reference-not-deterministic`, `waiver-reason-missing`,
`waiver-not-admissible`, `waiver-stale`, `policy-unreadable`,
`manifest-unreadable`, `manifest-untracked`, and `repository-unavailable`.

Commit the manifests before verifying. The check reads committed content and
fails closed on a dirty in-scope manifest, so an unverified pin is indistinguishable
from a modified one.

The regression suites are:

```
python -m pytest tests/deployment/test_image_determinism.py
pwsh -NoProfile -Command "Invoke-Pester tests/deployment/image-determinism.Tests.ps1"
```

## Adding a locally built image

An image built on the deployment host has no registry digest. Add it to the
`waivers` list in `infra/proxmox/image-determinism-policy.json` with a reason
stating where it is built and why no digest exists. A waiver for an image a
registry could resolve is rejected — pin that one instead.

When a locally built image is retired, remove its waiver in the same change
that removes its last reference. A waiver matching no reference blocks readiness.

## Rotating a pin

Rotation is a reviewed content change, never routine maintenance.

1. Establish the reason: a security advisory, a required upstream fix, or a
   deliberate version bump. "The pin is old" is not a reason.
2. Resolve the new digest exactly as above.
3. Replace tag and digest together in the stack and in every affected phase
   manifest, and say in the commit message which version moved to which, and why.
4. Re-run the verification above.
5. Deploying the rotated pin needs request-specific authority. This runbook
   grants none. A verified manifest is a precondition for a deployment
   proposal, not an approval of one.

## Stop criteria

Stop and escalate rather than proceeding when:

- a registry returns a different digest on two consecutive reads for the same tag;
- an ECR-style computed digest disagrees with a `Docker-Content-Digest` header
  on a control image;
- the determinism check reports a finding that a pin was expected to clear; or
- a change would require waiving an image a registry can resolve.

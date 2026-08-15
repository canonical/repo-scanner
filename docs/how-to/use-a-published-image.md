# Use a published image

The container backends run scans in a single tool image that holds every pinned
tool. By default reposcan builds that image locally on first use and reuses it
afterward. You can instead run a published image, or manage the local build.

## Run a published image

Point reposcan at a remote OCI image with the `image` config key. The
`canonical` shorthand resolves to the image published for this project:

    reposcan config set image canonical
    reposcan scan sbom ./repo            # pulls and runs the published image

Any explicit OCI reference works too, including a digest-pinned one:

    reposcan config set image ghcr.io/canonical/repo-scanner:latest
    reposcan config set image ghcr.io/canonical/repo-scanner@sha256:...

reposcan verifies a pulled image before running it: a digest-pinned reference is
trusted by content, and a tag-only reference is pinned on first use and refused
later if the tag has moved to different content. Clear the key to go back to
building locally:

    reposcan config unset image

The published-image path is Docker-only; the LXD backend always builds locally.

## Build the image locally

Build (or rebuild) the tool image without running a scan:

    reposcan image build
    reposcan image build --backend docker

The image is content-addressed by a digest of its build script, so reposcan
reuses an existing image when nothing has changed and rebuilds when a tool
version, hash, or the base image changes.

## Manage the image record

reposcan records the identity of each image it built or pulled, which is how it
verifies reuse and detects a moved tag. Inspect or clear that record:

    reposcan image cache list
    reposcan image cache remove <reference>
    reposcan image cache clear

If a pull is refused because a tag moved, `image cache remove` clears the stale
entry so the new content can be trusted on the next pull.

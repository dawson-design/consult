"""The shared verifier image: every image it pulls names a version, never `latest`.

python3 -m unittest discover eval/verifier/tests
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[1] / "shared" / "Dockerfile"
# `FROM [--platform=...] image[:tag][@digest] [AS name]` and `COPY [flags] --from=image[:tag][@digest]`.
FROM_RE = re.compile(r"^\s*FROM\s+(?:--\S+\s+)*(\S+)", re.MULTILINE | re.IGNORECASE)
COPY_FROM_RE = re.compile(r"^\s*COPY\s+(?:--(?!from=)\S+\s+)*--from=(\S+)", re.MULTILINE | re.IGNORECASE)


STAGE_RE = re.compile(r"^\s*FROM\s+(?:--\S+\s+)*\S+\s+AS\s+(\S+)", re.MULTILINE | re.IGNORECASE)


def is_build_stage(source: str, stages: set[str]) -> bool:
    """A COPY --from source that names a stage (Docker lowercases the names) or gives a stage index."""
    return source.lower() in stages or source.isdigit()


def pulled_images(text: str) -> list[str]:
    """Every image the build pulls: FROM images, and COPY --from sources that are not a build stage."""
    stages = {name.lower() for name in STAGE_RE.findall(text)}
    return FROM_RE.findall(text) + [
        source for source in COPY_FROM_RE.findall(text) if not is_build_stage(source, stages)
    ]


def is_pinned(image: str) -> bool:
    """A digest, or a tag other than latest; the tag follows the last colon after the last slash."""
    if "@sha256:" in image:
        return True
    _, colon, tag = image.rsplit("/", 1)[-1].partition(":")
    return bool(colon) and tag.lower() != "latest"


class DockerfilePinTests(unittest.TestCase):
    def test_a_copy_from_a_build_stage_is_not_a_pulled_image(self):
        text = (
            "FROM node:22-bookworm-slim AS Build\nCOPY --from=build /out /out\nCOPY --from=0 /b /b\n"
            "COPY --from=ghcr.io/x/y:1.2 /a /a\n"
        )

        self.assertEqual(pulled_images(text), ["node:22-bookworm-slim", "ghcr.io/x/y:1.2"])

    def test_every_pulled_image_names_a_version(self):
        images = pulled_images(DOCKERFILE.read_text())

        self.assertTrue(images, "no FROM or COPY --from images found")
        self.assertEqual([image for image in images if not is_pinned(image)], [])


if __name__ == "__main__":
    unittest.main()

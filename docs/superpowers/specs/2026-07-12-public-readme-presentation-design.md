# Public README Presentation Design

## Purpose

Make the repository's public landing page clear, credible, and easy to scan
while accurately representing the project as an initial scaffold.

## Scope

- Add a compact badge row for CI, CodeQL, Codecov coverage, latest release,
  Python 3.12+, Apache-2.0, and scaffold status.
- Link badges to their authoritative GitHub, Codecov, release, and license
  destinations.
- Improve the README's opening copy and section flow for public readers.
- Preserve the existing setup, verification, automation, and layout details.

## Constraints

- Do not claim a released plug-in or implemented image-treatment behavior.
- The release badge may be present before the first release and should activate
  naturally when Release Please publishes one.
- Do not add dependencies, workflows, product behavior, or external services.

## Verification

- Check Markdown links and image URLs for the intended repository paths.
- Run the existing formatting, linting, type, and test verification commands.
- Review the final diff to confirm the change is limited to documentation.

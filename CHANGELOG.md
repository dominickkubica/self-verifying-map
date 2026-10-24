# Changelog

All notable changes to `lean-agent-kit`. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `lean-agents` command: `carry-cost`, `stats`, `slim`, `prefetch` and `map`.
- `lean-agents map generate | check | stamp`: the self-verifying map, configured by
  `map/config.json`, with generic extractors for modules, SQL tables and HTTP routes
  (decorators or an OpenAPI file), and plugins for anything stack-specific.
- Python 3.10 to 3.13 on Linux, macOS and Windows; no runtime dependencies.

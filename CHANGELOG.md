# Changelog

All notable changes to `lean-agent-kit`. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-24

The first release: the tools behind the measurements in this repository, installable as
one command.

### Added

- `lean-agents carry-cost`: ranks what costs tokens in your own Claude Code transcripts,
  each source weighted by how many later API calls re-read it.
- `lean-agents stats`: per-request tokens, tool calls, searches and re-reads, with a
  before/after split and CSV output.
- `lean-agents slim`: splits an instruction file into a small core and sections read on
  demand.
- `lean-agents prefetch`: a `UserPromptSubmit` hook that injects verified map facts about
  whatever the prompt names.
- `lean-agents map generate | check | stamp`: the self-verifying map, configured by
  `map/config.json`, with generic extractors for modules, SQL tables and HTTP routes
  (decorators or an OpenAPI file), and plugins for anything stack-specific.
- Neither transcript analyzer prints or writes message content; a test guards it.
- Python 3.10 to 3.13 on Linux, macOS and Windows; no runtime dependencies.

[Unreleased]: https://github.com/dominickkubica/self-verifying-map/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/dominickkubica/self-verifying-map/releases/tag/v0.1.0

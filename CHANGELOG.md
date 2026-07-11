# Changelog

> 完整变更日志见 [docs/changelog.md](docs/changelog.md)。

## v0.1.2 (2026-07-11)

### Fixes
- AssetMCP/DataMCP `embed()` → ModelServing `/v1/embeddings` (was 404 on Server)
- Memory search: L2 → cosine metric (score was always 0 with L2)
- `verify_full.py`: adapted for ModelServing architecture (286/286 L0-L8 PASS)

### Added
- `examples/meeting-agent/` — browser real-time meeting agent demo
- `examples/lakemind-connector/` — opencode Skill for LakeMind cognitive backend
- `README_agent.md` — agent-facing onboarding guide

## v0.1.1 ( 2026-07-10)

- LakeMindModelServing: litellm + fastembed + FunASR (:10824)
- Steward LLM dialog via ModelServing
- Monitor frontend fixes

## v0.1.0 (2026-07-06)

- Initial release: 13 containers, 10 engines, 58 MCP tools, 297/297 tests pass
- See [docs/release-notes-v0.1.0.md](docs/release-notes-v0.1.0.md) for full notes

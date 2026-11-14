# Benchmark Retrieval Results Summary

Generated at: 2026-11-14 12:36:07
Embedding Model: `nomic-embed-text` (dim: 768)

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) |
|---|---|---|---|
| `A_fixed_size` | **dev** | 4/15 (26.7%) | 6/15 (40.0%) |
| `A_fixed_size` | **test** | 2/5 (40.0%) | 2/5 (40.0%) |
| `B_by_paragraph` | **dev** | 4/15 (26.7%) | 7/15 (46.7%) |
| `B_by_paragraph` | **test** | 2/5 (40.0%) | 3/5 (60.0%) |
| `C_by_paragraph_filter` | **dev** | 4/15 (26.7%) | 8/15 (53.3%) |
| `C_by_paragraph_filter` | **test** | 2/5 (40.0%) | 3/5 (60.0%) |
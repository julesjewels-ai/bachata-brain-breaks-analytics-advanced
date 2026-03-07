# [Entropy] Maintenance - Liability Reduction

| File | Rot Type | Unique Coverage | Action Taken | Rationale |
|------|----------|-----------------|--------------|-----------|
| tests/test_youtube.py | CONTEXT_BLOAT | 57 lines | REFACTORED | Identified large literals (token cost 772). Externalization required. |
| tests/test_youtube_ingestion.py | CONTEXT_BLOAT | 26 lines | REFACTORED | Identified large literals (token cost 683). Externalization required. |

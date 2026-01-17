"""Utility functions."""

# Legacy API (simple interface)
from src.utils.truncate import (
    limit_output,
    limit_lines,
    smart_truncate,
    limit_output_bytes,
    truncate_output,
    estimate_tokens,
    APPROX_BYTES_PER_TOKEN,
    DEFAULT_MAX_TOKENS,
)

# Full fabric-core API
from src.utils.truncate import (
    TruncateStrategy,
    TruncateConfig,
    TruncateResult,
    TokenEstimator,
    TruncateBuilder,
    truncate,
    truncate_file,
    truncate_batch,
)

__all__ = [
    # Legacy
    "limit_output",
    "limit_lines", 
    "smart_truncate",
    "limit_output_bytes",
    "truncate_output",
    "estimate_tokens",
    "APPROX_BYTES_PER_TOKEN",
    "DEFAULT_MAX_TOKENS",
    # Full API
    "TruncateStrategy",
    "TruncateConfig",
    "TruncateResult",
    "TokenEstimator",
    "TruncateBuilder",
    "truncate",
    "truncate_file",
    "truncate_batch",
]

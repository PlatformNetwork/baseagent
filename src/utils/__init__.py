"""Utility functions."""

# Legacy API (simple interface)
# Full fabric-core API
from src.utils.truncate import (
    APPROX_BYTES_PER_TOKEN,
    DEFAULT_MAX_TOKENS,
    TokenEstimator,
    TruncateBuilder,
    TruncateConfig,
    TruncateResult,
    TruncateStrategy,
    estimate_tokens,
    limit_lines,
    limit_output,
    limit_output_bytes,
    smart_truncate,
    truncate,
    truncate_batch,
    truncate_file,
    truncate_output,
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

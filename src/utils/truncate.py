"""
Text truncation and summarization utilities.

Provides intelligent truncation of text content for context management,
supporting various strategies and format preservation.

Port of fabric-core/src/truncate.rs
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class TruncateStrategy(Enum):
    """Truncation strategy."""
    
    # Truncate from the end (keep beginning)
    END = "end"
    # Truncate from the beginning (keep end)
    START = "start"
    # Keep both ends, remove middle
    MIDDLE = "middle"
    # Smart truncation based on content analysis
    SMART = "smart"
    # Summarize instead of truncate
    SUMMARIZE = "summarize"


@dataclass
class TruncateConfig:
    """Truncation configuration."""
    
    # Maximum length in characters
    max_chars: int = 10000
    # Maximum length in tokens (approximate)
    max_tokens: Optional[int] = None
    # Truncation strategy
    strategy: TruncateStrategy = TruncateStrategy.END
    # Suffix to add when truncated
    suffix: str = "... [truncated]"
    # Prefix to add when truncated
    prefix: str = ""
    # Preserve code blocks
    preserve_code: bool = True
    # Preserve markdown structure
    preserve_markdown: bool = True
    # Word boundary alignment
    word_boundary: bool = True
    # Sentence boundary alignment
    sentence_boundary: bool = False
    # Line boundary alignment
    line_boundary: bool = False


@dataclass
class TruncateResult:
    """Truncation result."""
    
    # Resulting text
    text: str
    # Whether truncation occurred
    truncated: bool
    # Original character count
    original_chars: int
    # Final character count
    final_chars: int
    # Original estimated tokens
    original_tokens: int
    # Final estimated tokens
    final_tokens: int
    # Strategy that was used
    strategy_used: TruncateStrategy
    
    def reduction_percent(self) -> float:
        """Get reduction percentage."""
        if self.original_chars == 0:
            return 0.0
        return (1.0 - (self.final_chars / self.original_chars)) * 100.0
    
    def is_ok(self) -> bool:
        """Check if truncation was successful."""
        return len(self.text) > 0


def estimate_tokens(text: str) -> int:
    """
    Estimate token count (rough approximation).
    
    Rough estimate: ~4 chars per token for English.
    This is a simplification - real tokenization varies by model.
    """
    char_count = len(text)
    word_count = len(text.split())
    
    # Average of character-based and word-based estimates
    return (char_count // 4 + word_count) // 2


class TokenEstimator:
    """More accurate token estimation with caching."""
    
    def __init__(self, chars_per_token: float = 4.0):
        """Create a new estimator."""
        self._cache: Dict[str, int] = {}
        self._chars_per_token = chars_per_token
    
    @classmethod
    def with_ratio(cls, chars_per_token: float) -> "TokenEstimator":
        """Create with custom ratio."""
        return cls(chars_per_token=chars_per_token)
    
    def estimate(self, text: str) -> int:
        """Estimate tokens for text."""
        # Create hash for caching
        text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
        
        if text_hash in self._cache:
            return self._cache[text_hash]
        
        estimate = self._calculate(text)
        
        # Cache if not too large
        if len(self._cache) < 10000:
            self._cache[text_hash] = estimate
        
        return estimate
    
    def _calculate(self, text: str) -> int:
        """Calculate token estimate."""
        char_count = len(text)
        return int((char_count / self._chars_per_token) + 0.5)  # ceil-like rounding
    
    def calibrate(self, samples: List[Tuple[str, int]]) -> None:
        """Calibrate ratio based on actual token counts."""
        if not samples:
            return
        
        total_chars = sum(len(text) for text, _ in samples)
        total_tokens = sum(tokens for _, tokens in samples)
        
        if total_tokens > 0:
            self._chars_per_token = total_chars / total_tokens
    
    def clear_cache(self) -> None:
        """Clear cache."""
        self._cache.clear()


def truncate(text: str, config: TruncateConfig) -> TruncateResult:
    """Truncate text according to configuration."""
    original_len = len(text)
    original_tokens = estimate_tokens(text)
    
    # Check if truncation needed
    needs_truncation = original_len > config.max_chars
    if config.max_tokens is not None:
        needs_truncation = needs_truncation or (original_tokens > config.max_tokens)
    
    if not needs_truncation:
        return TruncateResult(
            text=text,
            truncated=False,
            original_chars=original_len,
            final_chars=original_len,
            original_tokens=original_tokens,
            final_tokens=original_tokens,
            strategy_used=config.strategy,
        )
    
    # Apply truncation strategy
    if config.strategy == TruncateStrategy.END:
        truncated_text = truncate_end(text, config)
    elif config.strategy == TruncateStrategy.START:
        truncated_text = truncate_start(text, config)
    elif config.strategy == TruncateStrategy.MIDDLE:
        truncated_text = truncate_middle(text, config)
    elif config.strategy == TruncateStrategy.SMART:
        truncated_text = truncate_smart(text, config)
    elif config.strategy == TruncateStrategy.SUMMARIZE:
        truncated_text = _truncate_summarize(text, config)
    else:
        truncated_text = truncate_end(text, config)
    
    final_len = len(truncated_text)
    final_tokens = estimate_tokens(truncated_text)
    
    return TruncateResult(
        text=truncated_text,
        truncated=True,
        original_chars=original_len,
        final_chars=final_len,
        original_tokens=original_tokens,
        final_tokens=final_tokens,
        strategy_used=config.strategy,
    )


def truncate_end(text: str, config: TruncateConfig) -> str:
    """Simple truncation from end."""
    target_len = max(0, config.max_chars - len(config.suffix))
    
    if len(text) <= target_len:
        return text
    
    end = target_len
    
    # Align to boundary
    if config.sentence_boundary:
        end = find_sentence_boundary(text, end, forward=False)
    elif config.line_boundary:
        end = find_line_boundary(text, end, forward=False)
    elif config.word_boundary:
        end = find_word_boundary(text, end, forward=False)
    
    return f"{text[:end]}{config.suffix}"


def truncate_start(text: str, config: TruncateConfig) -> str:
    """Truncation from start (keep end)."""
    target_len = max(0, config.max_chars - len(config.prefix))
    
    if len(text) <= target_len:
        return text
    
    start = len(text) - target_len
    
    # Align to boundary
    if config.sentence_boundary:
        start = find_sentence_boundary(text, start, forward=True)
    elif config.line_boundary:
        start = find_line_boundary(text, start, forward=True)
    elif config.word_boundary:
        start = find_word_boundary(text, start, forward=True)
    
    return f"{config.prefix}{text[start:]}"


def truncate_middle(text: str, config: TruncateConfig) -> str:
    """Truncation from middle (keep both ends)."""
    separator = "\n\n[...content omitted...]\n\n"
    target_len = max(0, config.max_chars - len(separator))
    
    if len(text) <= target_len:
        return text
    
    keep_each = target_len // 2
    start_end = _find_boundary(text, keep_each, forward=True, config=config)
    end_start = len(text) - _find_boundary(text, keep_each, forward=False, config=config)
    
    return f"{text[:start_end]}{separator}{text[end_start:]}"


def truncate_smart(text: str, config: TruncateConfig) -> str:
    """Smart truncation based on content analysis."""
    # Analyze content structure
    has_code = "```" in text or "    " in text
    has_lists = "\n- " in text or "\n* " in text or "\n1." in text
    has_headers = "\n#" in text or "\n==" in text
    
    # Choose strategy based on content
    if has_code and config.preserve_code:
        return truncate_preserve_code(text, config)
    elif has_lists or has_headers:
        return truncate_preserve_structure(text, config)
    else:
        return truncate_end(text, config)


def truncate_preserve_code(text: str, config: TruncateConfig) -> str:
    """Truncate while preserving code blocks."""
    result: List[str] = []
    remaining = config.max_chars
    in_code_block = False
    code_block_content: List[str] = []
    
    for line in text.split('\n'):
        if line.startswith("```"):
            if in_code_block:
                # End of code block - add it if it fits
                code_block_content.append(line)
                code_block_content.append('')  # For the newline
                
                block_text = '\n'.join(code_block_content)
                if len(block_text) <= remaining:
                    result.append(block_text)
                    remaining -= len(block_text)
                code_block_content.clear()
                in_code_block = False
            else:
                # Start of code block
                in_code_block = True
                code_block_content.append(line)
        elif in_code_block:
            code_block_content.append(line)
        else:
            line_len = len(line) + 1  # +1 for newline
            if line_len <= remaining:
                result.append(line)
                result.append('')  # For newline
                remaining -= line_len
            else:
                break
    
    result_text = '\n'.join(result)
    if len(result_text) < len(text):
        result_text += config.suffix
    
    return result_text


def truncate_preserve_structure(text: str, config: TruncateConfig) -> str:
    """Truncate while preserving document structure."""
    result: List[str] = []
    remaining = max(0, config.max_chars - len(config.suffix))
    current_section: List[str] = []
    section_header = ""
    
    for line in text.split('\n'):
        is_header = (
            line.startswith('#') or 
            line.startswith("==") or 
            line.startswith("--")
        )
        
        if is_header:
            # Flush previous section
            section_content = '\n'.join(current_section)
            total_section = section_header + section_content
            if current_section and len(total_section) <= remaining:
                result.append(total_section)
                remaining -= len(total_section)
            section_header = f"{line}\n"
            current_section.clear()
        else:
            current_section.append(line)
        
        if remaining == 0:
            break
    
    # Add last section if it fits
    if current_section:
        section_content = '\n'.join(current_section)
        total_section = section_header + section_content
        if len(total_section) <= remaining:
            result.append(total_section)
    
    result_text = ''.join(result)
    if len(result_text) < len(text):
        result_text += config.suffix
    
    return result_text


def _truncate_summarize(text: str, config: TruncateConfig) -> str:
    """Summarize instead of truncate (placeholder)."""
    # In a real implementation, this would use an LLM to summarize
    # For now, fall back to smart truncation
    return truncate_smart(text, config)


def _find_boundary(text: str, pos: int, forward: bool, config: TruncateConfig) -> int:
    """Find appropriate boundary position."""
    if config.sentence_boundary:
        return find_sentence_boundary(text, pos, forward)
    elif config.line_boundary:
        return find_line_boundary(text, pos, forward)
    elif config.word_boundary:
        return find_word_boundary(text, pos, forward)
    else:
        return min(pos, len(text))


def find_word_boundary(text: str, pos: int, forward: bool) -> int:
    """Find word boundary near position."""
    if pos >= len(text):
        return len(text)
    
    if forward:
        # Search forward for space or newline
        for i in range(pos, min(len(text), pos + 50)):
            if text[i] in ' \n':
                return i
        # Search backward if nothing found
        for i in range(max(0, pos - 50), pos):
            idx = pos - 1 - (i - max(0, pos - 50))
            if idx >= 0 and text[idx] in ' \n':
                return idx + 1
    else:
        # Search backward
        for i in range(min(pos, len(text)) - 1, max(0, pos - 50) - 1, -1):
            if text[i] in ' \n':
                return i + 1
    
    return pos


def find_sentence_boundary(text: str, pos: int, forward: bool) -> int:
    """Find sentence boundary near position."""
    sentence_ends = [". ", "! ", "? ", ".\n", "!\n", "?\n"]
    
    if forward:
        for i in range(pos, min(len(text), pos + 200)):
            for end in sentence_ends:
                if text[i:].startswith(end):
                    return i + len(end)
    else:
        for i in range(min(pos, len(text)) - 1, max(0, pos - 200) - 1, -1):
            for end in sentence_ends:
                if text[i:].startswith(end):
                    return i + len(end)
    
    return find_word_boundary(text, pos, forward)


def find_line_boundary(text: str, pos: int, forward: bool) -> int:
    """Find line boundary near position."""
    if forward:
        idx = text.find('\n', pos)
        if idx != -1:
            return idx + 1
        return pos
    else:
        idx = text.rfind('\n', 0, pos)
        if idx != -1:
            return idx + 1
        return 0


def truncate_file(content: str, file_type: str, max_chars: int) -> str:
    """Truncate file content intelligently."""
    code_types = {"rs", "py", "js", "ts", "go", "c", "cpp", "java", "rb", "php"}
    markdown_types = {"md", "markdown"}
    
    config = TruncateConfig(
        max_chars=max_chars,
        preserve_code=file_type in code_types,
        preserve_markdown=file_type in markdown_types,
        strategy=TruncateStrategy.SMART,
    )
    
    return truncate(content, config).text


def truncate_batch(items: List[str], total_chars: int) -> List[str]:
    """Truncate multiple strings to fit total budget."""
    if not items:
        return []
    
    total_len = sum(len(s) for s in items)
    
    if total_len <= total_chars:
        return list(items)
    
    # Proportional allocation
    ratio = total_chars / total_len
    
    result: List[str] = []
    for item in items:
        target = int(len(item) * ratio)
        config = TruncateConfig(max_chars=target)
        result.append(truncate(item, config).text)
    
    return result


@dataclass
class TruncateBuilder:
    """Builder for truncation configuration."""
    
    _config: TruncateConfig = field(default_factory=TruncateConfig)
    
    def max_chars(self, max_val: int) -> "TruncateBuilder":
        """Set maximum characters."""
        self._config.max_chars = max_val
        return self
    
    def max_tokens(self, max_val: int) -> "TruncateBuilder":
        """Set maximum tokens."""
        self._config.max_tokens = max_val
        return self
    
    def strategy(self, strategy: TruncateStrategy) -> "TruncateBuilder":
        """Set strategy."""
        self._config.strategy = strategy
        return self
    
    def suffix(self, suffix: str) -> "TruncateBuilder":
        """Set suffix."""
        self._config.suffix = suffix
        return self
    
    def prefix(self, prefix: str) -> "TruncateBuilder":
        """Set prefix."""
        self._config.prefix = prefix
        return self
    
    def word_boundary(self, enabled: bool) -> "TruncateBuilder":
        """Enable word boundary alignment."""
        self._config.word_boundary = enabled
        return self
    
    def sentence_boundary(self, enabled: bool) -> "TruncateBuilder":
        """Enable sentence boundary alignment."""
        self._config.sentence_boundary = enabled
        return self
    
    def line_boundary(self, enabled: bool) -> "TruncateBuilder":
        """Enable line boundary alignment."""
        self._config.line_boundary = enabled
        return self
    
    def preserve_code(self, enabled: bool) -> "TruncateBuilder":
        """Preserve code blocks."""
        self._config.preserve_code = enabled
        return self
    
    def preserve_markdown(self, enabled: bool) -> "TruncateBuilder":
        """Preserve markdown structure."""
        self._config.preserve_markdown = enabled
        return self
    
    def build(self) -> TruncateConfig:
        """Build configuration."""
        return self._config
    
    def truncate(self, text: str) -> TruncateResult:
        """Truncate text with built configuration."""
        return truncate(text, self._config)


# =============================================================================
# Legacy API for backward compatibility
# =============================================================================

# Codex uses 4 bytes per token approximation
APPROX_BYTES_PER_TOKEN = 4

# Default token limit for output truncation
DEFAULT_MAX_TOKENS = 2500  # ~10KB of output


@dataclass
class LegacyTruncateResult:
    """Result of truncation operation (legacy)."""
    text: str
    truncated: bool
    original_bytes: int
    original_tokens: int
    tokens_truncated: int
    total_lines: int


def truncate_output(
    output: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> LegacyTruncateResult:
    """
    Truncate output to max tokens, keeping head and tail.
    
    Matches Codex behavior:
    - Uses token-based (not byte-based) limits
    - Truncates middle, keeping equal head/tail
    - Format: "{N} tokens truncated"
    - Prepends "Total output lines: {N}" when truncated
    
    Args:
        output: The output string to truncate
        max_tokens: Maximum tokens to keep (default: 2500 = ~10KB)
        
    Returns:
        LegacyTruncateResult with truncated text and metadata
    """
    if not output:
        return LegacyTruncateResult(
            text=output,
            truncated=False,
            original_bytes=0,
            original_tokens=0,
            tokens_truncated=0,
            total_lines=0,
        )
    
    output_bytes = output.encode("utf-8")
    original_bytes = len(output_bytes)
    original_tokens = original_bytes // APPROX_BYTES_PER_TOKEN
    total_lines = output.count('\n') + (1 if output and not output.endswith('\n') else 0)
    
    if original_tokens <= max_tokens:
        return LegacyTruncateResult(
            text=output,
            truncated=False,
            original_bytes=original_bytes,
            original_tokens=original_tokens,
            tokens_truncated=0,
            total_lines=total_lines,
        )
    
    # Calculate bytes to keep (convert tokens back to bytes)
    max_bytes = max_tokens * APPROX_BYTES_PER_TOKEN
    
    # Split evenly between head and tail
    head_bytes = max_bytes // 2
    tail_bytes = max_bytes - head_bytes
    
    # Get head portion
    head_raw = output_bytes[:head_bytes]
    # Get tail portion  
    tail_raw = output_bytes[-tail_bytes:]
    
    # Decode, handling UTF-8 boundary issues
    head = head_raw.decode("utf-8", errors="ignore")
    tail = tail_raw.decode("utf-8", errors="ignore")
    
    # Calculate truncated tokens
    kept_bytes = len(head.encode()) + len(tail.encode())
    tokens_truncated = (original_bytes - kept_bytes) // APPROX_BYTES_PER_TOKEN
    
    # Build truncation message matching Codex format
    truncation_msg = f"\n...{tokens_truncated} tokens truncated...\n"
    
    # Prepend total lines info
    lines_prefix = f"Total output lines: {total_lines}\n"
    
    truncated_text = f"{lines_prefix}{head}{truncation_msg}{tail}"
    
    return LegacyTruncateResult(
        text=truncated_text,
        truncated=True,
        original_bytes=original_bytes,
        original_tokens=original_tokens,
        tokens_truncated=tokens_truncated,
        total_lines=total_lines,
    )


def limit_output(
    output: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """
    Simple interface: truncate and return just the text.
    
    Args:
        output: The output string to truncate
        max_tokens: Maximum tokens to keep
        
    Returns:
        Truncated string
    """
    return truncate_output(output, max_tokens).text


def limit_lines(
    output: str,
    max_lines: int = 100,
    head_lines: int = 50,
) -> str:
    """
    Limit output to max lines, keeping first and last portions.
    
    Args:
        output: The output string to truncate
        max_lines: Maximum lines to keep
        head_lines: Number of lines to keep from the start
        
    Returns:
        Truncated string with message if truncated
    """
    if not output:
        return output
    
    lines = output.splitlines(keepends=True)
    total_lines = len(lines)
    
    if total_lines <= max_lines:
        return output
    
    tail_lines = max_lines - head_lines
    omitted = total_lines - max_lines
    
    head = "".join(lines[:head_lines])
    tail = "".join(lines[-tail_lines:]) if tail_lines > 0 else ""
    
    # Match Codex message format
    truncation_msg = f"\n...{omitted} lines omitted...\n"
    
    return f"Total output lines: {total_lines}\n{head}{truncation_msg}{tail}"


def smart_truncate(
    output: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_lines: int = 500,
) -> str:
    """
    Smart truncation: applies both token and line limits.
    
    Args:
        output: The output to truncate
        max_tokens: Maximum tokens
        max_lines: Maximum lines
        
    Returns:
        Truncated output
    """
    # First limit by lines (faster check)
    result = limit_lines(output, max_lines)
    
    # Then limit by tokens
    result = limit_output(result, max_tokens)
    
    return result


# Legacy aliases for backward compatibility
def limit_output_bytes(output: str, max_bytes: int = 10000) -> str:
    """Legacy byte-based truncation. Converts to tokens."""
    max_tokens = max_bytes // APPROX_BYTES_PER_TOKEN
    return limit_output(output, max_tokens)


def middle_out_truncate(
    text: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """
    Middle-out truncation like Codex.
    
    Keeps beginning and end, removes middle.
    More useful than head-only because:
    - Beginning often has context/headers
    - End often has results/conclusions
    
    Args:
        text: Text to truncate
        max_tokens: Maximum tokens to keep
        
    Returns:
        Truncated text with marker in middle
    """
    if not text:
        return text
    
    text_bytes = text.encode("utf-8")
    original_bytes = len(text_bytes)
    original_tokens = original_bytes // APPROX_BYTES_PER_TOKEN
    
    if original_tokens <= max_tokens:
        return text
    
    # Calculate bytes to keep
    max_bytes = max_tokens * APPROX_BYTES_PER_TOKEN
    
    # Split 50/50 between head and tail
    head_bytes = max_bytes // 2
    tail_bytes = max_bytes - head_bytes
    
    # Extract portions
    head_raw = text_bytes[:head_bytes]
    tail_raw = text_bytes[-tail_bytes:]
    
    # Decode safely (handle UTF-8 boundary issues)
    head = head_raw.decode("utf-8", errors="ignore")
    tail = tail_raw.decode("utf-8", errors="ignore")
    
    # Calculate removed tokens
    kept_bytes = len(head.encode()) + len(tail.encode())
    removed_tokens = (original_bytes - kept_bytes) // APPROX_BYTES_PER_TOKEN
    
    return f"{head}\n\n...{removed_tokens} tokens truncated...\n\n{tail}"


__all__ = [
    # New API (fabric-core compatible)
    "TruncateStrategy",
    "TruncateConfig",
    "TruncateResult",
    "TruncateBuilder",
    "TokenEstimator",
    "truncate",
    "truncate_end",
    "truncate_start",
    "truncate_middle",
    "truncate_smart",
    "truncate_preserve_code",
    "truncate_preserve_structure",
    "truncate_file",
    "truncate_batch",
    "estimate_tokens",
    "find_word_boundary",
    "find_sentence_boundary",
    "find_line_boundary",
    # Legacy API
    "LegacyTruncateResult",
    "truncate_output",
    "limit_output",
    "limit_lines",
    "smart_truncate",
    "limit_output_bytes",
    "middle_out_truncate",
    "APPROX_BYTES_PER_TOKEN",
    "DEFAULT_MAX_TOKENS",
]

"""Logging utilities for A2A agent communications."""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Optional
from functools import wraps

# ANSI color codes for terminal output
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Agent colors
    ORCHESTRATOR = "\033[95m"  # Magenta
    CONCEPT_GUIDE = "\033[94m"  # Blue
    QUESTION_GEN = "\033[92m"   # Green
    QUALITY_CHECK = "\033[93m"  # Yellow

    # Message types
    SEND = "\033[96m"      # Cyan (outgoing)
    RECEIVE = "\033[97m"   # White (incoming)
    LLM_PROMPT = "\033[33m"  # Orange/Brown
    LLM_RESPONSE = "\033[32m"  # Green
    ERROR = "\033[91m"     # Red

    # Content types
    JSON = "\033[36m"      # Cyan
    TEXT = "\033[37m"      # Light gray


# Configure logging level from environment
LOG_LEVEL = os.environ.get("A2A_LOG_LEVEL", "INFO").upper()
LOG_VERBOSE = os.environ.get("A2A_LOG_VERBOSE", "false").lower() == "true"
LOG_LLM = os.environ.get("A2A_LOG_LLM", "true").lower() == "true"
LOG_MESSAGES = os.environ.get("A2A_LOG_MESSAGES", "true").lower() == "true"

# Create logger
logger = logging.getLogger("a2a")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# Console handler with custom formatting
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def get_agent_color(agent_name: str) -> str:
    """Get color code for an agent."""
    name_lower = agent_name.lower()
    if "orchestrator" in name_lower:
        return Colors.ORCHESTRATOR
    elif "concept" in name_lower:
        return Colors.CONCEPT_GUIDE
    elif "question" in name_lower or "generator" in name_lower:
        return Colors.QUESTION_GEN
    elif "quality" in name_lower or "checker" in name_lower:
        return Colors.QUALITY_CHECK
    return Colors.TEXT


def truncate_text(text: str, max_length: int = 500) -> str:
    """Truncate text for display."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + f"... ({len(text) - max_length} more chars)"


def format_json(data: Any, indent: int = 2, max_length: int = 1000) -> str:
    """Format JSON data for display."""
    try:
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return truncate_text(data, max_length)

        formatted = json.dumps(data, indent=indent, default=str)
        return truncate_text(formatted, max_length)
    except Exception:
        return truncate_text(str(data), max_length)


def log_separator(char: str = "─", length: int = 80):
    """Print a separator line."""
    logger.info(f"{Colors.DIM}{char * length}{Colors.RESET}")


def log_agent_message(
    direction: str,  # "SEND" or "RECEIVE"
    from_agent: str,
    to_agent: str,
    message_type: str,
    content: Any,
    metadata: Optional[dict] = None,
):
    """Log an agent-to-agent message."""
    if not LOG_MESSAGES:
        return

    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    from_color = get_agent_color(from_agent)
    to_color = get_agent_color(to_agent)
    dir_color = Colors.SEND if direction == "SEND" else Colors.RECEIVE
    arrow = "→" if direction == "SEND" else "←"

    # Header
    log_separator()
    logger.info(
        f"{Colors.DIM}[{timestamp}]{Colors.RESET} "
        f"{dir_color}{Colors.BOLD}{direction}{Colors.RESET} "
        f"{from_color}{from_agent}{Colors.RESET} "
        f"{arrow} "
        f"{to_color}{to_agent}{Colors.RESET} "
        f"{Colors.DIM}({message_type}){Colors.RESET}"
    )

    # Content
    if content:
        formatted = format_json(content, max_length=2000 if LOG_VERBOSE else 500)
        logger.info(f"{Colors.JSON}{formatted}{Colors.RESET}")

    # Metadata
    if metadata and LOG_VERBOSE:
        logger.info(f"{Colors.DIM}Metadata: {format_json(metadata, max_length=200)}{Colors.RESET}")


def log_llm_call(
    agent_name: str,
    prompt: str,
    response: Optional[str] = None,
    model: str = "gemini",
    error: Optional[str] = None,
    duration_ms: Optional[float] = None,
):
    """Log an LLM API call."""
    if not LOG_LLM:
        return

    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    agent_color = get_agent_color(agent_name)

    log_separator("═")
    logger.info(
        f"{Colors.DIM}[{timestamp}]{Colors.RESET} "
        f"{Colors.LLM_PROMPT}{Colors.BOLD}LLM CALL{Colors.RESET} "
        f"{agent_color}{agent_name}{Colors.RESET} "
        f"{Colors.DIM}({model}){Colors.RESET}"
    )

    # Prompt
    logger.info(f"\n{Colors.LLM_PROMPT}{Colors.BOLD}PROMPT:{Colors.RESET}")
    prompt_display = truncate_text(prompt, 3000 if LOG_VERBOSE else 800)
    logger.info(f"{Colors.TEXT}{prompt_display}{Colors.RESET}")

    # Response
    if response:
        if duration_ms:
            logger.info(f"\n{Colors.LLM_RESPONSE}{Colors.BOLD}RESPONSE{Colors.RESET} {Colors.DIM}({duration_ms:.0f}ms):{Colors.RESET}")
        else:
            logger.info(f"\n{Colors.LLM_RESPONSE}{Colors.BOLD}RESPONSE:{Colors.RESET}")

        response_display = truncate_text(response, 3000 if LOG_VERBOSE else 800)
        logger.info(f"{Colors.TEXT}{response_display}{Colors.RESET}")

    # Error
    if error:
        logger.info(f"\n{Colors.ERROR}{Colors.BOLD}ERROR:{Colors.RESET}")
        logger.info(f"{Colors.ERROR}{error}{Colors.RESET}")

    log_separator("═")


def log_pipeline_step(
    step_name: str,
    step_number: int,
    total_steps: int,
    details: Optional[str] = None,
):
    """Log a pipeline step."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    logger.info(
        f"{Colors.DIM}[{timestamp}]{Colors.RESET} "
        f"{Colors.BOLD}STEP {step_number}/{total_steps}:{Colors.RESET} "
        f"{Colors.ORCHESTRATOR}{step_name}{Colors.RESET}"
    )

    if details:
        logger.info(f"  {Colors.DIM}{details}{Colors.RESET}")


def log_error(agent_name: str, error: str, context: Optional[str] = None):
    """Log an error."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    agent_color = get_agent_color(agent_name)

    logger.error(
        f"{Colors.DIM}[{timestamp}]{Colors.RESET} "
        f"{Colors.ERROR}{Colors.BOLD}ERROR{Colors.RESET} "
        f"{agent_color}{agent_name}{Colors.RESET}: "
        f"{Colors.ERROR}{error}{Colors.RESET}"
    )

    if context:
        logger.error(f"  {Colors.DIM}Context: {context}{Colors.RESET}")


def log_info(agent_name: str, message: str):
    """Log an info message."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    agent_color = get_agent_color(agent_name)

    logger.info(
        f"{Colors.DIM}[{timestamp}]{Colors.RESET} "
        f"{agent_color}{agent_name}{Colors.RESET}: "
        f"{message}"
    )

from typing import Any


def answer_from_response(response: Any) -> str:
    """Handle known Perplexity response formats without exposing them upstream."""
    if not isinstance(response, dict):
        return ""
    if isinstance(response.get("answer"), str):
        return response["answer"]
    for block in response.get("blocks", []):
        if not isinstance(block, dict) or block.get("intended_usage") != "ask_text":
            continue
        markdown = block.get("markdown_block", {})
        if not isinstance(markdown, dict):
            continue
        chunks = markdown.get("chunks")
        if isinstance(chunks, list):
            return "".join(str(chunk) for chunk in chunks)
        if isinstance(markdown.get("answer"), str):
            return markdown["answer"]
    return ""

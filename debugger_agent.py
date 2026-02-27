"""
Debugger Agent: Uses Claude Opus to diagnose and rewrite failing image generation prompts.

Called when the QA agent returns Decision 3 (escalate) — meaning the image has failed
QA on the 3rd attempt and needs a fundamentally different approach.
"""

import os
import re

import anthropic


DEBUGGER_PROMPT_TEMPLATE = """\
**Role:** You are an Expert Code Debugger Agent.

**Objective:** The primary image generation pipeline is repeatedly failing to meet strict visual requirements. Your job is to analyze the failure, diagnose the root cause in the generation logic, and rewrite the prompt to fix it.

**Inputs You Will Receive For This Run:**
1. The Blog Title: {blog_title}
2. The specific Requirement that failed: {failure_reason}
3. The current Image Generation Prompt: {current_prompt}

**Action Required:**
1. **Analyze:** Briefly explain why the current prompt is failing the visual requirement.
2. **Resolve:** Formulate a technical fix. This may involve adjusting negative prompts, forcing specific camera angles, tweaking crop logic, or modifying prompt parameters.
3. **Execute:** Output the fully revised, ready-to-use prompt to replace the failing prompt in the pipeline.

**Output Format:**
Analysis: [1-2 sentences on why the current prompt is failing]
Fix: [1-2 sentences on the technical change being made]
Revised Prompt:
```
[the complete rewritten prompt here — this will be used directly as the image generation input]
```
"""


def rewrite_prompt(
    blog_title: str,
    failure_reason: str,
    current_prompt: str,
    model: str = "claude-opus-4-5",
) -> str:
    """
    Ask Claude Opus to rewrite a failing image generation prompt.

    Args:
        blog_title: Title of the blog post
        failure_reason: The specific QA requirement that failed (from Sonnet's reasoning)
        current_prompt: The current image generation prompt that has been failing
        model: Anthropic model to use for debugging

    Returns:
        A revised prompt string ready to be passed to generate_image()
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not found in environment variables.\n"
            "Add it to your .env file: ANTHROPIC_API_KEY=your-key-here"
        )

    prompt_text = DEBUGGER_PROMPT_TEMPLATE.format(
        blog_title=blog_title,
        failure_reason=failure_reason,
        current_prompt=current_prompt,
    )

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": prompt_text,
            }
        ],
    )

    response_text = message.content[0].text.strip()
    return _extract_revised_prompt(response_text, current_prompt)


def _extract_revised_prompt(response_text: str, fallback_prompt: str) -> str:
    """
    Extract the revised prompt from Opus's response.

    Looks for content inside a fenced code block after 'Revised Prompt:'.
    Falls back to returning the original prompt if parsing fails.
    """
    # Try to find content inside a fenced code block
    code_block_match = re.search(r"```(?:\w+)?\s*\n(.*?)```", response_text, re.DOTALL)
    if code_block_match:
        return code_block_match.group(1).strip()

    # Fallback: try to grab everything after "Revised Prompt:"
    revised_match = re.search(r"Revised Prompt:\s*\n(.*)", response_text, re.IGNORECASE | re.DOTALL)
    if revised_match:
        return revised_match.group(1).strip()

    # Last resort: return original prompt unchanged
    print("  ⚠ Opus response could not be parsed — using original prompt")
    return fallback_prompt

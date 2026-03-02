"""
QA Agent: Uses Claude Sonnet to evaluate generated images against visual requirements.

Returns a QAResult with:
  - decision: 1 (continue), 2 (regenerate), or 3 (escalate to Opus)
  - reasoning: Sonnet's explanation
  - failure_reason: specific requirement that failed (if any)
"""

import base64
import os
import re
from dataclasses import dataclass

import anthropic


QA_PROMPT_TEMPLATE = """\
**Role:** You are an expert Image Quality Assurance (QA) Agent integrated into an automated blog-to-image pipeline.

**Objective:** Evaluate generated images against strict visual and thematic criteria based on a provided blog title. Determine the next step in the pipeline: continue, regenerate, or escalate for code edits.

**Inputs You Will Receive For This Run:**
1. Blog Title: {blog_title}
2. Generated Image: [attached below]
3. Current Attempt Number: {attempt_number}
4. Previous Image Styles/Concepts: {past_images_log}

**Evaluation Requirements:**
1. Cropped Faces: Human faces must be cropped out of the frame as much as visually possible.
2. Thematic Accuracy: The visual concept must clearly make sense and align with the "Blog Title."
3. Close-up Composition: The image must be framed as a tight, close-up shot.
4. Visual Diversity: The image must not look too similar in style, subject, or layout to the "Previous Image Styles/Concepts."
5. Logo Visibility: The clinic logo must be clearly visible on the therapist's clothing. It must match the exact logo design from the reference images (dark navy scrubs, logo on the upper chest). A missing, blurred, or incorrectly styled logo is a failure.

**Decision Logic:**
Analyze the image strictly against the five requirements above. Provide a brief reasoning, then output EXACTLY ONE of the following numbers based on your conclusion:

* Output "1" (Continue): If the image meets ALL requirements perfectly.
* Output "2" (Regenerate): If the image fails ONE OR MORE requirements AND the "Current Attempt Number" is 1 or 2. Specify exactly which requirement failed so the image generator can adjust on the next try.
* Output "3" (Escalate): If the image fails ONE OR MORE requirements AND the "Current Attempt Number" is 3.

**Output Format:**
Reasoning: [1-2 sentences explaining why the image passes or fails specific criteria]
Decision: [1, 2, or 3]
"""


@dataclass
class QAResult:
    """Result from the QA agent evaluation."""
    decision: int          # 1 = continue, 2 = regenerate, 3 = escalate
    reasoning: str         # Sonnet's explanation
    failure_reason: str    # Which requirement failed (empty string if passed)


def evaluate_image(
    blog_title: str,
    image_path: str,
    attempt_number: int,
    past_images_log: list[str],
    model: str = "claude-sonnet-4-5",
) -> QAResult:
    """
    Evaluate a generated image using Claude Sonnet.

    Args:
        blog_title: Title of the blog post
        image_path: Absolute path to the generated PNG image
        attempt_number: Current attempt number (1, 2, or 3)
        past_images_log: Brief descriptions of previously generated images for this post
        model: Anthropic model to use for QA

    Returns:
        QAResult with decision (1/2/3), reasoning, and failure_reason
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not found in environment variables.\n"
            "Add it to your .env file: ANTHROPIC_API_KEY=your-key-here"
        )

    # Build past images context string
    if past_images_log:
        past_log_str = "; ".join(past_images_log)
    else:
        past_log_str = "None (this is the first attempt)"

    # Encode image as base64
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    # Detect MIME type from extension
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    media_type = mime_map.get(ext, "image/png")

    # Build prompt
    prompt_text = QA_PROMPT_TEMPLATE.format(
        blog_title=blog_title,
        attempt_number=attempt_number,
        past_images_log=past_log_str,
    )

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt_text,
                    },
                ],
            }
        ],
    )

    response_text = message.content[0].text.strip()
    return _parse_qa_response(response_text)


def _parse_qa_response(response_text: str) -> QAResult:
    """Parse Sonnet's response to extract decision and reasoning."""
    reasoning = ""
    failure_reason = ""
    decision = 2  # Default to regenerate if parsing fails

    # Extract Reasoning
    reasoning_match = re.search(r"Reasoning:\s*(.+?)(?=Decision:|$)", response_text, re.IGNORECASE | re.DOTALL)
    if reasoning_match:
        reasoning = reasoning_match.group(1).strip()

    # Extract Decision (look for a standalone 1, 2, or 3)
    decision_match = re.search(r"Decision:\s*([123])", response_text, re.IGNORECASE)
    if decision_match:
        decision = int(decision_match.group(1))

    # If decision is 2 or 3, the failure reason is embedded in the reasoning
    if decision in (2, 3):
        failure_reason = reasoning

    return QAResult(decision=decision, reasoning=reasoning, failure_reason=failure_reason)

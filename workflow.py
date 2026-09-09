import json
import os
import random
import re
import time
from typing import Any, Callable, Dict, Optional

from groq import Groq

from prompts import (
    PLANNER_PROMPT,
    CONTENT_PROMPT,
    ASSESSMENT_PROMPT,
    REVIEW_PROMPT,
    REFINEMENT_PROMPT,
)

MODEL_NAME = "openai/gpt-oss-120b"
MAX_RETRIES = 3
BASE_DELAY = 2.0


class WorkflowError(Exception):
    pass


def get_api_key():
    key = os.getenv("GROQ_API_KEY")

    if key:
        return key

    try:
        import streamlit as st
        key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        key = None

    if not key:
        raise WorkflowError(
            "GROQ_API_KEY is missing. Add it to Streamlit Secrets."
        )

    return key


def get_client():
    return Groq(api_key=get_api_key())


def fill_prompt(template: str, **values: str) -> str:
    # Do not use str.format() because the prompts contain JSON braces.
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


def parse_json(text: str):
    """
    Robust JSON parser.

    GPT-OSS normally returns a JSON object when JSON mode is enabled.
    This parser also handles:
    - Markdown JSON fences
    - extra text around the object
    - a JSON object encoded as a JSON string
    """
    text = (text or "").strip()

    if not text:
        raise ValueError("The model returned an empty response.")

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\s*```$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # First attempt.
    parsed = json.loads(text)

    # Sometimes a model/API layer returns the JSON object as a string.
    if isinstance(parsed, str):
        parsed = json.loads(parsed)

    if isinstance(parsed, dict):
        return parsed

    # Last-resort recovery if extra text surrounds the JSON object.
    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        parsed = json.loads(text[start:end + 1])

        if isinstance(parsed, str):
            parsed = json.loads(parsed)

        if isinstance(parsed, dict):
            return parsed

    raise ValueError(
        f"Expected a JSON object, received {type(parsed).__name__}."
    )


def is_transient_error(exc: Exception) -> bool:
    message = str(exc).lower()

    markers = [
        "429",
        "rate limit",
        "too many requests",
        "500",
        "502",
        "503",
        "504",
        "internal server error",
        "service unavailable",
        "temporarily unavailable",
        "timeout",
        "timed out",
        "connection",
    ]

    return any(marker in message for marker in markers)


def short_error(exc: Exception) -> str:
    """
    Prevent huge API/model responses from being displayed in Streamlit.
    """
    message = str(exc).replace("\n", " ").strip()

    if len(message) > 500:
        message = message[:500] + "..."

    return message


def generate_json(
    client,
    prompt: str,
    stage_name: str,
):
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are one stage in a multi-stage AI "
                            "study-pack workflow. Follow the user's "
                            "instructions exactly. Return one valid "
                            "JSON object only. Do not wrap the JSON "
                            "inside another JSON string. Do not use "
                            "Markdown fences."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                response_format={
                    "type": "json_object"
                },
                reasoning_effort="medium",
                temperature=0.2,
            )

            message = response.choices[0].message

            # Normal response.
            content = message.content

            # GPT-OSS can expose reasoning separately depending on
            # SDK/API configuration. We only parse the final content.
            if not content:
                raise ValueError(
                    f"{stage_name} returned no final content."
                )

            data = parse_json(content)

            if not isinstance(data, dict):
                raise ValueError(
                    f"{stage_name} did not return a JSON object."
                )

            return data

        except Exception as exc:
            last_error = exc

            # JSON parsing/validation problems are not normally fixed
            # by repeatedly sending the exact same request.
            if not is_transient_error(exc):
                break

            if attempt >= MAX_RETRIES:
                break

            delay = (
                BASE_DELAY * (2 ** (attempt - 1))
                + random.uniform(0, 0.75)
            )

            time.sleep(delay)

    raise WorkflowError(
        f"{stage_name} failed with {MODEL_NAME}. "
        f"Please try again. Technical detail: {short_error(last_error)}"
    )


def require(data: Dict[str, Any], keys, stage: str):
    if not isinstance(data, dict):
        raise WorkflowError(
            f"{stage} returned invalid JSON. Expected an object."
        )

    missing = [key for key in keys if key not in data]

    if missing:
        raise WorkflowError(
            f"{stage} returned incomplete JSON. "
            f"Missing: {', '.join(missing)}"
        )


def run_workflow(
    user_input: Dict[str, Any],
    on_stage: Optional[Callable] = None,
):
    client = get_client()

    context = {
        "user_input": user_input,
        "model": MODEL_NAME,
    }

    def update(stage, status, detail=""):
        if on_stage:
            on_stage(stage, status, detail)

    user_json = json.dumps(
        user_input,
        ensure_ascii=False,
        indent=2,
    )

    # 1. Planning
    update(
        "Planning",
        "running",
        f"Creating learning blueprint with {MODEL_NAME}.",
    )

    plan = generate_json(
        client,
        fill_prompt(
            PLANNER_PROMPT,
            user_input=user_json,
        ),
        "Planning",
    )

    require(
        plan,
        [
            "learning_objectives",
            "priority_concepts",
            "study_strategy",
            "assessment_strategy",
        ],
        "Planning",
    )

    context["plan"] = plan

    update(
        "Planning",
        "complete",
        "Learning blueprint created.",
    )

    # 2. Content Generation
    update(
        "Content Generation",
        "running",
        "Generating personalized study material.",
    )

    content = generate_json(
        client,
        fill_prompt(
            CONTENT_PROMPT,
            user_input=user_json,
            plan=json.dumps(
                plan,
                ensure_ascii=False,
                indent=2,
            ),
        ),
        "Content Generation",
    )

    require(
        content,
        [
            "summary",
            "key_concepts",
            "glossary",
            "study_plan",
        ],
        "Content Generation",
    )

    context["content"] = content

    update(
        "Content Generation",
        "complete",
        "Core study material generated.",
    )

    # 3. Assessment
    update(
        "Assessment",
        "running",
        "Creating flashcards and quiz questions.",
    )

    assessment = generate_json(
        client,
        fill_prompt(
            ASSESSMENT_PROMPT,
            user_input=user_json,
            plan=json.dumps(
                plan,
                ensure_ascii=False,
                indent=2,
            ),
            content=json.dumps(
                content,
                ensure_ascii=False,
                indent=2,
            ),
        ),
        "Assessment",
    )

    require(
        assessment,
        [
            "flashcards",
            "quiz",
            "exam_tips",
        ],
        "Assessment",
    )

    context["assessment"] = assessment

    update(
        "Assessment",
        "complete",
        "Assessment material generated.",
    )

    # 4. Review
    update(
        "Review",
        "running",
        "Checking quality, consistency and difficulty.",
    )

    review = generate_json(
        client,
        fill_prompt(
            REVIEW_PROMPT,
            user_input=user_json,
            plan=json.dumps(
                plan,
                ensure_ascii=False,
                indent=2,
            ),
            content=json.dumps(
                content,
                ensure_ascii=False,
                indent=2,
            ),
            assessment=json.dumps(
                assessment,
                ensure_ascii=False,
                indent=2,
            ),
        ),
        "Review",
    )

    require(
        review,
        [
            "status",
            "issues",
            "recommended_changes",
        ],
        "Review",
    )

    context["review"] = review

    update(
        "Review",
        "complete",
        f"Review result: {review.get('status', 'UNKNOWN')}.",
    )

    # 5. Conditional Refinement
    if str(review.get("status", "")).upper() == "PASS":
        final_pack = {
            **content,
            **assessment,
        }

        context["refinement"] = {
            "performed": False,
            "reason": "Review passed.",
        }

        update(
            "Refinement",
            "complete",
            "No refinement was necessary.",
        )

    else:
        update(
            "Refinement",
            "running",
            "Fixing issues identified by the reviewer.",
        )

        final_pack = generate_json(
            client,
            fill_prompt(
                REFINEMENT_PROMPT,
                user_input=user_json,
                plan=json.dumps(
                    plan,
                    ensure_ascii=False,
                    indent=2,
                ),
                content=json.dumps(
                    content,
                    ensure_ascii=False,
                    indent=2,
                ),
                assessment=json.dumps(
                    assessment,
                    ensure_ascii=False,
                    indent=2,
                ),
                review=json.dumps(
                    review,
                    ensure_ascii=False,
                    indent=2,
                ),
            ),
            "Refinement",
        )

        require(
            final_pack,
            [
                "summary",
                "key_concepts",
                "glossary",
                "study_plan",
                "flashcards",
                "quiz",
                "exam_tips",
            ],
            "Refinement",
        )

        context["refinement"] = {
            "performed": True,
            "reason": "Review feedback was applied.",
        }

        update(
            "Refinement",
            "complete",
            "Study pack refined successfully.",
        )

    context["final_pack"] = final_pack

    return context

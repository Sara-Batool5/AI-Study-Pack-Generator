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
            "GROQ_API_KEY is missing. Add it to Streamlit Secrets "
            "or set it as an environment variable."
        )
    return key


def get_client():
    return Groq(api_key=get_api_key())


def fill_prompt(template: str, **values: str) -> str:
    """Replace only named placeholders; JSON braces remain untouched."""
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


def parse_json(text: str):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text, flags=re.I)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def is_transient_error(exc: Exception) -> bool:
    message = str(exc).lower()
    markers = [
        "429", "rate limit", "too many requests",
        "500", "502", "503", "504",
        "internal server error", "service unavailable",
        "temporarily unavailable", "timeout", "timed out", "connection",
    ]
    return any(marker in message for marker in markers)


def generate_json(client, prompt: str, stage_name: str):
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are part of a multi-stage educational AI workflow. "
                            "Follow the requested JSON structure exactly. Return valid JSON only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError(f"{stage_name} returned an empty model response.")
            return parse_json(content)

        except Exception as exc:
            last_error = exc
            if attempt >= MAX_RETRIES or not is_transient_error(exc):
                break
            delay = BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 0.75)
            time.sleep(delay)

    raise WorkflowError(
        f"{stage_name} failed using {MODEL_NAME} after {MAX_RETRIES} attempts: {last_error}"
    )


def require(data: Dict[str, Any], keys, stage: str):
    missing = [key for key in keys if key not in data]
    if missing:
        raise WorkflowError(
            f"{stage} returned incomplete JSON. Missing: {', '.join(missing)}"
        )


def run_workflow(user_input: Dict[str, Any], on_stage: Optional[Callable] = None):
    client = get_client()
    context = {"user_input": user_input, "model": MODEL_NAME}

    def update(stage, status, detail=""):
        if on_stage:
            on_stage(stage, status, detail)

    user_json = json.dumps(user_input, ensure_ascii=False, indent=2)

    update("Planning", "running", f"Creating learning blueprint with {MODEL_NAME}.")
    plan = generate_json(
        client,
        fill_prompt(PLANNER_PROMPT, user_input=user_json),
        "Planning",
    )
    require(plan, ["learning_objectives", "priority_concepts", "study_strategy", "assessment_strategy"], "Planning")
    context["plan"] = plan
    update("Planning", "complete", "Learning blueprint created.")

    plan_json = json.dumps(plan, ensure_ascii=False, indent=2)
    update("Content Generation", "running", "Generating personalized study material.")
    content = generate_json(
        client,
        fill_prompt(CONTENT_PROMPT, user_input=user_json, plan=plan_json),
        "Content Generation",
    )
    require(content, ["summary", "key_concepts", "glossary", "study_plan"], "Content Generation")
    context["content"] = content
    update("Content Generation", "complete", "Core study material generated.")

    content_json = json.dumps(content, ensure_ascii=False, indent=2)
    update("Assessment", "running", "Creating flashcards and quiz questions.")
    assessment = generate_json(
        client,
        fill_prompt(ASSESSMENT_PROMPT, user_input=user_json, plan=plan_json, content=content_json),
        "Assessment",
    )
    require(assessment, ["flashcards", "quiz", "exam_tips"], "Assessment")
    context["assessment"] = assessment
    update("Assessment", "complete", "Assessment material generated.")

    assessment_json = json.dumps(assessment, ensure_ascii=False, indent=2)
    update("Review", "running", "Checking quality, consistency and difficulty.")
    review = generate_json(
        client,
        fill_prompt(
            REVIEW_PROMPT,
            user_input=user_json,
            plan=plan_json,
            content=content_json,
            assessment=assessment_json,
        ),
        "Review",
    )
    require(review, ["status", "issues", "recommended_changes"], "Review")
    context["review"] = review
    update("Review", "complete", f"Review result: {review.get('status', 'UNKNOWN')}.")

    if str(review.get("status", "")).upper() == "PASS":
        final_pack = {**content, **assessment}
        context["refinement"] = {"performed": False, "reason": "Review passed."}
        update("Refinement", "complete", "No refinement was necessary.")
    else:
        update("Refinement", "running", "Fixing issues identified by the reviewer.")
        final_pack = generate_json(
            client,
            fill_prompt(
                REFINEMENT_PROMPT,
                user_input=user_json,
                plan=plan_json,
                content=content_json,
                assessment=assessment_json,
                review=json.dumps(review, ensure_ascii=False, indent=2),
            ),
            "Refinement",
        )
        require(
            final_pack,
            ["summary", "key_concepts", "glossary", "study_plan", "flashcards", "quiz", "exam_tips"],
            "Refinement",
        )
        context["refinement"] = {"performed": True, "reason": "Review feedback was applied."}
        update("Refinement", "complete", "Study pack refined successfully.")

    context["final_pack"] = final_pack
    return context

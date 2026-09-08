import json, os, re, time
from typing import Any, Callable, Dict, Optional
from google import genai
from google.genai import types
from prompts import PLANNER_PROMPT, CONTENT_PROMPT, ASSESSMENT_PROMPT, REVIEW_PROMPT, REFINEMENT_PROMPT

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
MAX_RETRIES = 2

class WorkflowError(Exception):
    pass

def get_client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise WorkflowError("GEMINI_API_KEY is missing. Add it to Streamlit Secrets.")
    return genai.Client(api_key=key)

def parse_json(text):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.I)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        a, b = text.find("{"), text.rfind("}")
        if a >= 0 and b > a:
            return json.loads(text[a:b+1])
        raise

def generate_json(client, prompt):
    last = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    thinking_config=types.ThinkingConfig(thinking_level="medium"),
                ),
            )
            if not response.text:
                raise ValueError("Empty model response.")
            return parse_json(response.text)
        except Exception as exc:
            last = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep(1.5 * (attempt + 1))
    raise WorkflowError(f"AI generation failed after {MAX_RETRIES} attempts: {last}")

def require(data, keys, stage):
    missing = [k for k in keys if k not in data]
    if missing:
        raise WorkflowError(f"{stage} returned incomplete JSON. Missing: {', '.join(missing)}")



def fill_prompt(template: str, **values: str) -> str:
    """Replace only named placeholders; JSON braces in prompts stay untouched."""
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template

def run_workflow(user_input: Dict[str, Any], on_stage: Optional[Callable] = None):
    client = get_client()
    context = {"user_input": user_input}

    def update(stage, status, detail=""):
        if on_stage:
            on_stage(stage, status, detail)

    update("Planning", "running", "Creating a personalized learning blueprint.")
    plan = generate_json(client, fill_prompt(PLANNER_PROMPT, user_input=json.dumps(user_input, ensure_ascii=False, indent=2)))
    require(plan, ["learning_objectives", "priority_concepts", "study_strategy", "assessment_strategy"], "Planning")
    context["plan"] = plan
    update("Planning", "complete", "Learning blueprint created.")

    update("Content Generation", "running", "Generating personalized study material.")
    content = generate_json(client, fill_prompt(CONTENT_PROMPT, user_input=json.dumps(user_input, ensure_ascii=False, indent=2), plan=json.dumps(plan, ensure_ascii=False, indent=2)))
    require(content, ["summary", "key_concepts", "glossary", "study_plan"], "Content Generation")
    context["content"] = content
    update("Content Generation", "complete", "Core study material generated.")

    update("Assessment", "running", "Creating flashcards and quiz questions.")
    assessment = generate_json(client, fill_prompt(ASSESSMENT_PROMPT, user_input=json.dumps(user_input, ensure_ascii=False, indent=2), plan=json.dumps(plan, ensure_ascii=False, indent=2), content=json.dumps(content, ensure_ascii=False, indent=2)))
    require(assessment, ["flashcards", "quiz", "exam_tips"], "Assessment")
    context["assessment"] = assessment
    update("Assessment", "complete", "Assessment material generated.")

    update("Review", "running", "Checking quality, consistency and difficulty.")
    review = generate_json(client, fill_prompt(REVIEW_PROMPT, user_input=json.dumps(user_input, ensure_ascii=False, indent=2), plan=json.dumps(plan, ensure_ascii=False, indent=2), content=json.dumps(content, ensure_ascii=False, indent=2), assessment=json.dumps(assessment, ensure_ascii=False, indent=2)))
    require(review, ["status", "issues", "recommended_changes"], "Review")
    context["review"] = review
    update("Review", "complete", f"Review result: {review.get('status', 'UNKNOWN')}.")

    if str(review.get("status", "")).upper() == "PASS":
        final_pack = {**content, **assessment}
        context["refinement"] = {"performed": False, "reason": "Review passed."}
        update("Refinement", "complete", "No refinement was necessary.")
    else:
        update("Refinement", "running", "Fixing issues identified by the reviewer.")
        final_pack = generate_json(client, fill_prompt(REFINEMENT_PROMPT, user_input=json.dumps(user_input, ensure_ascii=False, indent=2), plan=json.dumps(plan, ensure_ascii=False, indent=2), content=json.dumps(content, ensure_ascii=False, indent=2), assessment=json.dumps(assessment, ensure_ascii=False, indent=2), review=json.dumps(review, ensure_ascii=False, indent=2)))
        require(final_pack, ["summary", "key_concepts", "glossary", "study_plan", "flashcards", "quiz", "exam_tips"], "Refinement")
        context["refinement"] = {"performed": True, "reason": "Review feedback was applied."}
        update("Refinement", "complete", "Study pack refined successfully.")

    context["final_pack"] = final_pack
    return context

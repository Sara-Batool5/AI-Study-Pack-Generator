"""
workflow.py - Orchestration Layer for Multi-Stage AI Pipeline
"""

import json
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential
import prompts

class StudyPackWorkflow:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Google API Key is missing.")
        self.client = genai.Client(api_key=api_key)

    # Automatically retry on temporary 503 errors (wait 2s, 4s, 8s, 10s)
    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=10)
    )
    def _call_llm_with_retry(self, system_prompt: str, user_prompt: str, model_name: str) -> dict:
        response = self.client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)

    def _call_llm(self, system_prompt: str, user_prompt: str) -> dict:
        """Utility method with automatic fallback if primary model is unavailable."""
        # Try primary model first
        try:
            return self._call_llm_with_retry(system_prompt, user_prompt, "gemini-3.6-flash")
        except Exception as e:
            # Fallback model if gemini-3.6-flash continues to throw 503 high-demand errors
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                return self._call_llm_with_retry(system_prompt, user_prompt, "gemini-2.5-flash")
            raise e

    def execute_pipeline(self, topic: str, depth: str, style: str, progress_callback=None):
        """
        Executes the 5-stage agentic workflow:
        Stage 1: Planning
        Stage 2: Content Generation
        Stage 3: Assessment
        Stage 4: Review / QA Audit
        Stage 5: Refinement
        """
        # Stage 1: Planning
        if progress_callback:
            progress_callback(10, "⚡ [Stage 1/5] Architectural Planning & Learning Plan Generation...")
        plan_res = self._call_llm(
            prompts.STAGE_1_SYSTEM,
            prompts.get_stage_1_prompt(topic, depth, style)
        )

        # Stage 2: Content Generation
        if progress_callback:
            progress_callback(30, "⚡ [Stage 2/5] Synthesizing Content & Flashcards...")
        content_res = self._call_llm(
            prompts.STAGE_2_SYSTEM,
            prompts.get_stage_2_prompt(topic, depth, style, json.dumps(plan_res))
        )

        # Stage 3: Assessment
        if progress_callback:
            progress_callback(50, "⚡ [Stage 3/5] Generating Targeted Assessments & Quizzes...")
        assessment_res = self._call_llm(
            prompts.STAGE_3_SYSTEM,
            prompts.get_stage_3_prompt(topic, depth, json.dumps(content_res))
        )

        # Stage 4: Review & Audit
        if progress_callback:
            progress_callback(75, "⚡ [Stage 4/5] Running Quality Control & Peer Review Audit...")
        combined_materials = {
            "plan": plan_res,
            "content": content_res,
            "assessment": assessment_res
        }
        review_res = self._call_llm(
            prompts.STAGE_4_SYSTEM,
            prompts.get_stage_4_prompt(json.dumps(combined_materials))
        )

        # Stage 5: Refinement
        if progress_callback:
            progress_callback(90, "⚡ [Stage 5/5] Refinement & Optimization Stage...")
        draft_pack = {
            "summary": content_res.get("summary"),
            "key_takeaways": content_res.get("key_takeaways"),
            "flashcards": content_res.get("flashcards"),
            "quiz": assessment_res.get("quiz")
        }
        final_pack = self._call_llm(
            prompts.STAGE_5_SYSTEM,
            prompts.get_stage_5_prompt(json.dumps(draft_pack), json.dumps(review_res))
        )

        if progress_callback:
            progress_callback(100, " Workflow Execution Complete!")

        return {
            "plan": plan_res,
            "review": review_res,
            "final_pack": final_pack
        }

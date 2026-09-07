"""
workflow.py - Groq API Orchestration Layer
"""

import json
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential
import prompts

class StudyPackWorkflow:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Groq API Key is missing.")
        self.client = Groq(api_key=api_key)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=8)
    )
    def _call_llm_with_retry(self, system_prompt: str, user_prompt: str, model_name: str) -> dict:
        response = self.client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)

    def _call_llm(self, system_prompt: str, user_prompt: str) -> dict:
        """Utility method using verified active Groq models."""
        primary_model = "llama-3.3-70b-versatile"
        fallback_model = "llama-3.1-8b-instant"

        try:
            return self._call_llm_with_retry(system_prompt, user_prompt, primary_model)
        except Exception as e:
            # Automatic fallback to 8B instant model if primary fails
            try:
                return self._call_llm_with_retry(system_prompt, user_prompt, fallback_model)
            except Exception:
                raise e

    def execute_pipeline(self, topic: str, depth: str, style: str, progress_callback=None):
        """Executes the 5-stage agentic workflow."""
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

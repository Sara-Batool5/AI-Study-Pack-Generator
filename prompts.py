"""
prompts.py - Centralized System and User Prompts for Multi-Stage AI Workflow
"""

# Stage 1: Planning Prompts
STAGE_1_SYSTEM = "You are an expert educational curriculum designer. Output raw JSON only."

def get_stage_1_prompt(topic: str, depth: str, style: str) -> str:
    return f"""
Design a structured, high-yield study plan for:
- Topic: {topic}
- Target Depth: {depth}
- Preferred Style: {style}

Return JSON with:
1. "learning_objectives": List of 3-4 key objectives.
2. "concept_breakdown": List of core subtopics/modules to cover.
3. "recommended_focus": Brief statement on key concepts to prioritize.
"""

# Stage 2: Content Generation Prompts
STAGE_2_SYSTEM = "You are a professional educational author and domain expert. Output raw JSON only."

def get_stage_2_prompt(topic: str, depth: str, style: str, plan_data: str) -> str:
    return f"""
Generate comprehensive study content based on this approved curriculum plan:
{plan_data}

Topic: {topic}
Target Depth: {depth}
Style: {style}

Return JSON with:
1. "summary": A detailed breakdown of the topic mapped to objectives.
2. "key_takeaways": List of 5 high-yield bullet points.
3. "flashcards": List of 5 objects with "question" and "answer" fields.
"""

# Stage 3: Assessment Prompts
STAGE_3_SYSTEM = "You are an expert academic evaluator and assessment creator. Output raw JSON only."

def get_stage_3_prompt(topic: str, depth: str, content_data: str) -> str:
    return f"""
Based on this generated study content:
{content_data}

Create a practice quiz for topic: "{topic}" at depth level: "{depth}".

Return JSON with:
1. "quiz": List of 4 questions containing:
   - "id": integer (1-4)
   - "question": string
   - "options": list of 4 choices
   - "correct_answer": string (exact match to one option)
   - "explanation": string explaining why it is correct
"""

# Stage 4: Review & Audit Prompts
STAGE_4_SYSTEM = "You are a Quality Assurance Auditor for higher-education study materials. Output raw JSON only."

def get_stage_4_prompt(combined_materials: str) -> str:
    return f"""
Audit the following generated study pack:
{combined_materials}

Check for:
- Pedagogical alignment with learning objectives
- Conceptual accuracy and clarity
- Flashcard and quiz difficulty consistency

Return JSON with:
1. "passed_audit": boolean
2. "quality_score": number out of 10
3. "critique": Detailed explanation of any flaws or missing info.
4. "improvement_instructions": Specific directives for refining content.
"""

# Stage 5: Refinement Prompts
STAGE_5_SYSTEM = "You are a master educational editor and instructional designer. Output raw JSON only."

def get_stage_5_prompt(draft_materials: str, review_feedback: str) -> str:
    return f"""
Refine and finalize the study pack based on the Quality Review feedback.

DRAFT MATERIALS:
{draft_materials}

REVIEW FEEDBACK & INSTRUCTIONS:
{review_feedback}

Apply fixes for all issues raised. Return JSON containing the finalized structure:
1. "summary": Refined and enhanced summary.
2. "key_takeaways": Refined key takeaways list.
3. "flashcards": Refined list of flashcard objects ("question", "answer").
4. "quiz": Refined list of quiz objects ("id", "question", "options", "correct_answer", "explanation").
"""

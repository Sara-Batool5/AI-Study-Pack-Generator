import os
import json
import re
import io
import streamlit as st
from google import genai

st.set_page_config(
    page_title="AI Study Pack Generator",
    page_icon="📚",
    layout="wide"
)

MODEL_NAME = "gemini-3.7-flash"

def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets["GEMINI_API_KEY"]
        except Exception:
            api_key = None

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is not configured. Add it to Streamlit Secrets "
            "or set it as an environment variable."
        )
    return genai.Client(api_key=api_key)

def clean_json(text):
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.I)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

def generate_study_pack(topic, level, study_goal, pack_size, question_count):
    client = get_client()

    prompt = f"""
You are an expert educational content designer.

Create a useful, accurate and student-friendly study pack.

Topic: {topic}
Student level: {level}
Study goal: {study_goal}
Pack size: {pack_size}
Number of quiz questions: {question_count}

Return ONLY valid JSON with exactly these top-level keys:
summary, key_concepts, glossary, study_plan, flashcards, quiz, exam_tips

Requirements:
- summary: a clear overview in 2-4 paragraphs.
- key_concepts: 6-10 important concepts, each with a short explanation.
- glossary: 8-12 important terms with simple definitions.
- study_plan: a practical 5-day plan. Each day must contain day, focus, tasks, and estimated_minutes.
- flashcards: 10-15 cards. Each must contain question and answer.
- quiz: exactly {question_count} questions. Each must contain question, options (4 strings),
  correct_answer (the exact option text), and explanation.
- exam_tips: 5-8 practical tips specific to the topic.
- Match the language and difficulty to the student level.
- Do not invent citations or claim facts you are unsure about.
- Make the material educational rather than merely motivational.
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    raw = clean_json(response.text)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # A second pass asks Gemini to repair malformed JSON.
        repair_prompt = f"""
Convert the following study-pack response into valid JSON only.
Keep the content unchanged as much as possible.
Use exactly these keys:
summary, key_concepts, glossary, study_plan, flashcards, quiz, exam_tips.

TEXT:
{response.text}
"""
        repaired = client.models.generate_content(
            model=MODEL_NAME,
            contents=repair_prompt
        )
        return json.loads(clean_json(repaired.text))

def study_pack_markdown(data, topic):
    lines = [f"# AI Study Pack: {topic}", ""]
    lines += ["## Summary", data.get("summary", ""), ""]

    lines += ["## Key Concepts", ""]
    for item in data.get("key_concepts", []):
        if isinstance(item, dict):
            lines.append(f"### {item.get('concept', 'Concept')}")
            lines.append(item.get("explanation", ""))
            lines.append("")
        else:
            lines.append(f"- {item}")

    lines += ["## Glossary", ""]
    for item in data.get("glossary", []):
        if isinstance(item, dict):
            lines.append(f"- **{item.get('term', 'Term')}** — {item.get('definition', '')}")
        else:
            lines.append(f"- {item}")
    lines.append("")

    lines += ["## 5-Day Study Plan", ""]
    for item in data.get("study_plan", []):
        lines.append(
            f"### {item.get('day', 'Day')} — {item.get('focus', '')}"
        )
        lines.append(f"- Tasks: {item.get('tasks', '')}")
        lines.append(f"- Estimated time: {item.get('estimated_minutes', '')} minutes")
        lines.append("")

    lines += ["## Flashcards", ""]
    for i, card in enumerate(data.get("flashcards", []), 1):
        lines.append(f"**{i}. Q:** {card.get('question', '')}")
        lines.append(f"**A:** {card.get('answer', '')}")
        lines.append("")

    lines += ["## Quiz", ""]
    for i, q in enumerate(data.get("quiz", []), 1):
        lines.append(f"### {i}. {q.get('question', '')}")
        for option in q.get("options", []):
            lines.append(f"- {option}")
        lines.append(f"- **Correct answer:** {q.get('correct_answer', '')}")
        lines.append(f"- **Explanation:** {q.get('explanation', '')}")
        lines.append("")

    lines += ["## Exam Tips", ""]
    for tip in data.get("exam_tips", []):
        lines.append(f"- {tip}")

    return "\n".join(lines)

st.title("📚 AI Study Pack Generator")
st.caption("Turn any topic into a structured study pack with summaries, concepts, flashcards, quizzes and a study plan.")

with st.sidebar:
    st.header("Study Settings")
    level = st.selectbox(
        "Student level",
        ["Beginner", "High school", "College / Undergraduate", "Graduate", "Professional"]
    )
    study_goal = st.selectbox(
        "Study goal",
        ["Understand the topic", "Prepare for an exam", "Quick revision", "Learn from scratch"]
    )
    pack_size = st.select_slider(
        "Pack depth",
        options=["Short", "Standard", "Detailed"],
        value="Standard"
    )
    question_count = st.slider("Quiz questions", 5, 15, 10)

topic = st.text_input(
    "What do you want to study?",
    placeholder="e.g., CRISPR-Cas9, Python functions, Photosynthesis, Project Management"
)

generate = st.button("✨ Generate Study Pack", type="primary", use_container_width=True)

if generate:
    if not topic.strip():
        st.warning("Please enter a study topic.")
    else:
        try:
            with st.spinner("Creating your study pack..."):
                data = generate_study_pack(
                    topic.strip(),
                    level,
                    study_goal,
                    pack_size,
                    question_count
                )

            st.session_state["study_pack"] = data
            st.session_state["study_topic"] = topic.strip()
            st.success("Study pack generated successfully!")

        except Exception as e:
            st.error(f"Something went wrong: {e}")
            st.info("Check that your Gemini API key is configured correctly and try again.")

if "study_pack" in st.session_state:
    data = st.session_state["study_pack"]
    current_topic = st.session_state["study_topic"]

    tabs = st.tabs([
        "📖 Summary",
        "🧠 Concepts",
        "📚 Glossary",
        "🗓️ Study Plan",
        "🃏 Flashcards",
        "❓ Quiz",
        "🎯 Exam Tips",
        "⬇️ Export"
    ])

    with tabs[0]:
        st.markdown(data.get("summary", ""))

    with tabs[1]:
        for item in data.get("key_concepts", []):
            st.subheader(item.get("concept", "Concept"))
            st.write(item.get("explanation", ""))

    with tabs[2]:
        for item in data.get("glossary", []):
            st.markdown(f"**{item.get('term', 'Term')}**")
            st.write(item.get("definition", ""))

    with tabs[3]:
        for item in data.get("study_plan", []):
            with st.expander(f"{item.get('day', 'Day')} — {item.get('focus', '')}"):
                st.write(f"**Tasks:** {item.get('tasks', '')}")
                st.write(f"**Estimated time:** {item.get('estimated_minutes', '')} minutes")

    with tabs[4]:
        for i, card in enumerate(data.get("flashcards", []), 1):
            with st.expander(f"Flashcard {i}: {card.get('question', '')}"):
                st.write(card.get("answer", ""))

    with tabs[5]:
        for i, q in enumerate(data.get("quiz", []), 1):
            st.markdown(f"### {i}. {q.get('question', '')}")
            options = q.get("options", [])
            selected = st.radio(
                "Choose an answer:",
                options,
                key=f"quiz_{i}",
                index=None
            )
            if selected:
                if selected == q.get("correct_answer"):
                    st.success("Correct!")
                else:
                    st.error(f"Not quite. Correct answer: {q.get('correct_answer')}")
                st.caption(q.get("explanation", ""))

    with tabs[6]:
        for tip in data.get("exam_tips", []):
            st.markdown(f"- {tip}")

    with tabs[7]:
        md = study_pack_markdown(data, current_topic)
        st.download_button(
            "📄 Download Study Pack (.md)",
            data=md,
            file_name=f"{current_topic.replace(' ', '_')}_study_pack.md",
            mime="text/markdown",
            use_container_width=True
        )
        st.download_button(
            "🧾 Download Study Pack (.json)",
            data=json.dumps(data, indent=2, ensure_ascii=False),
            file_name=f"{current_topic.replace(' ', '_')}_study_pack.json",
            mime="application/json",
            use_container_width=True
        )

st.divider()
st.caption("Built with Python + Gemini API + Streamlit")

"""
app.py - Main Streamlit User Interface & Event Handler
"""

import os
import streamlit as st
from workflow import StudyPackWorkflow

# ------------------------------------------------------------------------------
# 1. Page Configuration
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Multi-Stage AI Study Pack Generator",
    page_icon="🧠",
    layout="wide"
)

# ------------------------------------------------------------------------------
# 2. Sidebar & API Setup
# ------------------------------------------------------------------------------
st.sidebar.title("🛠️ Configuration")

# API Key Handling (Streamlit Secrets or Manual Input)
api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))

if not api_key:
    api_key = st.sidebar.text_input("Enter OpenAI API Key:", type="password")
    if not api_key:
        st.sidebar.warning("⚠️ Please provide an API key to proceed.")

st.sidebar.subheader("Inputs")
topic_in = st.sidebar.text_input("Topic / Subject:", placeholder="e.g., Quantum Computing")
depth_in = st.sidebar.selectbox("Depth Level:", ["Beginner", "Intermediate / Undergraduate", "Advanced / Graduate"])
style_in = st.sidebar.selectbox("Learning Style:", ["Conceptual & Theoretical", "Practical & Code-focused", "Exam / High-Yield Prep"])

run_btn = st.sidebar.button("🚀 Run Workflow Pipeline", type="primary")

# ------------------------------------------------------------------------------
# 3. Session State Initialization
# ------------------------------------------------------------------------------
if "results" not in st.session_state:
    st.session_state.results = None

# ------------------------------------------------------------------------------
# 4. Main UI & Pipeline Execution
# ------------------------------------------------------------------------------
st.title("🧠 Multi-Stage AI Study Pack Generator")
st.caption("Powered by a 5-Stage Orchestrated Agentic Pipeline: Plan ➔ Content ➔ Assessment ➔ Audit ➔ Refine")

if run_btn:
    if not api_key:
        st.error("Please enter a valid OpenAI API Key in the sidebar.")
    elif not topic_in.strip():
        st.warning("Please enter a topic to generate study materials.")
    else:
        st.session_state.results = None
        
        progress_bar = st.progress(0)
        status_text = st.empty()

        def update_progress(percent, message):
            progress_bar.progress(percent)
            status_text.text(message)

        try:
            workflow = StudyPackWorkflow(api_key=api_key)
            pipeline_output = workflow.execute_pipeline(
                topic=topic_in,
                depth=depth_in,
                style=style_in,
                progress_callback=update_progress
            )
            st.session_state.results = pipeline_output
            status_text.success(" Multi-Stage Workflow Completed Successfully!")

        except Exception as e:
            status_text.empty()
            progress_bar.empty()
            st.error(f"❌ Pipeline Execution Error: {str(e)}")

# ------------------------------------------------------------------------------
# 5. Output Display
# ------------------------------------------------------------------------------
if st.session_state.results:
    res = st.session_state.results
    plan = res.get("plan", {})
    review = res.get("review", {})
    final = res.get("final_pack", {})

    st.divider()

    # QA Audit Metadata Block
    with st.expander("📊 View Stage 4 Quality Control & Audit Report", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.metric("QA Score", f"{review.get('quality_score', 'N/A')} / 10")
            st.write(f"**Passed Audit:** `{review.get('passed_audit')}`")
        with col2:
            st.write("**Auditor Critique:**")
            st.info(review.get("critique", "No critique provided."))
        
        st.write("**Improvement Directives Applied in Stage 5 Refinement:**")
        st.json(review.get("improvement_instructions", {}))

    # Main Output Tabs
    tab_plan, tab_summary, tab_takeaways, tab_cards, tab_quiz = st.tabs([
        "📋 Curriculum Plan", 
        "📖 Summary", 
        "💡 Key Takeaways", 
        "🎴 Flashcards", 
        "❓ Practice Quiz"
    ])

    with tab_plan:
        st.subheader("Curriculum & Roadmap")
        st.markdown("**Learning Objectives:**")
        for obj in plan.get("learning_objectives", []):
            st.markdown(f"- {obj}")
        
        st.markdown("**Core Subtopics Breakdown:**")
        for subtopic in plan.get("concept_breakdown", []):
            st.markdown(f"- {subtopic}")
        
        st.info(f"**Recommended Focus:** {plan.get('recommended_focus')}")

    with tab_summary:
        st.subheader("Detailed Summary")
        st.write(final.get("summary", "No summary available."))

    with tab_takeaways:
        st.subheader("High-Yield Takeaways")
        for point in final.get("key_takeaways", []):
            st.markdown(f"- {point}")

    with tab_cards:
        st.subheader("Flashcards")
        cards = final.get("flashcards", [])
        for i, card in enumerate(cards, 1):
            with st.expander(f"Card {i}: {card.get('question')}"):
                st.success(f"**Answer:** {card.get('answer')}")

    with tab_quiz:
        st.subheader("Self-Assessment Quiz")
        for q in final.get("quiz", []):
            st.markdown(f"**Q{q.get('id')}: {q.get('question')}**")
            user_choice = st.radio(
                "Options:",
                q.get("options", []),
                key=f"q_{q.get('id')}"
            )
            if st.button(f"Check Answer for Q{q.get('id')}", key=f"btn_{q.get('id')}"):
                if user_choice == q.get("correct_answer"):
                    st.success("✨ Correct!")
                else:
                    st.error(f"❌ Incorrect. Correct Answer: {q.get('correct_answer')}")
                st.info(f"**Explanation:** {q.get('explanation')}")
            st.divider()

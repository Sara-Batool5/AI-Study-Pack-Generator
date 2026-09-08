import json
import streamlit as st
from workflow import WorkflowError, run_workflow

st.set_page_config(page_title="AI Study Pack Generator", page_icon="📚", layout="wide")
st.title("📚 AI Study Pack Generator")
st.caption("Planning → Content → Assessment → Review → Refinement")
STAGES = ["Planning", "Content Generation", "Assessment", "Review", "Refinement"]
if "stage_state" not in st.session_state:
    st.session_state.stage_state = {s: "⚪ Waiting" for s in STAGES}

def update_stage(stage, status, detail=""):
    icons = {"running":"🔵 Running", "complete":"✅ Complete", "error":"❌ Error"}
    st.session_state.stage_state[stage] = f"{icons.get(status, status)} — {detail}"

with st.sidebar:
    st.header("🎓 Student Profile")
    topic = st.text_input("Topic", placeholder="e.g. CRISPR-Cas9")
    level = st.selectbox("Student level", ["Beginner", "High school", "College / Undergraduate", "Graduate", "Professional"])
    goal = st.selectbox("Study goal", ["Learn from scratch", "Understand the topic", "Prepare for an exam", "Quick revision"])
    prior = st.selectbox("Prior knowledge", ["None", "Basic", "Intermediate", "Advanced"])
    minutes = st.slider("Study time per day", 15, 180, 45, 15)
    style = st.selectbox("Preferred learning style", ["Balanced", "Concept explanations", "Examples and applications", "Flashcards and active recall", "Practice questions"])
    depth = st.selectbox("Pack depth", ["Short", "Standard", "Detailed"], index=1)
    quiz_count = st.slider("Quiz questions", 5, 15, 10)
    generate = st.button("✨ Generate Study Pack", type="primary", use_container_width=True)

st.subheader("🤖 Workflow Status")
cols = st.columns(5)
for col, stage in zip(cols, STAGES):
    with col:
        st.metric(stage, st.session_state.stage_state[stage].split(" — ")[0])

if generate:
    if not topic.strip():
        st.warning("Please enter a topic.")
        st.stop()
    st.session_state.stage_state = {s: "⚪ Waiting" for s in STAGES}
    payload = {"topic": topic.strip(), "student_level": level, "study_goal": goal, "prior_knowledge": prior, "available_study_minutes_per_day": minutes, "preferred_learning_style": style, "pack_depth": depth, "quiz_question_count": quiz_count}
    progress, status = st.progress(0), st.empty()
    def callback(stage, state, detail=""):
        update_stage(stage, state, detail)
        done = sum("Complete" in x for x in st.session_state.stage_state.values())
        progress.progress(done / len(STAGES))
        status.info(f"{stage}: {detail}")
    try:
        with st.spinner("Running the five-stage AI workflow..."):
            st.session_state.result = run_workflow(payload, callback)
        progress.progress(1.0)
        status.success("Study pack completed.")
    except WorkflowError as exc:
        status.error(str(exc))
        st.error("The workflow stopped safely. Check your API key/model access and try again.")
    except Exception as exc:
        status.error("Unexpected error.")
        st.exception(exc)

if "result" in st.session_state:
    result = st.session_state.result
    pack, plan, review = result["final_pack"], result["plan"], result["review"]
    tabs = st.tabs(["📖 Overview","🧠 Concepts","📚 Glossary","🗓️ Study Plan","🃏 Flashcards","❓ Quiz","🔎 AI Review","⬇️ Export"])
    with tabs[0]:
        st.subheader("Learning Objectives")
        for x in plan.get("learning_objectives", []): st.markdown(f"- {x}")
        st.subheader("Summary")
        st.write(pack.get("summary", ""))
    with tabs[1]:
        for x in pack.get("key_concepts", []):
            st.markdown(f"### {x.get('concept','Concept')}")
            st.write(x.get("explanation", ""))
            if x.get("example"): st.info(f"Example: {x['example']}")
    with tabs[2]:
        for x in pack.get("glossary", []):
            with st.expander(x.get("term", "Term")): st.write(x.get("definition", ""))
    with tabs[3]:
        for x in pack.get("study_plan", []):
            with st.expander(f"{x.get('day','Day')} — {x.get('focus','')}"):
                for task in x.get("tasks", []): st.markdown(f"- {task}")
                st.caption(f"Estimated time: {x.get('estimated_minutes','')} minutes")
    with tabs[4]:
        for i, x in enumerate(pack.get("flashcards", []), 1):
            with st.expander(f"{i}. {x.get('question','')}"):
                st.write(x.get("answer", ""))
                st.caption(x.get("difficulty", ""))
    with tabs[5]:
        for i, q in enumerate(pack.get("quiz", []), 1):
            st.markdown(f"### {i}. {q.get('question','')}")
            selected = st.radio("Select:", q.get("options", []), key=f"q_{i}", index=None)
            if selected:
                if selected == q.get("correct_answer"): st.success("Correct!")
                else: st.error(f"Incorrect. Correct answer: {q.get('correct_answer','')}")
                st.caption(q.get("explanation", ""))
    with tabs[6]:
        if review.get("status") == "PASS": st.success(f"Review passed — {review.get('score',0)}/100")
        else: st.warning(f"Refinement triggered — {review.get('score',0)}/100")
        for issue in review.get("issues", []):
            st.markdown(f"**{issue.get('section','Section')} — {issue.get('severity','Medium')}**")
            st.write(issue.get("problem", ""))
            if issue.get("suggested_fix"): st.caption(f"Suggested fix: {issue['suggested_fix']}")
    with tabs[7]:
        st.download_button("🧾 Download complete workflow JSON", json.dumps(result, indent=2, ensure_ascii=False), "ai_study_pack_workflow.json", "application/json", use_container_width=True)
        st.download_button("📄 Download final study pack JSON", json.dumps(pack, indent=2, ensure_ascii=False), "study_pack.json", "application/json", use_container_width=True)

st.divider()
st.caption("Built with Python • Gemini • Multi-stage AI workflow • Streamlit")

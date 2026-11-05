import streamlit as st
import json
import time
from groq import Groq

st.set_page_config(
    page_title="AI Mock Interview Coach",
    page_icon="💼",
    layout="wide"
)

MODEL_NAME = "llama-3.3-70b-versatile"

def clean_json_string(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

# --- Key Resolution ---
saved_key = st.secrets.get("GROQ_API_KEY", "").strip()

with st.sidebar:
    st.title("⚙️ Interview Configuration")
    
    if saved_key.startswith("gsk_"):
        api_key = saved_key
        st.success("✅ Groq API Key loaded")
    else:
        api_key = st.text_input("Enter Groq API Key (starts with gsk_):", value=saved_key, type="password")

    job_role = st.selectbox(
        "Target Role:",
        [
            "Cybersecurity Analyst / SOC Analyst",
            "Junior Software Engineer (Python/Full-Stack)",
            "Data Analyst / BI Specialist",
            "Network & Systems Administrator",
            "DevOps / Cloud Engineer"
        ]
    )

    experience_level = st.selectbox(
        "Experience Level:",
        ["Entry Level / Fresh Graduate", "Associate / Junior (1-2 yrs)", "Mid-Level (3-5 yrs)"]
    )

    interview_style = st.selectbox(
        "Interview Style:",
        ["Balanced (Technical + Behavioral)", "Deep Technical & Scenario-Based", "HR & Culture Fit"]
    )

    total_questions = st.slider("Total Number of Questions:", min_value=3, max_value=8, value=5)

    st.markdown("---")
    if st.button("🔄 Reset / Start New Interview", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# --- Session State Initialization ---
if "interview_started" not in st.session_state:
    st.session_state.interview_started = False
if "questions" not in st.session_state:
    st.session_state.questions = []
if "current_q_index" not in st.session_state:
    st.session_state.current_q_index = 0
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "feedback" not in st.session_state:
    st.session_state.feedback = None

st.title("🎯 AI Technical & Behavioral Mock Interviewer")
st.caption("Realistic interview practice powered by Groq LLaMA 3.3.")

is_valid_key = bool(api_key and api_key.startswith("gsk_"))

if not is_valid_key:
    st.warning("⚠️ **Groq API Key Required**")
    st.info("Please provide a valid key starting with `gsk_` via Streamlit Secrets (`GROQ_API_KEY`) or the sidebar.")
    st.stop()

client = Groq(api_key=api_key)

# --- Screen 1: Pre-Interview Setup ---
if not st.session_state.interview_started:
    st.subheader("Candidate Profile & Resume Context")
    candidate_notes = st.text_area(
        "Paste your key skills, notable projects, or resume summary (Optional):",
        placeholder="E.g., Proficient in Python, Linux, Active Directory labs, network security fundamentals...",
        height=180
    )

    if st.button("🚀 Begin Interview", type="primary"):
        with st.spinner("Drafting role-specific interview questions..."):
            prompt = f"""
You are a senior hiring manager and technical interviewer conducting an interview for:
- Role: {job_role}
- Seniority: {experience_level}
- Interview Style: {interview_style}
- Candidate Background Context: {candidate_notes if candidate_notes.strip() else 'Standard graduate applicant'}

Generate exactly {total_questions} interview questions tailored to this role.
Return STRICTLY valid JSON with no markdown wrapping:
{{
  "questions": [
    {{
      "id": 1,
      "category": "string (e.g. Technical / Scenario / Behavioral)",
      "question": "string",
      "what_evaluators_look_for": "string"
    }}
  ]
}}
"""
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": "You are a professional hiring manager. Output strictly valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3
                )
                raw = clean_json_string(response.choices[0].message.content)
                data = json.loads(raw)
                st.session_state.questions = data.get("questions", [])
                st.session_state.interview_started = True
                st.rerun()
            except Exception as e:
                st.error(f"Failed to generate questions: {e}")

# --- Screen 2: Active Interview ---
elif st.session_state.interview_started and st.session_state.feedback is None:
    total_q = len(st.session_state.questions)
    curr_idx = st.session_state.current_q_index
    curr_q = st.session_state.questions[curr_idx]

    progress = (curr_idx) / total_q
    st.progress(progress, text=f"Question {curr_idx + 1} of {total_q}")

    st.markdown(f"### Question {curr_idx + 1} ({curr_q.get('category', 'General')})")
    st.info(f"🎙️ **{curr_q.get('question')}**")

    existing_ans = st.session_state.user_answers.get(str(curr_q["id"]), "")
    answer_text = st.text_area(
        "Your Response:",
        value=existing_ans,
        placeholder="Formulate your response clearly (use STAR method for behavioral questions)...",
        height=220,
        key=f"ans_input_{curr_q['id']}"
    )

    c1, c2, c3 = st.columns([1, 1, 2])

    with c1:
        if curr_idx > 0 and st.button("⬅️ Previous Question"):
            st.session_state.user_answers[str(curr_q["id"])] = answer_text
            st.session_state.current_q_index -= 1
            st.rerun()

    with c2:
        if curr_idx < total_q - 1:
            if st.button("Next Question ➡️", type="primary"):
                if not answer_text.strip():
                    st.warning("Please type a response before proceeding.")
                else:
                    st.session_state.user_answers[str(curr_q["id"])] = answer_text
                    st.session_state.current_q_index += 1
                    st.rerun()
        else:
            if st.button("🏁 Submit Interview", type="primary"):
                if not answer_text.strip():
                    st.warning("Please provide an answer before final submission.")
                else:
                    st.session_state.user_answers[str(curr_q["id"])] = answer_text
                    
                    with st.spinner("Analyzing performance and compiling evaluation report..."):
                        eval_prompt = f"""
You are an expert hiring committee lead evaluating a candidate's mock interview performance.
- Position: {job_role} ({experience_level})
- Questions and Candidate Answers:
{json.dumps([{'question': q['question'], 'category': q['category'], 'answer': st.session_state.user_answers.get(str(q['id']), 'No answer provided')} for q in st.session_state.questions])}

Provide a comprehensive, constructive assessment.
Return STRICTLY valid JSON with no markdown wrapping:
{{
  "overall_score": 0,
  "hiring_verdict": "string (e.g. Strong Hire / Hire / Leaning No / Needs Preparation)",
  "executive_summary": "string",
  "strengths": ["string", "string"],
  "areas_for_improvement": ["string", "string"],
  "question_breakdown": [
    {{
      "question": "string",
      "score": 0,
      "candidate_response": "string",
      "feedback": "string",
      "suggested_ideal_answer": "string"
    }}
  ]
}}
"""
                        try:
                            eval_res = client.chat.completions.create(
                                model=MODEL_NAME,
                                messages=[
                                    {"role": "system", "content": "You are an executive interviewer. Output strictly valid JSON."},
                                    {"role": "user", "content": eval_prompt}
                                ],
                                response_format={"type": "json_object"},
                                temperature=0.2
                            )
                            clean_eval = clean_json_string(eval_res.choices[0].message.content)
                            st.session_state.feedback = json.loads(clean_eval)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Evaluation error: {e}")

# --- Screen 3: Final Performance Report ---
elif st.session_state.feedback is not None:
    res = st.session_state.feedback
    st.balloons()
    st.success("🎉 Interview Complete! Here is your performance debrief:")

    score = res.get("overall_score", 0)
    verdict = res.get("hiring_verdict", "N/A")

    col1, col2 = st.columns(2)
    col1.metric("Overall Score", f"{score} / 100")
    col2.metric("Hiring Committee Verdict", verdict)

    st.info(f"**Executive Summary:** {res.get('executive_summary', '')}")

    s_col, w_col = st.columns(2)
    with s_col:
        st.markdown("#### ✅ Demonstrated Strengths")
        for s in res.get("strengths", []):
            st.markdown(f"- {s}")

    with w_col:
        st.markdown("#### 🎯 Priority Areas for Improvement")
        for a in res.get("areas_for_improvement", []):
            st.markdown(f"- {a}")

    st.markdown("---")
    st.subheader("📋 Question-by-Question Analysis")
    for q_data in res.get("question_breakdown", []):
        with st.expander(f"Q: {q_data.get('question')} — Score: {q_data.get('score', 0)}/10"):
            st.write(f"**Your Answer:** {q_data.get('candidate_response')}")
            st.markdown(f"**Feedback:** {q_data.get('feedback')}")
            st.markdown(f"**💡 Ideal Answer Outline:**\n{q_data.get('suggested_ideal_answer')}")

    if st.button("⬅️ Practice Another Session"):
        st.session_state.clear()
        st.rerun()

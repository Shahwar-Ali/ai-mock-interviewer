import streamlit as st
import json
import time
from google import genai
from google.genai import types
from google.genai.errors import ServerError, APIError

# --- Page Setup ---
st.set_page_config(page_title="AI Mock Interviewer", page_icon="🎯", layout="wide")
st.title("🎯 AI Mock Interview Coach")

# --- Model & Robust API Call Function ---
MODEL_NAME = "gemini-3.5-flash-lite"

def safe_generate_content(client, model, contents, config, retries=3):
    """Wrapper that retries on transient Google ServerError/APIError."""
    for attempt in range(retries):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
        except (ServerError, APIError) as e:
            if attempt == retries - 1:
                raise e
            time.sleep(3)  # Wait 3 seconds before retrying

# --- API Key Detection ---
api_key = None
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]

# --- Sidebar Configuration ---
with st.sidebar:
    st.header("⚙️ Interview Settings")
    if not api_key:
        api_key = st.text_input("Enter Gemini API Key:", type="password")
        if api_key:
            st.success("API Key provided!")
        else:
            st.warning("Please provide an API Key to continue.")
    else:
        st.success("API Key loaded from Secrets!")

    persona = st.selectbox(
        "Interviewer Persona",
        ["Tough Technical Lead", "Supportive Mentor", "Strict HR / Behavioral Recruiter"]
    )
    total_questions = st.slider("Total Questions", min_value=1, max_value=6, value=3)

    if st.button("🔄 Reset Interview", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# --- Initialize Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "question_count" not in st.session_state:
    st.session_state.question_count = 0
if "interview_started" not in st.session_state:
    st.session_state.interview_started = False
if "interview_completed" not in st.session_state:
    st.session_state.interview_completed = False
if "evaluation" not in st.session_state:
    st.session_state.evaluation = None

# --- Interview Flow Functions ---
def start_interview(client, job_desc, background):
    prompt = f"""
You are conducting a professional mock interview.
Persona: {persona}
Target Role / Job Description: {job_desc}
Candidate Background: {background}

Instructions:
1. Greet the candidate in character briefly.
2. Ask ONLY Question 1. Do not ask multiple questions at once.
3. Stay strictly in character.
"""
    response = safe_generate_content(
        client=client,
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.7)
    )
    return response.text

def get_next_question(client, job_desc, transcript, current_q, total_q):
    prompt = f"""
You are conducting a mock interview.
Persona: {persona}
Job Description: {job_desc}
Current Question Count: {current_q} of {total_q}

Transcript so far:
{transcript}

Instructions:
1. Briefly evaluate the candidate's last answer in character (1-2 sentences acknowledging strengths or probing gaps).
2. Ask Question {current_q + 1}. Focus on a different critical requirement from the job description.
3. Ask ONLY ONE question. Do not conclude the interview yet.
"""
    response = safe_generate_content(
        client=client,
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.7)
    )
    return response.text

def run_evaluation(client, job_desc, transcript):
    prompt = f"""
You are an expert technical hiring manager evaluating a completed candidate interview transcript.
Job Description: {job_desc}

Transcript:
{transcript}

Analyze the candidate's performance across all turns and return your analysis strictly as a valid JSON object matching this schema:
{{
  "overall_score": 85,
  "verdict": "Strong Hire",
  "technical_depth_score": 85,
  "communication_score": 80,
  "strengths": ["string", "string"],
  "improvements": ["string", "string"],
  "model_answers": [
    {{
      "question": "string",
      "critique": "string",
      "suggested_response": "string"
    }}
  ]
}}

Do NOT wrap the JSON in Markdown code fences. Output valid raw JSON only.
"""
    response = safe_generate_content(
        client=client,
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json"
        )
    )
    try:
        clean_text = response.text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        return json.loads(clean_text.strip())
    except Exception:
        return {"raw_evaluation": response.text}

# --- Main App Interface ---
if not st.session_state.interview_started:
    st.subheader("📋 Interview Setup")
    col1, col2 = st.columns(2)
    with col1:
        job_desc = st.text_area(
            "Target Job Description:",
            placeholder="Paste the job description or role requirements here...",
            height=180
        )
    with col2:
        candidate_bg = st.text_area(
            "Your Experience / Background (Optional):",
            placeholder="Highlight your current skills, projects, or areas of focus...",
            height=180
        )

    if st.button("🚀 Start Interview", type="primary", use_container_width=True):
        if not api_key:
            st.error("Please provide a Gemini API Key in the sidebar or via Secrets.")
        elif not job_desc.strip():
            st.error("Please enter a Target Job Description.")
        else:
            with st.spinner("Preparing your interview session..."):
                client = genai.Client(api_key=api_key)
                st.session_state.job_desc = job_desc
                st.session_state.candidate_bg = candidate_bg
                first_q = start_interview(client, job_desc, candidate_bg)
                st.session_state.messages.append({"role": "assistant", "content": first_q})
                st.session_state.question_count = 1
                st.session_state.interview_started = True
                st.rerun()

else:
    # Display Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Completed Evaluation View
    if st.session_state.interview_completed:
        st.divider()
        st.success("🎉 Interview Completed! Review your evaluation scorecard below:")
        eval_data = st.session_state.evaluation

        if eval_data and "overall_score" in eval_data:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Overall Score", f"{eval_data.get('overall_score', 'N/A')}/100")
            m2.metric("Verdict", eval_data.get('verdict', 'N/A'))
            m3.metric("Technical Depth", f"{eval_data.get('technical_depth_score', 'N/A')}/100")
            m4.metric("Communication", f"{eval_data.get('communication_score', 'N/A')}/100")

            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("✅ Key Strengths")
                for s in eval_data.get("strengths", []):
                    st.write(f"• {s}")
            with col_b:
                st.subheader("⚠️ Areas for Improvement")
                for imp in eval_data.get("improvements", []):
                    st.write(f"• {imp}")

            st.subheader("💡 Model Answer Coaching")
            for item in eval_data.get("model_answers", []):
                with st.expander(f"Question: {item.get('question', 'Review')}"):
                    st.markdown(f"**Critique:** {item.get('critique', '')}")
                    st.markdown(f"**Suggested Response:**\n{item.get('suggested_response', '')}")
        elif eval_data and "raw_evaluation" in eval_data:
            st.markdown(eval_data["raw_evaluation"])

    # Active Turn Input
    elif not st.session_state.interview_completed:
        user_input = st.chat_input("Type your response to the interviewer...")
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            client = genai.Client(api_key=api_key)
            transcript = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages])

            if st.session_state.question_count < total_questions:
                with st.spinner("Interviewer is evaluating and formulating the next question..."):
                    next_q = get_next_question(
                        client,
                        st.session_state.job_desc,
                        transcript,
                        st.session_state.question_count,
                        total_questions
                    )
                    st.session_state.messages.append({"role": "assistant", "content": next_q})
                    st.session_state.question_count += 1
                    st.rerun()
            else:
                with st.spinner("Final question answered! Generating your evaluation scorecard..."):
                    eval_result = run_evaluation(client, st.session_state.job_desc, transcript)
                    st.session_state.evaluation = eval_result
                    st.session_state.interview_completed = True
                    st.rerun()

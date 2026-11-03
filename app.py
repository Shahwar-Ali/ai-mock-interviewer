import streamlit as st
import json
from google import genai
from google.genai import types

st.set_page_config(
    page_title="AI Mock Interview Coach",
    page_icon="🎙️",
    layout="wide"
)

# Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "interview_active" not in st.session_state:
    st.session_state.interview_active = False
if "current_question_count" not in st.session_state:
    st.session_state.current_question_count = 0
if "scorecard_data" not in st.session_state:
    st.session_state.scorecard_data = None
if "job_description" not in st.session_state:
    st.session_state.job_description = ""
if "persona" not in st.session_state:
    st.session_state.persona = ""
if "max_questions" not in st.session_state:
    st.session_state.max_questions = 4

api_key = st.secrets.get("GEMINI_API_KEY", "")

def get_gemini_client(key):
    return genai.Client(api_key=key)

def generate_first_question(client, jd, candidate_bg, persona):
    prompt = f"""
You are an expert interviewer adopting the following persona: {persona}.
Target Job Description:
\"\"\"
{jd}
\"\"\"

Candidate Background / Resume Summary (optional):
\"\"\"
{candidate_bg}
\"\"\"

Instructions:
1. Greet the candidate briefly in character (1-2 sentences).
2. Ask your FIRST interview question based on the role requirements or their background.
3. Keep it conversational, focused, and realistic. Do not ask multiple questions at once.
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.7)
    )
    return response.text.strip()

def generate_next_turn(client, conversation_history, jd, persona, current_count, max_count):
    dialogue = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in conversation_history])
    
    prompt = f"""
You are conducting an interview as a {persona}.
Target Job Description:
\"\"\"
{jd}
\"\"\"

Conversation So Far:
{dialogue}

Current Question Number: {current_count} of {max_count}.

Instructions:
1. Provide a brief, natural reaction to the candidate's last answer (1 sentence).
2. If this was NOT the final question (current < {max_count}), ask your next targeted question (technical, behavioral, or situational).
3. If this WAS the final question (current >= {max_count}), thank the candidate warmly, close the interview, and state that feedback is being compiled.
Keep the response concise and natural.
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.6)
    )
    return response.text.strip()

def evaluate_interview(client, conversation_history, jd):
    dialogue = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in conversation_history])
    
    prompt = f"""
You are a senior hiring manager and executive talent evaluator.
Review this full mock interview transcript for the target role:

TARGET JOB DESCRIPTION:
\"\"\"
{jd}
\"\"\"

TRANSCRIPT:
\"\"\"
{dialogue}
\"\"\"

Generate an evaluation report strictly in valid JSON format matching this schema:
{{
  "overall_score": <int 0-100>,
  "verdict": "<Strong Hire | Lean Hire | Re-interview | Pass>",
  "summary": "<1-2 sentence overview of candidate performance>",
  "category_scores": {{
    "technical_accuracy": <int 0-100>,
    "communication_clarity": <int 0-100>,
    "star_method_depth": <int 0-100>
  }},
  "strengths": [
    "<Highlight 1>",
    "<Highlight 2>"
  ],
  "areas_for_improvement": [
    "<Critique 1 with actionable fix>",
    "<Critique 2 with actionable fix>"
  ],
  "model_answer_coaching": "<Pick one question where candidate gave a mediocre or brief answer, and show an ideal sample response using STAR framework>"
}}

Output ONLY the JSON object. Do not wrap in markdown tags or backticks.
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2
        )
    )
    return json.loads(response.text)

# Sidebar UI
with st.sidebar:
    st.title("⚙️ Interview Setup")
    
    if not api_key:
        api_key = st.text_input("Gemini API Key", type="password", help="Enter your Google AI Studio API key")
    
    st.markdown("---")
    persona_choice = st.selectbox(
        "Interviewer Persona",
        [
            "Tough Technical Lead (Drills into system architecture, trade-offs & edge cases)",
            "Friendly HR Talent Partner (Focuses on behavioral, team fit, and STAR stories)",
            "Executive Director (High-level business impact, prioritization, and leadership)"
        ]
    )
    
    num_questions = st.slider("Total Interview Questions", min_value=3, max_value=6, value=4)
    
    if st.button("🔄 Reset Interview", use_container_width=True):
        st.session_state.messages = []
        st.session_state.interview_active = False
        st.session_state.current_question_count = 0
        st.session_state.scorecard_data = None
        st.rerun()

st.title("🎙️ AI Mock Interview Coach")
st.write("Practice real-time technical and behavioral interviews with tailored feedback and scoring.")

# Setup Screen
if not st.session_state.interview_active and st.session_state.scorecard_data is None:
    col1, col2 = st.columns(2)
    with col1:
        jd_input = st.text_area(
            "Target Job Description *",
            height=200,
            placeholder="Paste the job description or role requirements here..."
        )
    with col2:
        resume_input = st.text_area(
            "Your Background / Key Experience (Optional)",
            height=200,
            placeholder="Paste your resume summary or technical highlights..."
        )
    
    if st.button("🚀 Start Interview", type="primary", use_container_width=True):
        if not api_key:
            st.error("Please provide a Gemini API Key in the sidebar or in secrets.toml.")
        elif not jd_input.strip():
            st.error("Please enter a Target Job Description to begin.")
        else:
            client = get_gemini_client(api_key)
            with st.spinner("Preparing interview session..."):
                st.session_state.job_description = jd_input
                st.session_state.persona = persona_choice
                st.session_state.max_questions = num_questions
                st.session_state.current_question_count = 1
                
                first_q = generate_first_question(client, jd_input, resume_input, persona_choice)
                st.session_state.messages.append({"role": "assistant", "content": first_q})
                st.session_state.interview_active = True
                st.rerun()

# Active Chat Screen
if st.session_state.interview_active:
    st.progress(
        st.session_state.current_question_count / st.session_state.max_questions,
        text=f"Question {st.session_state.current_question_count} of {st.session_state.max_questions}"
    )
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            
    user_input = st.chat_input("Type your answer here...")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        client = get_gemini_client(api_key)
        with st.spinner("Analyzing answer and preparing next question..."):
            if st.session_state.current_question_count < st.session_state.max_questions:
                st.session_state.current_question_count += 1
                next_msg = generate_next_turn(
                    client,
                    st.session_state.messages,
                    st.session_state.job_description,
                    st.session_state.persona,
                    st.session_state.current_question_count,
                    st.session_state.max_questions
                )
                st.session_state.messages.append({"role": "assistant", "content": next_msg})
                st.rerun()
            else:
                st.session_state.interview_active = False
                scorecard = evaluate_interview(
                    client,
                    st.session_state.messages,
                    st.session_state.job_description
                )
                st.session_state.scorecard_data = scorecard
                st.rerun()

# Feedback Scorecard Screen
if st.session_state.scorecard_data is not None:
    st.success("🎉 Interview Complete! Here is your performance evaluation.")
    card = st.session_state.scorecard_data
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("Overall Score", f"{card.get('overall_score', 0)} / 100")
        st.subheader(f"Verdict: {card.get('verdict', 'N/A')}")
    with col2:
        st.write("**Executive Summary:**")
        st.info(card.get("summary", "No summary generated."))
        
    st.markdown("### 📊 Category Scores")
    cat_scores = card.get("category_scores", {})
    c1, c2, c3 = st.columns(3)
    c1.metric("Technical Depth", f"{cat_scores.get('technical_accuracy', 0)}%")
    c2.metric("Communication Clarity", f"{cat_scores.get('communication_clarity', 0)}%")
    c3.metric("STAR Method Structure", f"{cat_scores.get('star_method_depth', 0)}%")
    
    st.markdown("---")
    col_str, col_imp = st.columns(2)
    with col_str:
        st.markdown("### ✅ Strengths")
        for s in card.get("strengths", []):
            st.markdown(f"- {s}")
            
    with col_imp:
        st.markdown("### 🎯 Areas for Improvement")
        for a in card.get("areas_for_improvement", []):
            st.markdown(f"- {a}")
            
    st.markdown("### 💡 Recommended STAR Response")
    st.write(card.get("model_answer_coaching", "No coaching breakdown provided."))
    
    report_text = f"""# Mock Interview Evaluation Report
Overall Score: {card.get('overall_score')}/100
Verdict: {card.get('verdict')}

Summary:
{card.get('summary')}

Category Breakdown:
- Technical Accuracy: {cat_scores.get('technical_accuracy')}%
- Communication Clarity: {cat_scores.get('communication_clarity')}%
- STAR Method Depth: {cat_scores.get('star_method_depth')}%

Strengths:
{chr(10).join(['- ' + s for s in card.get('strengths', [])])}

Areas for Improvement:
{chr(10).join(['- ' + a for a in card.get('areas_for_improvement', [])])}

Model Answer Coaching:
{card.get('model_answer_coaching')}
"""
    st.download_button(
        label="📥 Download Full Scorecard (.md)",
        data=report_text,
        file_name="interview_scorecard.md",
        mime="text/markdown",
        use_container_width=True
    )

import streamlit as st
import json
import time
from pypdf import PdfReader
from groq import Groq

st.set_page_config(
    page_title="Pak Exam Prep - Matric & Inter (Groq)",
    page_icon="📖",
    layout="wide"
)

# High-performing model available on Groq
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

def safe_groq_generate(client, prompt: str, system_message: str = "You are an examiner. Always return valid JSON."):
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.2
    )
    return response.choices[0].message.content

def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    extracted = []
    for page_idx, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            extracted.append(f"--- Page {page_idx + 1} ---\n{text}")
    return "\n".join(extracted)

# --- Retrieve Groq Key from Secrets or Sidebar ---
saved_key = st.secrets.get("GROQ_API_KEY", "").strip()

with st.sidebar:
    st.title("⚡ Groq Exam Prep Settings")
    
    if saved_key.startswith("gsk_"):
        api_key = saved_key
        st.success("✅ Groq API Key loaded")
    else:
        api_key = st.text_input("Enter Groq API Key (starts with gsk_):", value=saved_key, type="password")

    academic_level = st.selectbox(
        "Academic Level:",
        ["Matric (9th & 10th Class)", "Intermediate (11th & 12th / FSc / ICS / ICom)"]
    )
    
    board_system = st.selectbox(
        "Board Pattern:",
        ["Punjab Boards (BISE Lahore, Gujranwala, Rawalpindi, etc.)", 
         "Federal Board (FBISE - SLO / Conceptual)", 
         "Sindh Boards (BIEK, BSEK)", 
         "KPK / Balochistan Boards"]
    )
    
    explanation_lang = st.radio(
        "Explanation Language:",
        ["English", "Urdu (اردو)", "Roman Urdu (Hamaray alfaaz)"]
    )
    
    st.markdown("---")
    if st.button("🔄 Reset / Clear Session", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# --- Initialize Session State ---
if "chapter_text" not in st.session_state:
    st.session_state.chapter_text = ""
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "evaluation_result" not in st.session_state:
    st.session_state.evaluation_result = None

st.title("📚 Matric & Inter Textbook Exam Prep Coach")
st.caption("Powered by Groq Llama-3.3 — Fast textbook question generation and board grading.")

is_valid_key = api_key and api_key.startswith("gsk_")

if not is_valid_key:
    st.warning("⚠️ **Valid Groq API Key Required**")
    st.info("Enter your Groq key starting with `gsk_` in the sidebar or save it under `GROQ_API_KEY` in Streamlit Secrets.")

# --- 1. Chapter Input ---
if not st.session_state.chapter_text:
    st.subheader("1️⃣ Provide Your Textbook Chapter")
    upload_tab, paste_tab = st.tabs(["📄 Upload Chapter (PDF)", "📝 Paste Notes"])
    
    with upload_tab:
        uploaded_pdf = st.file_uploader("Upload Chapter PDF", type=["pdf"])
        if uploaded_pdf and st.button("Process PDF Chapter", type="primary"):
            with st.spinner("Reading textbook pages..."):
                extracted = extract_text_from_pdf(uploaded_pdf)
                if not extracted.strip():
                    st.error("No readable text found in PDF.")
                else:
                    st.session_state.chapter_text = extracted[:15000]
                    st.success("Text extracted successfully!")
                    st.rerun()
                    
    with paste_tab:
        pasted_text = st.text_area("Paste chapter text or topic notes:", height=250)
        if pasted_text and st.button("Use Pasted Text", type="primary"):
            st.session_state.chapter_text = pasted_text.strip()
            st.rerun()

# --- 2. Exam Generation ---
if st.session_state.chapter_text and st.session_state.quiz_data is None:
    st.info("✅ Chapter content loaded.")
    c1, c2, c3 = st.columns(3)
    with c1:
        num_mcqs = st.slider("MCQs", 2, 6, 3)
    with c2:
        num_short = st.slider("Short Questions", 1, 4, 2)
    with c3:
        num_long = st.slider("Long Questions", 0, 2, 1)

    if st.button("🎯 Generate Practice Exam", type="primary", disabled=not is_valid_key):
        client = Groq(api_key=api_key)
        with st.spinner("Generating exam with Groq... (~2-4 seconds)"):
            prompt = f"""
You are a board examiner for Pakistani {board_system} for {academic_level}.
Generate practice questions derived STRICTLY from this textbook excerpt:
\"\"\"
{st.session_state.chapter_text}
\"\"\"

Requirements:
- Exactly {num_mcqs} MCQs (4 options: A, B, C, D)
- Exactly {num_short} Short Answer Questions
- Exactly {num_long} Long / Essay Questions

Respond ONLY with valid JSON using this exact schema:
{{
  "mcqs": [
    {{
      "id": 1,
      "question": "string",
      "options": ["A) option 1", "B) option 2", "C) option 3", "D) option 4"],
      "correct_option": "A",
      "textbook_ref": "string"
    }}
  ],
  "short_questions": [
    {{
      "id": 1,
      "question": "string",
      "ideal_key_points": ["point 1", "point 2"]
    }}
  ],
  "long_questions": [
    {{
      "id": 1,
      "question": "string",
      "rubric": "string"
    }}
  ]
}}
"""
            try:
                raw_json = safe_groq_generate(client, prompt)
                clean_res = clean_json_string(raw_json)
                st.session_state.quiz_data = json.loads(clean_res)
                st.rerun()
            except Exception as e:
                st.error(f"Failed to generate exam: {e}")

# --- 3. Answering Interface ---
if st.session_state.quiz_data and st.session_state.evaluation_result is None:
    quiz = st.session_state.quiz_data
    st.subheader("📝 Answer Your Exam Paper")
    user_answers = {"mcqs": {}, "short": {}, "long": {}}
    
    if quiz.get("mcqs"):
        st.markdown("### Part 1: Multiple Choice Questions")
        for mcq in quiz["mcqs"]:
            user_answers["mcqs"][str(mcq["id"])] = st.radio(
                f"**Q{mcq['id']}:** {mcq['question']}",
                mcq["options"],
                index=None,
                key=f"mcq_{mcq['id']}"
            )
        st.divider()

    if quiz.get("short_questions"):
        st.markdown("### Part 2: Short Answer Questions")
        for sq in quiz["short_questions"]:
            user_answers["short"][str(sq["id"])] = st.text_area(
                f"**Q{sq['id']}:** {sq['question']}",
                key=f"sq_{sq['id']}"
            )
        st.divider()

    if quiz.get("long_questions"):
        st.markdown("### Part 3: Long / Detailed Questions")
        for lq in quiz["long_questions"]:
            user_answers["long"][str(lq["id"])] = st.text_area(
                f"**Q{lq['id']}:** {lq['question']}",
                height=150,
                key=f"lq_{lq['id']}"
            )

    if st.button("📤 Submit for Grading", type="primary", disabled=not is_valid_key):
        client = Groq(api_key=api_key)
        with st.spinner("Grading answers against textbook content..."):
            eval_prompt = f"""
You are an examiner for Pakistani {board_system} for {academic_level}.
Grade these student answers STRICTLY against the textbook text below.

TEXTBOOK CONTENT:
{st.session_state.chapter_text}

EXAM QUESTIONS:
{json.dumps(quiz)}

STUDENT SUBMITTED ANSWERS:
{json.dumps(user_answers)}

Language for explanations: {explanation_lang}
(If "Urdu (اردو)", provide explanations in Urdu script. If "Roman Urdu", use Roman Urdu. If "English", use formal English.)

Return strictly valid JSON:
{{
  "total_marks_obtained": 0,
  "total_maximum_marks": 0,
  "percentage": 0,
  "general_verdict": "string",
  "mcq_evaluations": [
    {{
      "id": 1,
      "is_correct": true,
      "student_choice": "string",
      "correct_choice": "string",
      "explanation": "string"
    }}
  ],
  "subjective_evaluations": [
    {{
      "question": "string",
      "marks_awarded": 0,
      "max_marks": 0,
      "feedback": "string",
      "textbook_reference": "string",
      "model_answer": "string"
    }}
  ]
}}
"""
            try:
                eval_json = safe_groq_generate(client, eval_prompt)
                clean_eval = clean_json_string(eval_json)
                st.session_state.evaluation_result = json.loads(clean_eval)
                st.rerun()
            except Exception as e:
                st.error(f"Evaluation error: {e}")

# --- 4. Results ---
if st.session_state.evaluation_result is not None:
    res = st.session_state.evaluation_result
    st.success("🏁 Paper Graded!")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Marks Obtained", f"{res.get('total_marks_obtained', 0)} / {res.get('total_maximum_marks', 0)}")
    m2.metric("Percentage", f"{res.get('percentage', 0)}%")
    m3.metric("Feedback Language", explanation_lang)
    
    st.info(f"**Examiner Remarks:** {res.get('general_verdict', '')}")
    
    if res.get("mcq_evaluations"):
        st.markdown("### 🔘 MCQ Breakdown")
        for item in res["mcq_evaluations"]:
            mark = "✅ Correct" if item.get("is_correct") else "❌ Incorrect"
            with st.expander(f"MCQ #{item.get('id')} — {mark}"):
                st.write(f"**Your Choice:** {item.get('student_choice', 'Unanswered')}")
                st.write(f"**Correct Choice:** {item.get('correct_choice', '')}")
                st.markdown(f"**Explanation:** {item.get('explanation', '')}")
                
    if res.get("subjective_evaluations"):
        st.markdown("### 📝 Subjective Question Feedback")
        for subj in res["subjective_evaluations"]:
            with st.expander(f"Question: {subj.get('question')} ({subj.get('marks_awarded')}/{subj.get('max_marks')} Marks)"):
                st.markdown(f"**Feedback:** {subj.get('feedback')}")
                st.info(f"**📖 Reference:** {subj.get('textbook_reference')}")
                st.markdown(f"**🌟 Model Answer:**\n{subj.get('model_answer')}")

    if st.button("⬅️ Practice Another Chapter"):
        st.session_state.clear()
        st.rerun()

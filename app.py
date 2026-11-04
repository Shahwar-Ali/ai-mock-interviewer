import streamlit as st
import json
import time
from pypdf import PdfReader
from google import genai
from google.genai import types
from google.genai.errors import ServerError, APIError

st.set_page_config(
    page_title="Pak Exam Prep - Matric & Inter",
    page_icon="📖",
    layout="wide"
)

MODEL_NAME = "gemini-3.5-flash-lite"

def clean_json_string(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

def safe_generate_content(client, model, contents, config, retries=3):
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
            time.sleep(3)

def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    extracted = []
    for page_idx, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            extracted.append(f"--- Page {page_idx + 1} ---\n{text}")
    return "\n".join(extracted)

# --- Safe API Key Resolution ---
raw_key = st.secrets.get("GEMINI_API_KEY", "").strip()

with st.sidebar:
    st.title("🇵🇰 Exam Preferences")
    
    # Check if existing key is invalid OAuth token
    if raw_key.startswith("AQ."):
        st.error("⚠️ The key in Streamlit Secrets starts with 'AQ.' which is a temporary login token, not an API key.")
        api_key = st.text_input("Enter valid Gemini API Key (starts with AIzaSy):", type="password")
    elif raw_key.startswith("AIzaSy"):
        api_key = raw_key
        st.success("✅ Valid API Key loaded from Secrets")
    else:
        api_key = st.text_input("Enter Gemini API Key (starts with AIzaSy):", value=raw_key, type="password")

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
st.caption("Upload a chapter PDF or paste notes to generate board-pattern questions and receive automated grading.")

# Check for valid API key before proceeding
is_valid_key = api_key and api_key.startswith("AIzaSy")

if not is_valid_key:
    st.warning("⚠️ **Valid API Key Required to Generate Questions**")
    st.info(
        """
        Your API key must start with **`AIzaSy`**.
        
        If you see **`AQ.`**, you copied the web login code instead of the key.
        1. Open [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials)
        2. Click **+ CREATE CREDENTIALS** ➔ **API key**
        3. Copy the string starting with `AIzaSy` and paste it into the sidebar.
        """
    )

# --- 1. Chapter Input ---
if not st.session_state.chapter_text:
    st.subheader("1️⃣ Provide Your Textbook Chapter")
    upload_tab, paste_tab = st.tabs(["📄 Upload Textbook Chapter (PDF)", "📝 Paste Text / Notes"])
    
    with upload_tab:
        uploaded_pdf = st.file_uploader("Upload Chapter PDF", type=["pdf"])
        if uploaded_pdf and st.button("Process PDF Chapter", type="primary"):
            with st.spinner("Extracting text from textbook pages..."):
                extracted = extract_text_from_pdf(uploaded_pdf)
                if not extracted.strip():
                    st.error("No readable text found. Ensure the PDF is not an image scan.")
                else:
                    st.session_state.chapter_text = extracted[:20000]
                    st.success("Chapter text extracted successfully!")
                    st.rerun()
                    
    with paste_tab:
        pasted_text = st.text_area("Paste chapter text or topic notes directly:", height=250)
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
        client = genai.Client(api_key=api_key)
        with st.spinner("Drafting questions according to board pattern..."):
            prompt = f"""
You are a board examiner for Pakistani {board_system} for {academic_level}.
Generate practice questions derived STRICTLY from this textbook excerpt:
\"\"\"
{st.session_state.chapter_text}
\"\"\"

Produce:
- Exactly {num_mcqs} MCQs (4 options: A, B, C, D)
- Exactly {num_short} Short Answer Questions
- Exactly {num_long} Long / Essay Questions

Return strictly valid JSON:
{{
  "mcqs": [
    {{
      "id": 1,
      "question": "string",
      "options": ["A) string", "B) string", "C) string", "D) string"],
      "correct_option": "A",
      "textbook_ref": "string"
    }}
  ],
  "short_questions": [
    {{
      "id": 1,
      "question": "string",
      "ideal_key_points": ["string"]
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
                response = safe_generate_content(
                    client=client,
                    model=MODEL_NAME,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        response_mime_type="application/json"
                    )
                )
                clean_res = clean_json_string(response.text)
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
        client = genai.Client(api_key=api_key)
        with st.spinner("Grading answers against textbook content..."):
            eval_prompt = f"""
You are an examiner for Pakistani {board_system} for {academic_level}.
Grade these answers STRICTLY against the textbook text below.

TEXTBOOK CONTENT:
{st.session_state.chapter_text}

EXAM PAPER:
{json.dumps(quiz)}

STUDENT ANSWERS:
{json.dumps(user_answers)}

Language for explanations: {explanation_lang}
(If "Urdu (اردو)", use proper Urdu script. If "Roman Urdu", write in conversational Roman Urdu. If "English", use clear academic English.)

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
                eval_res = safe_generate_content(
                    client=client,
                    model=MODEL_NAME,
                    contents=eval_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json"
                    )
                )
                clean_eval = clean_json_string(eval_res.text)
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

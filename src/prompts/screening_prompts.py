"""
src/prompts/screening_prompts.py
Prompts for answering application form questions and numerical screening fields.
"""

def build_screening_prompt(question_text: str, candidate_context: str) -> str:
    return f"""You are an applicant filling out an online job application form.
Screening Question: "{question_text}"

Candidate Profile:
\"\"\"{candidate_context[:1600]}\"\"\"

TASK:
Provide a concise, direct, professional answer (1-2 sentences maximum).
- If the question asks for numerical values (e.g., years of experience, salary expectations), return just the number or a brief realistic phrase.
- If it is a Yes/No question, start with Yes or No followed by one brief sentence.
- If it asks for sponsorship or work authorization, state that you are authorized to work.
Answer:"""

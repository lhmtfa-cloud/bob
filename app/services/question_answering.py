async def ask_questions(doc_id):
    questions = [
        "What is the document about?",
        "Who is the author?",
        "List all key topics."
    ]
    return {q: f"Mock answer for '{q}' on doc {doc_id}" for q in questions}
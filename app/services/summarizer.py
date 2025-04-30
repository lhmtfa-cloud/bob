SYSTEM_PROMPT = """
Use the extracted answers to produce structured output:
- Title
- Author
- Key Topics
- Summary
"""

async def generate_summary(extracted_data):
    return {
        "Title": "Sample Document",
        "Author": extracted_data.get("Who is the author?"),
        "Key Topics": extracted_data.get("List all key topics."),
        "Summary": extracted_data.get("What is the document about?")
    }
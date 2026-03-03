"""Centralized prompt templates for all AI operations."""

SYSTEM_PROMPT = "You are a helpful AI reading assistant. Help the user understand and analyze documents."

NOTE_ASSIST_SYSTEM_PROMPT = (
    "You are a note-taking assistant helping users improve and manage their PDF reading notes. "
    "You can read existing notes using available tools to provide better context. "
    "Help users write clearer, more organized, and insightful notes."
)

DOCUMENT_SYSTEM_PROMPT = (
    "You are a document analysis assistant. You can search the document for relevant content "
    "using available tools. Help users understand, analyze, and extract insights from documents."
)

AI_ACTIONS: dict[str, str] = {
    "explain": "Explain the following text in detail:\n\n{text}",
    "summarize": "Summarize the following text concisely:\n\n{text}",
    "translate": "Translate the following text to Chinese:\n\n{text}",
    "define": "Define or explain the key terms in:\n\n{text}",
    "ask": "Answer the following about this text:\n\n{text}",
}

QUICK_ACTIONS: dict[str, str] = {
    "full_summary": "Provide a comprehensive summary of this document.",
    "key_points": "Extract the key points and main arguments from this document.",
    "questions": "Generate thought-provoking questions based on this document.",
}

NOTE_ASSIST_ACTIONS: dict[str, str] = {
    "improve": (
        "Improve and polish the following note. Keep it concise and clear:\n\n"
        "Note: {note}\n\nContext (quoted from document): {quote}"
    ),
    "expand": (
        "Expand on the following note with more detail and insight:\n\n"
        "Note: {note}\n\nContext: {quote}"
    ),
    "translate": "Translate the following note to Chinese:\n\nNote: {note}",
    "summarize": (
        "Summarize the following note more concisely:\n\n"
        "Note: {note}\n\nContext: {quote}"
    ),
}

import ollama
import sys
from typing import Any, Dict
from pathlib import Path
import json
import re
from jinja2 import Template
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings


# Mapping of front-end model names to backend model identifiers (fill values later)
# Example keys should match options in the front-end <select> (e.g. 'Poro-2', 'deepseek-r1')
MODELS: Dict[str, str] = {
    'Poro-2': 'hf.co/tensorblock/LumiOpen_Llama-Poro-2-8B-Instruct-GGUF',
    'deepseek-r1': 'deepseek-r1',
}

# Pedagogical prompt for the assistant
pedagogical_prompt = """Käyttäen mahdollista RAG kontekstia alla sekä omia tietojasi, 
ja vastaa näiden pohjalta käyttäjän kysymykseen."""

# Vectorstore globals (injected at FastAPI startup)
_retriever = None
_emb = None


def set_vectorstore(retriever, emb=None):
    """Inject a retriever (and optionally embeddings instance) created at server startup.

    Call this from your FastAPI startup event so the heavy initialization isn't run on every
    request or at module import time.
    """
    global _retriever, _emb
    _retriever = retriever
    _emb = emb


def get_retriever():
    return _retriever



def _load_beginning_preprompt() -> str:
    "Load the Jinja2-ready session beginning prompt from the prompts folder."
    
    prompt_path = Path(__file__).resolve().parents[2] / "prompts" / "session_beginning_prompt.md"
    return prompt_path.read_text(encoding="utf-8")
    


beginning_preprompt = _load_beginning_preprompt()



def fetchDocuments(user_query: str) -> str:
    retriever = get_retriever()
    if retriever is None:
        raise RuntimeError("Vector retriever not initialized. Ensure FastAPI startup completed.")
    docs = retriever.get_relevant_documents(user_query)
    context = "RAG konteksti: " + "\n\n---\n\n".join(
        (
            f"[LÄHDE: {d.metadata.get('source','tuntematon')}"
            + (f", sivu {d.metadata.get('page')}" if d.metadata.get('page') is not None else "")
            + f"]\n{d.page_content[:800]}"
        )
        for d in docs
    )
    return "CONTEXT (faktoihin nojaamiseen, ei käyttäjälle näytettäväksi):\n" + context


def parse_router_plan(text: str) -> dict:
    # remove fenced code blocks if present
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()

    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass

    m = re.search(r"\{.*\}", t, flags=re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return {"route": "suora", "RAG": "no", "reason": "fallback: invalid json"}


def generate_response(payload: Dict[str, Any]) -> str:
    """Generate a response using the payload sent from the frontend.

    Payload (expected):
      {
        'messages': [ {'role': 'user'|'assistant', 'content': '...'}, ... ],
        'token': '...',  # currently unused / mock
        'tutor_tools': [...],
        'topic': '...',
        'model': 'deepseek-r1'
      }

    Returns: assistant reply string or an error description.
    """
    if not isinstance(payload, dict):
        return "Error: payload must be a dict"

    messages = payload.get("messages")
    if not messages or not isinstance(messages, list):
        return "Error: invalid or missing messages list in payload"

    front_model = payload.get("model") or ""
    model_name = MODELS.get(front_model, front_model) or "deepseek-r1"

    # Render the beginning preprompt with Jinja2 using provided topic (if any)
    topic = payload.get("topic") or ""
    try:
        rendered_beginning = Template(beginning_preprompt).render(TOPIC=topic)
    except Exception:
        rendered_beginning = beginning_preprompt

    # Decide if we need RAG via a simple router - keep this lightweight here
    # If the payload explicitly asked for tutor_tools or RAG handling, we can attach context later
    rag_context = ""
    # If frontend requested tools that imply RAG, include context
    tutor_tools = payload.get("tutor_tools") or []
    if "RAG" in (tutor_tools or []) or payload.get("use_rag"):
        # use the last user message as query
        last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        if last_user:
            rag_context = fetchDocuments(last_user.get("content", ""))

    # Build system prompt(s)
    system_prompt_parts = [rendered_beginning]
    if rag_context:
        system_prompt_parts.append(pedagogical_prompt + "\n\n" + rag_context)
    else:
        system_prompt_parts.append(pedagogical_prompt)

    system_prompt = "\n\n".join(system_prompt_parts)

    # Prepare messages for the model: system prompt first
    model_messages = [{"role": "system", "content": system_prompt}] + messages

    # Try to pull the model (best-effort)
    try:
        ollama.pull(model_name)
    except Exception as e:
        print(f"Warning: failed to pull model {model_name}: {e}", file=sys.stderr)

    try:
        response = ollama.chat(model=model_name, messages=model_messages)
    except Exception as e:
        return f"Error calling model: {e}"

    # Try several ways to extract text
    try:
        if hasattr(response, "message") and hasattr(response.message, "content"):
            return response.message.content
        # dict-like
        if isinstance(response, dict):
            return response.get("message", {}).get("content", str(response))
        return str(response)
    except Exception:
        return "Error: unable to parse model response"


if __name__ == "__main__":
    # Small interactive demo when running this module directly.
    print("assistant.py demo. Type a message (Ctrl-C to quit).")
    model = list(MODELS.values())[0]
    try:
        while True:
            user = input("You: ")
            payload = {"messages": [{"role": "user", "content": user}], "model": model}
            out = generate_response(payload)
            print("Viola:", out)
    except KeyboardInterrupt:
        print("\nExiting demo")






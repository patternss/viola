import ollama
import sys
from typing import Any, Dict
from pathlib import Path
import json
import re
from jinja2 import Template


# Mapping of front-end model names to backend model identifiers (fill values later)
# Example keys should match options in the front-end <select> (e.g. 'Poro-2', 'deepseek-r1')
MODELS: Dict[str, str] = {
    'Poro-2': 'hf.co/tensorblock/LumiOpen_Llama-Poro-2-8B-Instruct-GGUF',
    'Ahma-3': 'hf.co/QuantFactory/Ahma-3B-GGUF:Q8_0', #'hf.co/QuantFactory/Ahma-3B-GGUF:Q4_K_M',
}



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



def _load_beginning_preprompt(topic: str = "") -> str:
    """Load and render the session beginning prompt with the given topic."""
    prompt_path = Path(__file__).resolve().parents[2] / "prompts" / "session_beginning_prompt.md"
    template_content = prompt_path.read_text(encoding="utf-8")
    try:
        return Template(template_content).render(TOPIC=topic)
    except Exception:
        return template_content


def _load_system_prompt() -> str:
    """Load the system prompt from the prompts folder."""
    system_prompt_path = Path(__file__).resolve().parents[2] / "prompts" / "system_prompt.md"
    return system_prompt_path.read_text(encoding="utf-8")


def _load_pedagogical_prompt() -> str:
    """Load the pedagogical prompt from the prompts folder."""
    pedagogical_prompt_path = Path(__file__).resolve().parents[2] / "prompts" / "pedagogical_prompt.md"
    return pedagogical_prompt_path.read_text(encoding="utf-8")


def _load_startup_text() -> str:
    """Load the chat startup text from the prompts folder."""
    startup_text_path = Path(__file__).resolve().parents[2] / "prompts" / "chat_startup_text.md"
    return startup_text_path.read_text(encoding="utf-8")


def _load_session_beginning_prompt() -> str:
    """Load the raw session beginning prompt template from the prompts folder."""
    prompt_path = Path(__file__).resolve().parents[2] / "prompts" / "session_beginning_prompt.md"
    return prompt_path.read_text(encoding="utf-8")



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
        'tutor_tools': [...],  # Available options: 'pedagogy_prompt', 'RAG', 'guardrails', 'evaluator'
        'topic': '...',
        'model': 'Poro-2'
      }

    Tutor Tools:
      - 'pedagogy_prompt': Includes pedagogical guidelines for teaching approach
      - 'RAG': Retrieval-Augmented Generation - uses document context for answers
      - 'guardrails': Content safety and appropriateness filters (not yet implemented)
      - 'evaluator': Response quality evaluation tools (not yet implemented)

    Returns: assistant reply string or an error description.
    """
    if not isinstance(payload, dict):
        return "Error: payload must be a dict"

    messages = payload.get("messages")
    if not messages or not isinstance(messages, list):
        return "Error: invalid or missing messages list in payload"

    front_model = payload.get("model") or ""
    model_name = MODELS.get(front_model, front_model) or "deepseek-r1"

    # get selected tutor tools
    tutor_tools = payload.get("tutor_tools") or []
    
    # Check if this is the user's first message
    is_first_message = len([m for m in messages if m.get("role") == "user"]) <= 1
    
    system_prompt = _load_system_prompt()
    system_prompt_parts = [system_prompt]
    prompts_for_debug = ['system prompt loaded']
    
    # Add session beginning prompt for first message
    if is_first_message:
        topic = payload.get("topic") or ""
        session_beginning = _load_beginning_preprompt(topic)
        system_prompt_parts.append(session_beginning)
        prompts_for_debug.append('session beginning prompt added')
    
    # Check if pedagogical prompt should be included
    if "pedagogy_prompt" in tutor_tools:
        pedagogical_content = _load_pedagogical_prompt()
        system_prompt_parts.append(pedagogical_content)
        prompts_for_debug.append('pedagogical prompt added')

    if "RAG" in tutor_tools:
        try:
            rag_context = fetchDocuments(messages[-1].get("content", ""))
            system_prompt_parts.append(rag_context)
            prompts_for_debug.append('RAG context added')
        except Exception as e:
            print(f"Error fetching RAG context: {e}")

    print("tutor_tools selected:", tutor_tools)
    print("Prompts used in this request:", prompts_for_debug)

    system_prompt = "\n\n".join(system_prompt_parts)

    with open("debug.log", "a") as f:
        print(f"=== {system_prompt} ===", file=f)
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
    
    model = list(MODELS.values())[0]
    try:
        while True:
            user = input("You: ")
            payload = {"messages": [{"role": "user", "content": user}], "model": model}
            out = generate_response(payload)
            print("Viola:", out)
    except KeyboardInterrupt:
        print("\nExiting demo")






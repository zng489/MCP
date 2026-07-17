"""
Module: answer_questions.py
========================

Generates answers to user questions using retrieved context and a local LLM.
"""

import os
from typing import List, Dict
from gpt4all import GPT4All

from query_knowledge_base import search_knowledge_base

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_LLM_PATH = os.path.join(SCRIPT_DIR, '..', 'model', 'tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf')

MAX_TOKENS = 500
TEMPERATURE = 0.2
REPEAT_PENALTY = 1.1

# -------------------------------------------------------------------------
# LOAD LOCAL LLM
# -------------------------------------------------------------------------

print("Loading local LLM...")

try:
    llm = GPT4All(
        MODEL_LLM_PATH,
        device="gpu"  # Change to "cpu" if needed
    )
    print("✓ LLM loaded successfully")
except Exception as e:
    print(f"❌ Error loading LLM: {e}")
    print("Trying CPU fallback...")
    try:
        llm = GPT4All(
            MODEL_LLM_PATH,
            device="cpu"
        )
        print("✓ LLM loaded successfully (CPU mode)")
    except Exception as e:
        print(f"❌ Failed to load LLM: {e}")
        exit(1)

# -------------------------------------------------------------------------
# GENERATION FUNCTION
# -------------------------------------------------------------------------

def generate_answer(query: str, context_results: List[Dict]) -> str:
    """
    Generates an answer using a local LLM based on retrieved context.
    
    Args:
        query: The user's question
        context_results: List of relevant text chunks with metadata
        
    Returns:
        Generated answer based on the context
    """
    # Build context from results
    context = "\n\n".join(
        [f"[Source: {r['source']}]\n{r['text']}" for r in context_results]
    )

    # Chat-style prompt
    prompt = f"""<|system|>
You are an assistant that answers questions based only on the provided context.
If the answer is not in the context, say:
"I don't have enough information to answer this question."
Use clear and professional language.
</s>

<|user|>
CONTEXT:
{context}

QUESTION:
{query}
</s>

<|assistant|>"""

    # Generate response
    try:
        with llm.chat_session():
            response = llm.generate(
                prompt=prompt,
                max_tokens=MAX_TOKENS,
                temp=TEMPERATURE,
                repeat_penalty=REPEAT_PENALTY,
            )

        # Basic cleanup
        response = response.split("<|assistant|>")[-1].strip()
        response = response.split("</s>")[0].strip()
        response = response.split("[/INST]")[-1].strip()

        return response.strip()
    except Exception as e:
        return f"Error generating answer: {e}"

# -------------------------------------------------------------------------
# EXECUTION
# -------------------------------------------------------------------------

if __name__ == "__main__":
    user_query = input("Enter your question: ")

    print("Searching for relevant information...")
    search_results = search_knowledge_base(user_query, top_k=3)

    if not search_results:
        print("No relevant information found in the knowledge base.")
        exit(0)

    print("Generating answer...")
    answer = generate_answer(user_query, search_results)

    print("\n" + "=" * 50)
    print("ANSWER:")
    print(answer)
    print("=" * 50)

    print("\nSources consulted:")
    sources = set([os.path.basename(r['source']) for r in search_results])
    for source in sources:
        print(f"- {source}")
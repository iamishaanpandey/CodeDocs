from app.services.ai.llm_router import llm_router

async def generate_docstring(function_code: str) -> str:
    prompt = f"""
    Write a clear and concise Python docstring for the following function.
    Return ONLY the docstring text, no markdown quotes, no code blocks, DO NOT wrap it in quotes.
    
    Function:
    {function_code}
    """
    return await llm_router.generate_completion(prompt, provider="groq")

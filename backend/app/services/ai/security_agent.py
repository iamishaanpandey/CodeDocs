from app.services.ai.llm_router import llm_router

async def deeply_scan_for_vulnerabilities(code: str) -> str:
    prompt = f"""
    Analyze the following code for complex security vulnerabilities, logic flaws, or race conditions.
    Explain any found issues in detail. If none are found, say 'No vulnerabilities detected'.
    
    Code:
    {code}
    """
    return await llm_router.generate_completion(prompt, provider="groq", model="llama-3.1-70b-versatile")

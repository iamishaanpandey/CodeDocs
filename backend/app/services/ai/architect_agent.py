from app.services.ai.llm_router import llm_router

async def analyze_architecture(repo_structure: str) -> str:
    prompt = f"""
    Analyze the following repository structure and provide a high-level architectural overview.
    Identify the main components, frameworks used, and the overall design pattern.
    
    Structure:
    {repo_structure}
    """
    return await llm_router.generate_completion(prompt, provider="gemini")

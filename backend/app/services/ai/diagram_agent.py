from app.services.ai.llm_router import llm_router

async def generate_mermaid_diagram(description: str, diagram_type: str = "flowchart") -> str:
    prompt = f"""
    Create a Mermaid.js {diagram_type} for the following concept.
    Return ONLY the raw Mermaid syntax without any markdown wrappers (do not include ```mermaid or ```).
    
    Concept:
    {description}
    """
    return await llm_router.generate_completion(prompt, provider="deepseek")

import httpx
from typing import Dict, Any, Optional
from app.core.config import settings
import google.generativeai as genai

# Setup Gemini
genai.configure(api_key=settings.gemini_api_key)

class LLMRouter:
    @staticmethod
    async def generate_completion(prompt: str, provider: str = "groq", model: str = None) -> str:
        """
        Routes the prompt to the specified provider.
        Providers: gemini, groq, deepseek
        """
        if provider == "gemini":
            return await LLMRouter._call_gemini(prompt, model or settings.gemini_flash_model)
        elif provider == "groq":
            return await LLMRouter._call_groq(prompt, model or settings.groq_fast_model)
        elif provider == "deepseek":
            return await LLMRouter._call_deepseek(prompt, model or settings.deepseek_model)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    @staticmethod
    async def _call_gemini(prompt: str, model_name: str) -> str:
        model = genai.GenerativeModel(model_name)
        response = await model.generate_content_async(prompt)
        return response.text

    @staticmethod
    async def _call_groq(prompt: str, model_name: str) -> str:
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
            data = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}]
            }
            resp = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data, timeout=30.0)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    @staticmethod
    async def _call_deepseek(prompt: str, model_name: str) -> str:
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {settings.deepseek_api_key}"}
            data = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}]
            }
            resp = await client.post(f"{settings.deepseek_base_url}/chat/completions", headers=headers, json=data, timeout=30.0)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

llm_router = LLMRouter()

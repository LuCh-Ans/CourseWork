import os
from .llm_client import call_llm_internal

class LLMOrchestrator:
    def __init__(self):
        self.fast_model = "llama-3.3-70b-versatile" # Для чата
        self.accurate_model = "Qwen/Qwen2.5-72B-Instruct" # Для конспектов
        
        # Ключи
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.hf_key = os.getenv("HF_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY")

    async def get_answer(self, task_type: str, text: str, prompt: str):
        if task_type == "chat":
            model, key = self.fast_model, self.groq_key
        else:
            model, key = self.accurate_model, self.hf_key

        try:
            return await call_llm_internal(text, prompt, model, key)
        except Exception:
            print("Fallback to Gemini activated...")
            return await call_llm_internal(text, prompt, "gemini-2.5-flash", self.gemini_key)
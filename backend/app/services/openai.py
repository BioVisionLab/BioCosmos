from email.mime import base
from math import log
from venv import logger
from ..configs.config import OpenAIConfig
from openai import OpenAI


class AiSummary:
    def __init__(self):
        """
        Initializes the OpenAI service with the provided API key and base URL.
        """
        config = OpenAIConfig()
        if config.api_key is None or config.api_url is None:
            # Exit if API key or base URL is not provided
            raise ValueError(
                "OpenAI API key and base URL must be provided."
            )
        client = OpenAI(
            base_url=config.api_url, api_key=config.api_key
        )
        self.client = client
        self.model = config.model

    def summarize_text(
        self, prompt: str, word_limit: int = 250
    ) -> str:
        """
        Generate text using the OpenAI API.
        Args:
            prompt (str): The input prompt for text generation.
            model (str): The model to use for text generation.
        Returns:
            str: The generated text.
        """
        original_text = prompt
        logger.info(f"Generating summary for prompt: {prompt}")
        prompt = (
            f"You are an expert biodiversity and taxonomy editor.\n"
            f"Task: Produce a concise factual summary (<= {word_limit} words).\n"
            "Guidelines:\n"
            "- Preserve scientific names and key quantitative details.\n"
            "- Do not add information not present in the source.\n"
            "- Neutral tone, third person, no opinions.\n"
            "- Output ONLY the summary (no title, no preface, no word count).\n\n"
            "- If insufficient information, respond with 'No summary could be generated.'\n"
            "SOURCE TEXT:\n"
            f"{original_text.strip()}\n"
        )
        chat_completion = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return chat_completion.choices[0].message.content

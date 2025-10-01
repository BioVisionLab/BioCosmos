from backend.app.configs.config import OpenAIConfig
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
            api_key=config.api_key, api_base=config.api_url
        )
        self.client = client
        self.model = config.model

    async def summarize_text(
        self, prompt: str, max_length: int = 250
    ) -> str:
        """
        Generate text using the OpenAI API.
        Args:
            prompt (str): The input prompt for text generation.
            model (str): The model to use for text generation.
        Returns:
            str: The generated text.
        """
        prompt = (
            f"Summarize the following text with {max_length} tokens:\n\n"
            + prompt
        )
        chat_completion = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7,
        )
        return chat_completion.choices[0].message.content

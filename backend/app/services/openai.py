import logging

from openai import OpenAI

from ..configs.config import OpenAIConfig

logger = logging.getLogger(__name__)

# Bounds the species summary call, which otherwise waits on the provider's
# default of ten minutes.
SUMMARY_TIMEOUT_SECONDS = 60.0


def build_llm_client() -> OpenAI | None:
    """The OpenAI-compatible client the app shares, or None if unconfigured.

    Built once at startup and held on `app.state.llm_client`. A client per
    request opened a new connection pool, and a new TLS handshake, for every
    agent search and summary; the client is safe to share across the worker
    threads both run their calls in.
    """
    config = OpenAIConfig()

    if not config.api_key or not config.api_url:
        logger.info("No LLM provider configured; agent search and summaries are off.")

        return None

    return OpenAI(base_url=config.api_url, api_key=config.api_key)


class AiSummary:
    def __init__(self, client: OpenAI | None):
        """
        Wrap the shared client from `app.state.llm_client`.
        """
        if client is None:
            raise ValueError("OpenAI API key and base URL must be provided.")

        config = OpenAIConfig()

        if config.model is None:
            raise ValueError("OpenAI model must be provided.")

        self.client = client
        self.model = config.model

    def summarize_text(self, prompt: str, word_limit: int = 250) -> str | None:
        """
        Generate text using the OpenAI API.
        Args:
            prompt (str): The input prompt for text generation.
            model (str): The model to use for text generation.
        Returns:
            str | None: The generated text, or None when the model returned
            no content.
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
            timeout=SUMMARY_TIMEOUT_SECONDS,
        )
        return chat_completion.choices[0].message.content

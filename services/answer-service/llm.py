"""Pluggable language-model interface for drafting ticket replies.

MockLLMClient is the default: it drafts a reply using ONLY the retrieved
knowledge-base snippets, in a fixed template. It never invents facts and
refuses to draft when no source was retrieved.

RealLLMClient is a stub for a real model provider. It refuses to run
until a model is configured — it never calls any external API on its
own, and no API key is stored anywhere in this project.
"""
import os


class MockLLMClient:
    def draft(self, question, category, priority, sources, style="short"):
        if not sources:
            return ("I could not find a knowledge-base article that answers "
                    "this question, so I will not guess. A support agent "
                    "will review your ticket.")
        titles = ", ".join(s["title"] for s in sources)
        first = sources[0]
        reply = (
            f"Hello, thank you for writing about your {category} issue "
            f"(priority: {priority}). Based on \"{first['title']}\": "
            f"{first['snippet']} "
        )
        if style == "detailed":
            reply += (
                "Here is what to do next, step by step, following that "
                "article. If the steps do not fix it, reply to this ticket "
                "and a support agent will take over. "
                f"Related articles: {titles}."
            )
        else:
            reply += "Please follow those steps and let us know if it helps."
        return reply


class RealLLMClient:
    def __init__(self, model=None):
        self.model = model or os.environ.get("LLM_MODEL")

    def draft(self, question, category, priority, sources, style="short"):
        raise RuntimeError(
            "RealLLMClient is not configured: set LLM_MODEL and an approved "
            "model provider before use. Nothing was sent to any model."
        )


def get_client():
    if os.environ.get("USE_REAL_LLM") == "1":
        return RealLLMClient()
    return MockLLMClient()

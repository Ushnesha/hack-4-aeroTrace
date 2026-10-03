"""Ask stream entry point."""

from typing import cast

from aerotrace.contracts import AskAnswer, FakeGraphRepository, GraphRepository, fake_answer


def answer(repo: GraphRepository, run_id: str, question: str) -> AskAnswer:
    """Answer a question using typed graph tools (currently the fake)."""
    # TODO(narrative): replace with real implementation
    return fake_answer(cast(FakeGraphRepository, repo), run_id, question)

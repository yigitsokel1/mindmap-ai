"""Passage splitter for document text.

Splits raw document text into passage-sized units suitable
for LLM extraction. Uses RecursiveCharacterTextSplitter
with parameters tuned for extraction (not embedding).
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter


class PassageSplitter:
    """Splits text into extraction-ready passages."""

    def __init__(self, chunk_size: int = 1600, chunk_overlap: int = 200):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def split(self, text: str) -> list[str]:
        """Split text into passages.

        Args:
            text: Full document or section text.

        Returns:
            List of passage strings.
        """
        return self.splitter.split_text(text)

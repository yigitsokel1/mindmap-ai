"""Question interpreter contract for semantic query planning."""


class QuestionInterpreter:
    """Interpret natural language questions into structured query hints."""

    def interpret(self, question: str) -> dict:
        return {
            "intent": None,
            "entities": [],
            "relation_types": [],
            "constraints": {},
        }

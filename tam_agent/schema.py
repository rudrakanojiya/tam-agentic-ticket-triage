"""Phase 1 output contract; the brief's referenced starter schema was not supplied."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Priority = Literal['P1', 'P2', 'P3', 'P4']
Category = Literal['Bug', 'Feature Request', 'How-To', 'Performance', 'Billing',
                   'Integration', 'Onboarding', 'Data Loss']


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')


class TraceStep(StrictModel):
    """Concise decision summary and observable tool evidence, not hidden reasoning."""
    thought: Text
    action: Text
    observation: Text
    outcome: Text


class TriageOutput(StrictModel):
    category: Category
    priority: Priority
    routing: Text
    escalation: bool
    tam_notification: bool
    duplicate_status: bool
    duplicate_of_ticket_id: Text | None
    clarification_needed: bool
    customer_reply: Text
    internal_note: Text
    reasoning_trace: Annotated[list[TraceStep], Field(min_length=1)]

    @model_validator(mode='after')
    def consistent_duplicate(self):
        if self.duplicate_status != (self.duplicate_of_ticket_id is not None):
            raise ValueError('duplicate_status must agree with duplicate_of_ticket_id')
        return self


def validate_output(data: dict) -> TriageOutput:
    """Return validated output; raise pydantic.ValidationError on invalid data.

    Structural validation cannot guarantee politeness, factual accuracy, absence
    of internal leaks, or completeness of SLA/KB analysis; those need evaluation.
    """
    return TriageOutput.model_validate(data)

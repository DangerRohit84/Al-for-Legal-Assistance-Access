"""Action helper: checklists + draft letters. Always labelled, never advice."""
from __future__ import annotations

from .prompting import DISCLAIMER


def build_checklist(question: str, evidence: list) -> list:
    q = (question or "your matter").strip()[:120]
    cites = "; ".join(evidence[:2]) if evidence else "see uploaded PDF"
    return [
        f"1. Re-read cited clause(s): {cites}",
        f"2. Collect proof related to: {q}",
        "3. Note dates, amounts, and names in writing",
        "4. Check deadlines (notice period, limitation) in the document",
        "5. Verify with a qualified lawyer before acting",
    ]


def build_draft(topic: str, evidence: list) -> str:
    t = (topic or "Request").strip()[:120] or "Request"
    cites = "; ".join(evidence[:3]) if evidence else "the attached document"
    return (
        "[DRAFT — review before sending]\n"
        f"Re: {t}\n\n"
        "Dear Sir/Madam,\n"
        f"Per {cites}, I write regarding '{t}'. "
        "Kindly confirm your position in writing within 7 days.\n\n"
        "Sincerely,\n[Your Name]\n[Address / Contact]\n\n"
        f"({DISCLAIMER})"
    )

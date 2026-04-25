"""Agent Grounding Chain — multi-step session guard (H8).

When multiple LLM calls occur in sequence (extraction → synthesis → report),
this module tracks cumulative grounding scores and halts the chain if any
step drops below the configured threshold.
"""
import logging
import uuid
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Default halt threshold (configurable per project)
DEFAULT_HALT_THRESHOLD = 0.6


class GroundingChainSession:
    """
    Manages a single multi-step grounding chain.

    Usage:
        chain = GroundingChainSession(project_id=1)
        chain.record_step('extraction', grounding_score=0.85)
        chain.record_step('synthesis', grounding_score=0.55)
        chain.should_halt  # True — below threshold
    """

    def __init__(
        self,
        project_id: int,
        session_id: Optional[str] = None,
        halt_threshold: float = DEFAULT_HALT_THRESHOLD,
    ):
        self.project_id = project_id
        self.session_id = session_id or str(uuid.uuid4())
        self.halt_threshold = halt_threshold
        self.steps: List[Dict[str, Any]] = []
        self._halted = False
        self._halt_reason: Optional[str] = None

    @property
    def should_halt(self) -> bool:
        return self._halted

    @property
    def halt_reason(self) -> Optional[str]:
        return self._halt_reason

    @property
    def current_score(self) -> Optional[float]:
        if not self.steps:
            return None
        return self.steps[-1].get('grounding_score')

    @property
    def cumulative_score(self) -> Optional[float]:
        """Average grounding score across all steps."""
        scores = [s['grounding_score'] for s in self.steps if s.get('grounding_score') is not None]
        if not scores:
            return None
        return sum(scores) / len(scores)

    def record_step(
        self,
        step_name: str,
        grounding_score: Optional[float],
        answer_text: str = '',
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record a pipeline step and check halt conditions.

        Returns:
            dict with 'halted' (bool), 'reason' (str | None), 'step_index' (int).
        """
        step = {
            'step_name': step_name,
            'grounding_score': grounding_score,
            'answer_text_snippet': answer_text[:200] if answer_text else '',
            'metadata': metadata or {},
        }
        self.steps.append(step)

        # Check halt condition
        if grounding_score is not None and grounding_score < self.halt_threshold:
            self._halted = True
            self._halt_reason = (
                f"Grounding score {grounding_score:.2f} at step '{step_name}' "
                f"is below threshold {self.halt_threshold:.2f}. "
                f"Human review required before continuing."
            )
            logger.warning(
                f"[GroundingChain] HALT session={self.session_id} "
                f"step={step_name} score={grounding_score:.2f}"
            )

        return {
            'halted': self._halted,
            'reason': self._halt_reason,
            'step_index': len(self.steps) - 1,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'project_id': self.project_id,
            'halt_threshold': self.halt_threshold,
            'halted': self._halted,
            'halt_reason': self._halt_reason,
            'cumulative_score': self.cumulative_score,
            'steps': self.steps,
        }


# Simple in-memory session store (per process).
# For production, persist to DB or Redis.
_active_sessions: Dict[str, GroundingChainSession] = {}


def create_chain_session(
    project_id: int,
    halt_threshold: float = DEFAULT_HALT_THRESHOLD,
) -> GroundingChainSession:
    """Create and register a new grounding chain session."""
    session = GroundingChainSession(
        project_id=project_id,
        halt_threshold=halt_threshold,
    )
    _active_sessions[session.session_id] = session
    return session


def get_chain_session(session_id: str) -> Optional[GroundingChainSession]:
    """Retrieve an active chain session by ID."""
    return _active_sessions.get(session_id)


def close_chain_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Remove a chain session and return its final summary."""
    session = _active_sessions.pop(session_id, None)
    if session:
        return session.to_dict()
    return None

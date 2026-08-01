"""Evidence aggregation for type-specific proposal calibration.

This module only builds feature rows. It deliberately does not emit competition
entities, because accept/reject thresholds must be learned from independent
reviewed labels rather than chosen from the public inputs.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Iterable

from .proposals import Proposal
from .schema import Entity


@dataclass(frozen=True)
class ProposalEvidence:
    text: str
    type: str
    position: tuple[int, int]
    sources: tuple[str, ...]
    confidences: tuple[float, ...]
    source_count: int
    mean_confidence: float
    max_confidence: float
    baseline_exact: bool
    baseline_overlap_same_type: bool

    def to_dict(self) -> dict:
        value = asdict(self)
        value["position"] = list(self.position)
        value["sources"] = list(self.sources)
        value["confidences"] = list(self.confidences)
        return value


def aggregate_exact_evidence(
    proposal_groups: Iterable[Iterable[Proposal]],
    baseline: Iterable[Entity] = (),
) -> list[ProposalEvidence]:
    grouped: dict[
        tuple[int, int, str, str], list[Proposal]
    ] = defaultdict(list)
    for proposals in proposal_groups:
        for proposal in proposals:
            start, end = proposal.position
            grouped[(start, end, proposal.type, proposal.text)].append(proposal)

    baseline_values = list(baseline)
    baseline_exact = {
        (entity.position[0], entity.position[1], entity.type, entity.text)
        for entity in baseline_values
    }
    result: list[ProposalEvidence] = []
    for key, values in grouped.items():
        start, end, kind, text = key
        by_source: dict[str, float] = {}
        for proposal in values:
            by_source[proposal.source] = max(
                by_source.get(proposal.source, 0.0),
                proposal.confidence,
            )
        sources = tuple(sorted(by_source))
        confidences = tuple(by_source[source] for source in sources)
        overlaps = any(
            entity.type == kind
            and max(0, min(end, entity.position[1]) - max(start, entity.position[0])) > 0
            for entity in baseline_values
        )
        result.append(
            ProposalEvidence(
                text=text,
                type=kind,
                position=(start, end),
                sources=sources,
                confidences=confidences,
                source_count=len(sources),
                mean_confidence=sum(confidences) / len(confidences),
                max_confidence=max(confidences),
                baseline_exact=key in baseline_exact,
                baseline_overlap_same_type=overlaps,
            )
        )
    return sorted(
        result,
        key=lambda value: (
            value.position[0],
            value.position[1],
            value.type,
            value.text,
        ),
    )

import pytest

from airace.h44_transfer import transfer_calibration


def _reports(overlap: bool = False):
    h23_changes = [
        {
            "record": str(index),
            "position": [index, index + 1],
            "new_candidates": ["A00", f"A00.{index}"],
        }
        for index in range(144)
    ]
    h44_changes = [
        {
            "record_id": str(index + (0 if overlap else 1000)),
            "position": [index, index + 1],
            "after": ["A00", f"A00.{index}"],
        }
        for index in range(611)
    ]
    return {"changes": h23_changes}, {"changes": h44_changes}


def test_transfer_calibration_counts_disjoint_lineage() -> None:
    h23, h44 = _reports()
    report = transfer_calibration(h23, h44)
    assert report["lineage"] == {
        "h23_rows": 144,
        "h44_rows": 611,
        "exact_overlap_rows": 0,
        "disjoint_h44_rows": 611,
        "union_rows": 755,
    }


def test_transfer_ratio_arithmetic() -> None:
    h23, h44 = _reports()
    report = transfer_calibration(h23, h44)
    forecast = report["h44_linear_transfer_forecast"]
    gates = report["locked_gate_calibration"]
    assert forecast["candidate_delta_at_100_percent_h23_per_row_yield"] == pytest.approx(1.4600354167)
    assert gates["strong_gate_equivalent_h23_yield_ratio"] == pytest.approx(0.3424574514)


def test_overlap_is_detected_by_stable_identity() -> None:
    h23, h44 = _reports(overlap=True)
    report = transfer_calibration(h23, h44)
    assert report["lineage"]["exact_overlap_rows"] == 144

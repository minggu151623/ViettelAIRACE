from airace.confidence_calibration import dev_gates, select_threshold, threshold_metrics


def test_threshold_metrics_filters_entity_scores():
    rows = [
        {"record": 1, "position": [0, 3], "type": "x", "confidence": .9},
        {"record": 1, "position": [4, 7], "type": "x", "confidence": .6},
    ]
    gold = {(0, 3, "x", 1)}
    result = threshold_metrics(rows, gold, .8)
    assert result["precision"] == result["recall"] == result["f1"] == 1


def test_selection_obeys_precision_constraint_and_tiebreak():
    grid = [
        {"threshold": .7, "precision": .79, "recall": .8, "f1": .8},
        {"threshold": .8, "precision": .8, "recall": .4, "f1": .6},
        {"threshold": .9, "precision": .9, "recall": .4, "f1": .6},
    ]
    assert select_threshold(grid)["threshold"] == .9
    assert not all(dev_gates(select_threshold(grid), 0).values())  # recall absent/fail closed

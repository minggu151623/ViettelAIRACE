from airace.per_fold_calibration import _signature


def test_signature_ignores_input_order_but_not_confidence():
    rows = [
        {"record": 2, "position": [3, 4], "type": "x", "confidence": .9},
        {"record": 1, "position": [0, 1], "type": "y", "confidence": .8},
    ]
    assert _signature(rows) == _signature(list(reversed(rows)))
    changed = [{**rows[0], "confidence": .91}, rows[1]]
    assert _signature(rows) != _signature(changed)

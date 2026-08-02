from airace.boundary_selector import dev_gates, enumerate_choices


def test_enumerator_returns_raw_substrings_and_contains_seed():
    raw = "Khám thấy phù gai thị hai bên."
    start = raw.index("phù")
    end = start + len("phù")
    choices = enumerate_choices(raw, (start, end))
    assert any(choice["text"] == "phù gai thị" for choice in choices)
    assert all(raw[choice["position"][0]:choice["position"][1]] == choice["text"]
               for choice in choices)
    assert all(choice["position"][0] <= start and choice["position"][1] >= end
               for choice in choices)


def test_enumerator_does_not_cross_lines():
    raw = "đau đầu\nkhông sốt"
    choices = enumerate_choices(raw, (0, 3))
    assert all("\n" not in choice["text"] for choice in choices)


def test_dev_gates_are_fail_closed():
    result = {
        "enumeration": {"coverage": 0.95},
        "corrupted_exact_recovery": 0.70,
        "unchanged_control_retention": 0.93,
        "malformed_response_rate": 0,
    }
    assert all(dev_gates(result).values())

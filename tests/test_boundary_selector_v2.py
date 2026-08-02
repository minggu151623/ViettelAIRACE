from airace.boundary_selector_v2 import dev_gates_v2, enumerate_choices_v2


def test_v2_handles_multi_token_seed_and_punctuation_variants():
    raw = "Dùng Vastarel (trimetazidin)."
    start = raw.index("Vastarel")
    end = raw.index(")") + 1
    choices = enumerate_choices_v2(raw, (start, end))
    assert any(choice["text"] == "Vastarel (trimetazidin)" for choice in choices)
    assert all(raw[choice["position"][0]:choice["position"][1]] == choice["text"]
               for choice in choices)


def test_v2_can_expand_seven_tokens_from_first_token():
    raw = "không thể chịu lực ở chân phải hôm nay"
    seed = (0, len("không"))
    choices = enumerate_choices_v2(raw, seed)
    assert any(choice["text"] == "không thể chịu lực ở chân phải" for choice in choices)


def test_v2_gate_thresholds():
    result = {
        "enumeration": {"coverage": 1.0},
        "corrupted_exact_recovery": 0.70,
        "unchanged_control_retention": 0.93,
        "malformed_response_rate": 0,
    }
    assert all(dev_gates_v2(result).values())

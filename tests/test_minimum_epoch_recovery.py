import inspect

from airace.train import train_model


def test_trainer_exposes_minimum_epoch_safeguard():
    signature = inspect.signature(train_model)
    assert signature.parameters["minimum_epochs"].default == 0

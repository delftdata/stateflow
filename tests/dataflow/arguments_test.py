import pytest
from tests.context import stateflow
from stateflow.dataflow.args import Arguments


def test_match_simple_args():
    desc = {"x": int}
    args = Arguments.from_args_and_kwargs(desc, 1)

    assert args.get() == {"x": 1}


def test_match_more_args():
    desc = {"x": int, "y": str, "z": list}
    args = Arguments.from_args_and_kwargs(desc, 1, "hi", ["no"])

    assert args.get() == {"x": 1, "y": "hi", "z": ["no"]}


def test_match_simple_kwargs():
    desc = {"x": int}
    args = Arguments.from_args_and_kwargs(desc, x=1)

    assert args.get() == {"x": 1}


def test_match_more_kwargs():
    desc = {"x": int, "y": str, "z": list}
    args = Arguments.from_args_and_kwargs(desc, x=1, y="hi", z=["no"])

    assert args.get() == {"x": 1, "y": "hi", "z": ["no"]}


def test_match_mix_args_kwargs():
    desc = {"x": int, "y": str, "z": list}
    args = Arguments.from_args_and_kwargs(desc, 1, y="hi", z=["no"])

    assert args.get() == {"x": 1, "y": "hi", "z": ["no"]}


def test_match_mix_args_kwargs_more():
    desc = {"x": int, "y": str, "z": list}
    args = Arguments.from_args_and_kwargs(desc, 1, z=["no"], y="hi")

    assert args.get() == {"x": 1, "y": "hi", "z": ["no"]}


def test_match_wrong_desc():
    desc = {"x": int, "y": str, "z": list}

    with pytest.raises(AttributeError):
        Arguments.from_args_and_kwargs(desc, x=1, y="hi", z=["no"], not_exist=1)

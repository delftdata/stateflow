from tests.context import stateflow
from stateflow.analysis.ast_utils import *


def test_self_positive():
    stmt = "self.x"
    parsed = cst.parse_statement(stmt)

    assert is_self(parsed.body[0].value)


def test_self_negative():
    stmt = "not_self.x"
    parsed = cst.parse_statement(stmt)

    assert not is_self(parsed.body[0].value)


def test_self_not_attribute():
    stmt = "x + 3"
    parsed = cst.parse_statement(stmt)

    assert not is_self(parsed.body[0].value)


def test_type_positive_primitive():
    stmt = "x: int"
    parsed = cst.parse_module(stmt)
    assert extract_types(parsed, parsed.body[0].body[0].annotation) == "int"

    stmt = "x: str"
    parsed = cst.parse_module(stmt)
    assert extract_types(parsed, parsed.body[0].body[0].annotation) == "str"

    stmt = "x: bool"
    parsed = cst.parse_module(stmt)
    assert extract_types(parsed, parsed.body[0].body[0].annotation) == "bool"

    stmt = "x: float"
    parsed = cst.parse_module(stmt)
    assert extract_types(parsed, parsed.body[0].body[0].annotation) == "float"

    stmt = "x: bytes"
    parsed = cst.parse_module(stmt)
    assert extract_types(parsed, parsed.body[0].body[0].annotation) == "bytes"


def test_type_positive_complex_types():
    stmt = """
from collections.abc import Sequence
ConnectionOptions = dict[str, str]
Address = tuple[str, int]
Server = tuple[Address, ConnectionOptions]

x: Sequence[Server]
    """
    parsed = cst.parse_module(stmt)
    assert (
        extract_types(parsed, parsed.body[-1].body[0].annotation) == "Sequence[Server]"
    )

    stmt = """
class TestClass:
    pass

x: TestClass
        """
    parsed = cst.parse_module(stmt)
    assert extract_types(parsed, parsed.body[-1].body[0].annotation) == "TestClass"

    stmt = """
x: List[int]
        """
    parsed = cst.parse_module(stmt)
    assert extract_types(parsed, parsed.body[-1].body[0].annotation) == "List[int]"

    stmt = """
x: List[OtherClass]
        """
    parsed = cst.parse_module(stmt)
    assert (
        extract_types(parsed, parsed.body[-1].body[0].annotation) == "List[OtherClass]"
    )


def test_type_unpacking():
    stmt = "x: Tuple[str, int, bytes]"
    parsed = cst.parse_module(stmt)
    assert extract_types(parsed, parsed.body[0].body[0].annotation, unpack=True) == [
        "str",
        "int",
        "bytes",
    ]


def test_type_complex():
    stmt = "x: Tuple[str, int, bytes, List[str]]"
    parsed = cst.parse_module(stmt)
    assert extract_types(parsed, parsed.body[0].body[0].annotation, unpack=True) == [
        "str",
        "int",
        "bytes",
        "List[str]",
    ]

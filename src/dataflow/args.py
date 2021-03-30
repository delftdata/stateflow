from typing import Dict, Any, List, Optional


class Arguments:

    __slots__ = "_args"

    def __init__(self, args: Dict[str, Any]):
        self._args = args

    def __getitem__(self, item):
        return self._args[item]

    def __setitem__(self, key, value):
        self._args[key] = value

    def get(self) -> Dict[str, Any]:
        return self._args

    def get_keys(self) -> List[str]:
        return self._args.keys()

    @staticmethod
    def from_args_and_kwargs(*args, **kwargs) -> Optional["Arguments"]:
        pass

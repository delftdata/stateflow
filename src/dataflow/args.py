from typing import Dict, Any, List


class Arguments:
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

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
    def from_args_and_kwargs(
        desc: Dict[str, Any], *args, **kwargs
    ) -> Optional["Arguments"]:
        args_dict = {}
        print(list(args))
        for arg, name in zip(list(args), desc.keys()):
            args_dict[name] = arg
            print(f"Now set {name} and {arg}")

        for key, value in kwargs:
            args_dict[key] = value

        arguments = Arguments(args_dict)

        if not desc.keys() == args_dict.keys():
            raise AttributeError(f"Expected arguments: {desc} but got {args_dict}.")

        return arguments

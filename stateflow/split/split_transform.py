import libcst as cst
from libcst import matchers as m
from typing import Union, List, Dict
from stateflow.split.split_block import StatementBlock


class RemoveAfterClassDefinition(cst.CSTTransformer):
    def __init__(self, class_name: str):
        self.class_name: str = class_name
        self.is_defined = False

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> Union[cst.BaseStatement, cst.RemovalSentinel]:

        new_decorators = []
        for decorator in updated_node.decorators:
            if "stateflow" not in cst.helpers.get_full_name_for_node(decorator):
                new_decorators.append(decorator)

        if original_node.name == self.class_name:
            self.is_defined = True
            return updated_node.with_changes(decorators=tuple(new_decorators))

        return updated_node.with_changes(decorators=tuple(new_decorators))

    # def on_leave(
    #     self, original_node: cst.CSTNodeT, updated_node: cst.CSTNodeT
    # ) -> Union[cst.CSTNodeT, cst.RemovalSentinel]:
    #     if self.is_defined:
    #         return cst.RemovalSentinel()


class SplitTransformer(cst.CSTTransformer):
    def __init__(
        self, class_name: str, updated_methods: Dict[str, List[StatementBlock]]
    ):
        self.class_name: str = class_name
        self.updated_methods = updated_methods

    def visit_ClassDef(self, node: cst.ClassDef):
        if node.name.value != self.class_name:
            return False
        return True

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> Union[cst.BaseStatement, cst.RemovalSentinel]:
        if updated_node.name.value != self.class_name:
            return updated_node

        class_body = updated_node.body.body

        for method in self.updated_methods.values():
            for split in method:
                class_body = (*class_body, split.new_function)

        return updated_node.with_changes(
            body=updated_node.body.with_changes(body=class_body)
        )

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.CSTNode:
        if (
            m.matches(original_node.body, m.IndentedBlock())
            and updated_node.name.value in self.updated_methods
        ):
            pass_node = cst.SimpleStatementLine(body=[cst.Pass()])
            new_block = original_node.body.with_changes(body=[pass_node])
            return updated_node.with_changes(body=new_block)

        return updated_node

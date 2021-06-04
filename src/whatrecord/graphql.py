from typing import List

import apischema
from graphql import graphql_sync, print_schema

from .common import AsynPortBase, WhatRecord
from .shell import ScriptContainer


class QueryHelper:
    def __init__(self, container: ScriptContainer):
        self.container = container
        self.schema = apischema.graphql.graphql_schema(
            query=[self.whatrec, self.whatasyn]
        )

    def describe_schema(self) -> str:
        # TODO: remove
        return print_schema(self.schema)

    def whatrec(self, name: str) -> List[WhatRecord]:
        return self.container.whatrec(name, file=None)

    def whatasyn(self, name: str) -> List[AsynPortBase]:
        return []

    def query(self, query):
        return graphql_sync(self.schema, query)

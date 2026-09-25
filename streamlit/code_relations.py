"""Conservative references between Python symbols; never import analyzed code."""
from __future__ import annotations

import ast
import builtins
from dataclasses import dataclass, field

from code_snapshot import Snapshot


DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def owned_nodes(node):
    """Walk a scope's execution, leaving child bodies to their own symbols."""
    roots = node.body if isinstance(node, (*DEFINITIONS, ast.Module)) else [node]
    if isinstance(node, DEFINITIONS):
        roots = [*node.decorator_list, *roots]
        if isinstance(node, ast.ClassDef):
            roots += list(node.bases) + [kw.value for kw in node.keywords]
        else:
            roots += list(node.args.defaults) + [v for v in node.args.kw_defaults if v is not None]

    def walk(item):
        yield item
        if isinstance(item, DEFINITIONS):
            expressions = list(item.decorator_list)
            if isinstance(item, ast.ClassDef):
                expressions += list(item.bases) + [kw.value for kw in item.keywords]
            else:
                expressions += list(item.args.defaults)
                expressions += [v for v in item.args.kw_defaults if v is not None]
            for expression in expressions:
                yield from walk(expression)
            return
        if isinstance(item, ast.Lambda):
            return  # Lambda bodies have no stable named scope in this version.
        for child in ast.iter_child_nodes(item):
            yield from walk(child)

    for root in roots:
        yield from walk(root)


@dataclass
class Scope:
    symbol: object
    imports: dict[str, str] = field(default_factory=dict)
    definitions: dict[str, str] = field(default_factory=dict)
    stores: set[str] = field(default_factory=set)
    params: set[str] = field(default_factory=set)
    globals: set[str] = field(default_factory=set)
    nonlocals: set[str] = field(default_factory=set)
    ambiguous: set[str] = field(default_factory=set)


class Resolver:
    def __init__(self, snapshot: Snapshot):
        self.snapshot = snapshot
        self.scopes = {}
        self.modules = {}
        for symbol in snapshot.symbols.values():
            self.modules.setdefault(symbol.module, {})[symbol.qualified_name] = symbol.id
            scope = Scope(symbol)
            counts = {}

            def bind(name, kind):
                counts.setdefault(name, []).append(kind)

            for item in owned_nodes(symbol.node):
                if isinstance(item, DEFINITIONS):
                    qual = item.name if symbol.qualified_name == "<module>" else f"{symbol.qualified_name}.{item.name}"
                    scope.definitions[item.name] = f"{symbol.file}::{qual}"
                    bind(item.name, "definition")
                elif isinstance(item, ast.Import):
                    for alias in item.names:
                        local = alias.asname or alias.name.split(".")[0]
                        scope.imports[local] = alias.name if alias.asname else local
                        bind(local, "import")
                elif isinstance(item, ast.ImportFrom):
                    module = self.import_module(symbol, item)
                    for alias in item.names:
                        if alias.name == "*":
                            continue
                        local = alias.asname or alias.name
                        scope.imports[local] = ".".join(p for p in (module, alias.name) if p)
                        bind(local, "import")
                elif isinstance(item, ast.Name) and isinstance(item.ctx, (ast.Store, ast.Del)):
                    scope.stores.add(item.id)
                    bind(item.id, "delete" if isinstance(item.ctx, ast.Del) else "store")
                elif isinstance(item, ast.ExceptHandler) and item.name:
                    scope.stores.add(item.name)
                    bind(item.name, "store")
                elif isinstance(item, (ast.MatchAs, ast.MatchStar)) and item.name:
                    scope.stores.add(item.name)
                    bind(item.name, "store")
                elif isinstance(item, ast.MatchMapping) and item.rest:
                    scope.stores.add(item.rest)
                    bind(item.rest, "store")
                elif isinstance(item, ast.Global):
                    scope.globals.update(item.names)
                elif isinstance(item, ast.Nonlocal):
                    scope.nonlocals.update(item.names)
            if isinstance(symbol.node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = symbol.node.args
                scope.params.update(a.arg for a in [*args.posonlyargs, *args.args, *args.kwonlyargs])
                scope.params.update(a.arg for a in (args.vararg, args.kwarg) if a)
            scope.ambiguous = {name for name, kinds in counts.items() if len(kinds) > 1 and set(kinds) != {"store"}}
            scope.ambiguous.update(scope.params & (set(scope.imports) | set(scope.definitions)))
            self.scopes[symbol.id] = scope

    def import_module(self, symbol, node):
        if node.level == 0:
            return node.module or ""
        path = symbol.file.split("#cell-")[0]
        package = symbol.module.split(".") if path.endswith("/__init__.py") or path == "__init__.py" else symbol.module.split(".")[:-1]
        climb = node.level - 1
        if climb >= len(package) and climb:
            return "<unresolved-relative-import>"
        if climb:
            package = package[:-climb]
        return ".".join([*package, *([node.module] if node.module else [])])

    def scope_chain(self, symbol):
        parts = symbol.qualified_name.split(".") if symbol.qualified_name != "<module>" else []
        candidates = [".".join(parts[:i]) for i in range(len(parts), 0, -1)] + ["<module>"]
        for qual in candidates:
            scope = self.scopes.get(f"{symbol.file}::{qual}")
            if scope and (scope.symbol.id == symbol.id or scope.symbol.kind != "class"):
                yield scope

    def canonical(self, dotted):
        return self.canonical_guarded(dotted, set())

    def runtime_member(self, symbol_id, tail):
        """Only classes expose named child definitions as ordinary attributes."""
        current = self.snapshot.symbols.get(symbol_id)
        parts = tail.split(".")
        for index, name in enumerate(parts):
            if not current or current.kind != "class":
                return None
            scope = self.scopes[current.id]
            if name in scope.ambiguous:
                return None
            if name in scope.stores:
                return current.id if index == len(parts) - 1 else None
            current = self.snapshot.symbols.get(current.id + "." + name)
        return current.id if current else None

    def canonical_guarded(self, dotted, visited):
        if dotted in visited:
            return None
        visited = visited | {dotted}
        for module in sorted(self.modules, key=len, reverse=True):
            if dotted == module:
                return self.modules[module].get("<module>")
            if not dotted.startswith(module + "."):
                continue
            qual = dotted[len(module) + 1:]
            scope = self.scopes.get(self.modules[module].get("<module>"))
            head, _, tail = qual.partition(".")
            if scope and head in scope.ambiguous:
                return None
            found = self.modules[module].get(head)
            if found:
                return self.runtime_member(found, tail) if tail else found
            if scope and head in scope.imports and head not in scope.ambiguous:
                return self.canonical_guarded(scope.imports[head] + ("." + tail if tail else ""), visited)
            if scope and qual in scope.stores:
                return scope.symbol.id
        return None

    def receiver_class(self, symbol, name):
        if not isinstance(symbol.node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return None
        args = [*symbol.node.args.posonlyargs, *symbol.node.args.args]
        if not args or args[0].arg != name:
            return None
        if any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in symbol.node.decorator_list):
            return None
        scope = self.scopes[symbol.id]
        if name in scope.stores or name in scope.ambiguous:
            return None
        parts = symbol.qualified_name.split(".")[:-1]
        # Only direct methods; nested functions' first arg isn't a class receiver.
        class_id = f"{symbol.file}::{'.'.join(parts)}"
        cls = self.snapshot.symbols.get(class_id)
        return cls if cls and cls.kind == "class" else None

    def resolve(self, symbol, expression):
        text = dotted(expression)
        if not text:
            return None, "dynamic expression"
        head, _, tail = text.partition(".")
        if tail:
            cls = self.receiver_class(symbol, head)
            if cls:
                method = self.runtime_member(cls.id, tail)
                if method:
                    return method, None
                return None, "inherited or dynamic instance member"
        chain = list(self.scope_chain(symbol))
        if chain and head in chain[0].globals:
            chain = [self.scopes[f"{symbol.file}::<module>"]]
        for scope in chain:
            if head in scope.globals and scope.symbol.qualified_name != "<module>":
                continue
            if head in scope.nonlocals:
                continue
            if head in scope.ambiguous:
                return None, "binding redefined in scope"
            if head in scope.params:
                return None, "parameter or dynamic dispatch"
            if head in scope.imports:
                target = scope.imports[head] + ("." + tail if tail else "")
                return self.canonical(target), "external or unavailable import"
            if head in scope.definitions:
                target = self.runtime_member(scope.definitions[head], tail) if tail else scope.definitions[head]
                return (target, None) if target in self.snapshot.symbols else (None, "unresolved member")
            if head in scope.stores:
                if scope.symbol.kind in {"module", "class"} and not tail:
                    return scope.symbol.id, None
                return None, "local binding or unknown instance"
        if head in vars(builtins):
            return None, "builtin"
        return None, "unresolved name"


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted(node.value)
        return f"{parent}.{node.attr}" if parent else ""
    return ""


def build_relations(snapshot: Snapshot) -> dict:
    resolver = Resolver(snapshot)
    edges, unresolved, external = [], [], []
    seen = set()

    def add(symbol, callee, kind, item, expression):
        if callee == symbol.id or callee not in snapshot.symbols:
            return
        key = (symbol.id, callee, kind, getattr(item, "lineno", 1), expression)
        if key not in seen:
            seen.add(key)
            edges.append(dict(caller=symbol.id, callee=callee, kind=kind, line=key[3], expression=expression))

    for symbol in snapshot.symbols.values():
        nodes = list(owned_nodes(symbol.node))
        for item in nodes:
            if isinstance(item, ast.Call):
                name = dotted(item.func) or ast.unparse(item.func)
                callee, reason = resolver.resolve(symbol, item.func)
                if callee:
                    add(symbol, callee, "call", item, name)
                    if snapshot.symbols[callee].kind == "class":
                        init_id = callee + ".__init__"
                        add(symbol, init_id, "call", item, name + ".__init__")
                else:
                    record = dict(caller=symbol.id, line=item.lineno, expression=name, reason=reason)
                    (external if reason in {"builtin", "external or unavailable import"} else unresolved).append(record)
            elif isinstance(item, (ast.Name, ast.Attribute)) and isinstance(item.ctx, ast.Load):
                callee, _ = resolver.resolve(symbol, item)
                if callee:
                    add(symbol, callee, "reference", item, dotted(item))
    return {
        "edges": sorted(edges, key=lambda e: (e["caller"], e["line"], e["callee"], e["kind"])),
        "unresolved": sorted(unresolved, key=lambda e: (e["caller"], e["line"], e["expression"])),
        "external": external,
        "limitations": [
            "정적 호출·참조 후보이며 실행 순서나 실제 영향/Pass를 증명하지 않습니다.",
            "매개변수로 전달한 함수, 별칭 대입, 인스턴스 변수, 상속·동적 속성·리플렉션은 추적하지 않습니다.",
            "조건부 바인딩·컴프리헨션·데코레이터와 재정의는 일부 관계를 누락하거나 넓게 잡을 수 있습니다.",
            "노트북 셀 간 이름 해석과 star import, 암묵적 sys.path 변경은 지원하지 않습니다.",
        ],
    }

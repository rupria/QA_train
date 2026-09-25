"""Bounded, conservative Python value-dependency candidates; never run source."""
from __future__ import annotations

import ast
import copy
import hashlib
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
import uuid

from code_comparison import comparison_input
from code_relations import Resolver, build_relations, dotted, owned_nodes
from code_snapshot import load_snapshot


FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
DEFINITIONS = (*FUNCTIONS, ast.ClassDef)
COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
RELATION_KINDS = {"call", "reference"}


class _Graph:
    def __init__(self, snapshot, root, depth, cap):
        self.snapshot, self.root, self.depth, self.cap = snapshot, root, depth, cap
        self.resolver = Resolver(snapshot)
        self.nodes, self.edges, self.unresolved = {}, {}, {}
        self.truncated, self.reached = False, set()
        self.sites = {}
        for symbol in snapshot.symbols.values():
            counts = defaultdict(int)
            for node in owned_nodes(symbol.node):
                counts[type(node).__name__] += 1
                self.sites[(symbol.id, id(node))] = f"{type(node).__name__}{counts[type(node).__name__]}"

    def node(self, symbol, kind, key, label, at=None, context=""):
        suffix = hashlib.sha256(context.encode()).hexdigest()[:12] if context else "root"
        identity = f"{symbol.id}::flow:{kind}:{key}:{suffix}"
        if identity not in self.nodes:
            if len(self.nodes) >= self.cap:
                self.truncated = True
                return None
            self.nodes[identity] = dict(id=identity, label=label, kind=kind, file=symbol.file,
                symbol=symbol.qualified_name, line=getattr(at, "lineno", symbol.start_line))
        return identity

    def symbol_node(self, symbol):
        return self.node(symbol, "symbol", "scope", symbol.qualified_name)

    def event(self, symbol, kind, at, label, context, extra=""):
        site = self.sites.get((symbol.id, id(at)), type(at).__name__)
        return self.node(symbol, kind, site + extra, label, at, context)

    def edge(self, sources, target, kind, symbol, at, expression, interpretation):
        if not target:
            return
        for source in sorted(sources - {None}):
            if source not in self.nodes:
                continue
            key = (source, target, kind, expression)
            self.edges[key] = dict(source=source, target=target, kind=kind, file=symbol.file,
                symbol=symbol.qualified_name, line=getattr(at, "lineno", symbol.start_line),
                expression=expression, interpretation=interpretation)
            if kind not in RELATION_KINDS:
                self.reached.add(symbol.id)

    def unknown(self, symbol, at, reason, expression=None):
        text = expression if expression is not None else ast.unparse(at)
        key = (symbol.id, getattr(at, "lineno", symbol.start_line), text, reason)
        self.unresolved[key] = dict(file=symbol.file, symbol=symbol.qualified_name,
            line=key[1], expression=text, reason=reason)

    def usable(self, symbol):
        if not isinstance(symbol.node, ast.FunctionDef):
            return False
        return not symbol.node.decorator_list and not any(
            isinstance(n, (ast.Yield, ast.YieldFrom)) for n in owned_nodes(symbol.node))

    def simple_class(self, symbol):
        if not isinstance(symbol.node, ast.ClassDef):
            return False
        if symbol.node.bases or symbol.node.keywords or symbol.node.decorator_list:
            return False
        forbidden = {"__new__", "__getattr__", "__getattribute__", "__setattr__"}
        if any(f"{symbol.id}.{name}" in self.snapshot.symbols for name in forbidden):
            return False
        # Instance method replacement in source defeats constructor-based lookup.
        methods = {n.name for n in symbol.node.body if isinstance(n, FUNCTIONS)}
        for unit in self.snapshot.units.values():
            if unit.tree and any(isinstance(n, ast.Attribute) and isinstance(n.ctx, (ast.Store, ast.Del))
                    and isinstance(n.value, ast.Name) and n.value.id == symbol.node.name and n.attr in methods
                    for n in ast.walk(unit.tree)):
                return False
        for candidate in self.snapshot.symbols.values():
            if candidate.id.startswith(symbol.id + ".") and isinstance(candidate.node, FUNCTIONS):
                args = [*candidate.node.args.posonlyargs, *candidate.node.args.args]
                receiver = args[0].arg if args else None
                if any(isinstance(n, ast.Attribute) and isinstance(n.ctx, (ast.Store, ast.Del))
                       and isinstance(n.value, ast.Name) and n.value.id == receiver and n.attr in methods
                       for n in owned_nodes(candidate.node)):
                    return False
        return True

    def valid_constructor(self, caller, call, cls):
        if not self.simple_class(cls):
            self.unknown(caller, call, "constructor receiver unknown: inheritance/decorator/custom lookup/member mutation")
            return False
        initializer = self.snapshot.symbols.get(cls.id + ".__init__")
        if initializer:
            if self.bind(caller, call, initializer, True) is None:
                return False
            if any(isinstance(n, ast.Return) and n.value is not None
                    and not (isinstance(n.value, ast.Constant) and n.value.value is None)
                    for n in owned_nodes(initializer.node)):
                self.unknown(caller, call, "constructor initializer may return a non-None value; receiver not established")
                return False
            for statement in initializer.node.body:
                if isinstance(statement, ast.Raise):
                    self.unknown(caller, call, "constructor initializer unconditionally raises before completion")
                    return False
                if isinstance(statement, ast.Return):
                    break
            return True
        if call.args or call.keywords:
            self.unknown(caller, call, "class has no initializer accepting supplied arguments")
            return False
        return True

    def resolve(self, symbol, call, types, invalid=()):
        if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.func.value.id in invalid:
            return None, "receiver identity escaped or member dispatch changed", False
        target, reason = self.resolver.resolve(symbol, call.func)
        bound = False
        if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
            name = call.func.value.id
            cls = self.resolver.receiver_class(symbol, name)
            if cls and target:
                bound = True
            elif name in types:
                cls = self.snapshot.symbols[types[name]]
                target = self.resolver.runtime_member(cls.id, call.func.attr)
                if target:
                    reason, bound = None, True
        return self.snapshot.symbols.get(target), reason, bound

    def bind(self, caller, call, callee, bound):
        if not self.usable(callee):
            self.unknown(caller, call, "async/generator/decorated callable: body return is not an ordinary call result")
            return None
        if any(isinstance(a, ast.Starred) for a in call.args) or any(k.arg is None for k in call.keywords):
            self.unknown(caller, call, "expanded arguments cannot be bound statically")
            return None
        args = callee.node.args
        if args.vararg or args.kwarg:
            self.unknown(caller, call, "variadic parameter binding is not supported")
            return None
        positional = [*args.posonlyargs, *args.args]
        assigned, mapping = set(), []
        offset = 1 if bound else 0
        if bound:
            if not positional:
                self.unknown(caller, call, "invalid bound method: no receiver parameter")
                return None
            assigned.add(positional[0].arg)
        if len(call.args) + offset > len(positional):
            self.unknown(caller, call, "invalid argument binding: too many positional arguments")
            return None
        for expression, parameter in zip(call.args, positional[offset:]):
            assigned.add(parameter.arg)
            mapping.append((expression, parameter.arg))
        allowed = {a.arg for a in [*args.args, *args.kwonlyargs]}
        for keyword in call.keywords:
            if keyword.arg not in allowed or keyword.arg in assigned:
                self.unknown(caller, call, "invalid argument binding: unknown/positional-only/duplicate keyword")
                return None
            assigned.add(keyword.arg)
            mapping.append((keyword.value, keyword.arg))
        required = {a.arg for a in positional[:len(positional) - len(args.defaults)]}
        required.update(a.arg for a, default in zip(args.kwonlyargs, args.kw_defaults) if default is None)
        if not required <= assigned:
            self.unknown(caller, call, "invalid argument binding: missing required parameter")
            return None
        return mapping

    def analyze(self, symbol, seeds=None, injections=None, root=False, depth=0, context="", active=()):
        if depth > self.depth or symbol.id in active:
            self.truncated = True
            self.unknown(symbol, symbol.node, "depth limit or recursive call cycle")
            return set()
        if symbol.kind in {"function", "async_function"} and not self.usable(symbol):
            self.unknown(symbol, symbol.node, "async/generator/decorated scope: value execution semantics unsupported")
            return set()
        environment, types = {}, {}
        for name, values in (seeds or {}).items():
            parameter = self.node(symbol, "parameter", name, f"매개변수 {name}", symbol.node, context)
            self.edge(values, parameter, "parameter_binding", symbol, symbol.node, name, "명시적으로 바인딩한 인자 값의 매개변수 후보")
            environment[name] = {parameter} if parameter else set()
        if root and isinstance(symbol.node, ast.FunctionDef):
            for parameter in [*symbol.node.args.posonlyargs, *symbol.node.args.args, *symbol.node.args.kwonlyargs]:
                point = self.node(symbol, "parameter", parameter.arg, f"매개변수 {parameter.arg}", parameter, context)
                self.edge({self.symbol_node(symbol)}, point, "scope_parameter", symbol, parameter, parameter.arg,
                          "변경 심볼의 입력 매개변수; 실제 호출값은 미확정")
                environment[parameter.arg] = {point} if point else set()
        interpreter = _Interpreter(self, symbol, environment, types, injections or {}, root, depth, context, (*active, symbol.id))
        return interpreter.block(symbol.node.body)

    def build(self):
        symbol = self.snapshot.symbols.get(self.root)
        if symbol is None:
            return self.result(False)
        self.symbol_node(symbol)
        relations = build_relations(self.snapshot)
        reverse = defaultdict(list)
        for edge in relations["edges"]:
            reverse[edge["callee"]].append(edge)
        queue, seen = deque([(symbol.id, 0)]), {symbol.id}
        # Relationship evidence remains separate from value-dependency edges.
        while queue and len(self.nodes) < self.cap:
            current, depth = queue.popleft()
            for edge in reverse[current]:
                caller = self.snapshot.symbols[edge["caller"]]
                callee = self.snapshot.symbols[current]
                if depth >= self.depth:
                    self.truncated = True
                    continue
                a, b = self.symbol_node(caller), self.symbol_node(callee)
                self.edge({a}, b, edge["kind"], caller, ast.Constant(lineno=edge["line"]), edge["expression"],
                          "정적 호출·참조 후보; 값 전달이나 실제 실행을 증명하지 않음")
                if caller.id not in seen:
                    seen.add(caller.id)
                    queue.append((caller.id, depth + 1))
        output = self.analyze(symbol, root=True)
        queue, seen = deque([(symbol.id, output, 0)]), {symbol.id}
        while queue and len(self.nodes) < self.cap:
            producer, values, depth = queue.popleft()
            if not values:
                continue
            callers = sorted({edge["caller"] for edge in reverse[producer] if edge["kind"] == "call"})
            for identity in callers:
                caller = self.snapshot.symbols[identity]
                if depth >= self.depth:
                    self.truncated = True
                    self.unknown(caller, caller.node, "caller value traversal reached depth limit")
                    continue
                injections = {producer: values}
                outputs = self.analyze(caller, injections=injections, depth=depth + 1,
                                       context=f"upstream:{producer}")
                if identity not in seen:
                    seen.add(identity)
                    queue.append((identity, outputs, depth + 1))
        if queue:
            self.truncated = True
        return self.result(True)

    def result(self, present):
        for error in self.snapshot.errors:
            key = (error.get("file", "?"), 1, "", "parse/read error")
            self.unresolved[key] = dict(file=key[0], symbol="<module>", line=1,
                                       expression="", reason=f"parse/read error: {error}")
        return dict(nodes=sorted(self.nodes.values(), key=lambda n: n["id"]),
                    edges=sorted(self.edges.values(), key=lambda e: (e["source"], e["target"], e["kind"], e["expression"])),
                    unresolved=sorted(self.unresolved.values(), key=lambda n: (n["file"], n["symbol"], n["line"], n["reason"])),
                    truncated=self.truncated, root_present=present, reached_scope_ids=sorted(self.reached))


class _Interpreter:
    def __init__(self, graph, symbol, environment, types, injections, root, depth, context, active):
        self.g, self.s, self.env, self.types = graph, symbol, environment, types
        self.injections, self.root, self.depth = injections, root, depth
        self.context, self.active, self.returns = context, active, set()
        self.invalid_receivers, self.receiver_names = set(), set()
        if isinstance(symbol.node, FUNCTIONS):
            positional = [*symbol.node.args.posonlyargs, *symbol.node.args.args]
            if positional and graph.resolver.receiver_class(symbol, positional[0].arg):
                self.receiver_names.add(positional[0].arg)

    def point(self, kind, node, label, extra=""):
        return self.g.event(self.s, kind, node, label, self.context, extra)

    def link(self, values, target, kind, node, text, explanation):
        self.g.edge(values, target, kind, self.s, node, text, explanation)
        return {target} if values and target else set()

    def unknown(self, node, reason):
        self.g.unknown(self.s, node, reason)

    def kill(self, node):
        def erase(name):
            self.env.pop(name, None)
            self.types.pop(name, None)
        def walk(child):
            if isinstance(child, DEFINITIONS):
                erase(child.name)
                return
            if isinstance(child, (ast.Lambda, *COMPREHENSIONS)):
                return
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                for alias in child.names:
                    if alias.name == "*":
                        self.env.clear()
                        self.types.clear()
                    else:
                        erase(alias.asname or (alias.name.split(".")[0] if isinstance(child, ast.Import) else alias.name))
            if isinstance(child, ast.ExceptHandler) and child.name:
                erase(child.name)
            if isinstance(child, ast.Attribute) and isinstance(child.ctx, (ast.Store, ast.Del)) and isinstance(child.value, ast.Name):
                if child.value.id in self.types or child.value.id in self.receiver_names:
                    self.invalid_receivers.add(child.value.id)
                self.types.pop(child.value.id, None)  # A skipped region can replace instance dispatch.
            if isinstance(child, (ast.MatchAs, ast.MatchStar)) and child.name:
                erase(child.name)
            if isinstance(child, ast.MatchMapping) and child.rest:
                erase(child.rest)
            if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
                erase(child.id)
            for item in ast.iter_child_nodes(child):
                walk(item)
        walk(node)

    def expression(self, node):
        if node is None or len(self.g.nodes) >= self.g.cap:
            if node is not None:
                self.g.truncated = True
            return set()
        if isinstance(node, ast.Name):
            if node.id in self.types or node.id in self.receiver_names:
                self.invalid_receivers.add(node.id)
                self.types.pop(node.id, None)
                self.unknown(node, "known receiver used as a value/alias/argument: heap identity may escape")
            return set(self.env.get(node.id, ()))
        if isinstance(node, ast.Constant):
            return set()
        if isinstance(node, (ast.Lambda, *COMPREHENSIONS, ast.Await, ast.Yield, ast.YieldFrom)):
            if isinstance(node, COMPREHENSIONS):
                for child in ast.walk(node):
                    if isinstance(child, ast.NamedExpr):
                        self.kill(child.target)  # Walrus targets may replace an enclosing binding.
            self.unknown(node, "nested/dynamic/lazy expression is a value-flow boundary")
            return set()
        if isinstance(node, ast.Call):
            return self.call(node)
        if isinstance(node, ast.NamedExpr):
            values = self.expression(node.value)
            self.assign(node.target, values, node)
            return values
        if isinstance(node, (ast.Attribute, ast.Subscript)):
            values = self.expression(node.value)
            if isinstance(node, ast.Subscript):
                values |= self.expression(node.slice)
            if values:
                point = self.point("access", node, ast.unparse(node))
                self.link(values, point, "access_input", node, ast.unparse(node), "속성/첨자 접근 입력 의존; 읽은 값의 출처는 미확정")
                self.unknown(node, "heap/attribute/subscript contents and aliases are not tracked")
            return set()
        if isinstance(node, (ast.BoolOp, ast.IfExp)):
            first = node.values[0] if isinstance(node, ast.BoolOp) else node.test
            values = self.expression(first)
            self.condition(first, values)
            self.kill(node)  # Conditional walrus assignments invalidate later binding assumptions.
            self.unknown(node, "short-circuit or conditional expression: conditional values not propagated")
            return set()
        values = set()
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr):
                values |= self.expression(child)
        if values:
            point = self.point("expression", node, ast.unparse(node))
            return self.link(values, point, "expression", node, ast.unparse(node), "명시 표현식의 값 의존 후보; 동일 값/타입을 보장하지 않음")
        return set()

    def call(self, node):
        callee, reason, bound = self.g.resolve(self.s, node, self.types, self.invalid_receivers)
        arguments = [(arg, self.expression(arg)) for arg in node.args]
        arguments += [(keyword.value, self.expression(keyword.value)) for keyword in node.keywords]
        affected = set().union(*(values for _, values in arguments)) if arguments else set()
        if callee and callee.kind == "class":
            if affected:
                self.unknown(node, "constructor/heap value flow is not supported")
            return set()
        mapping = self.g.bind(self.s, node, callee, bound) if callee else None
        if callee and mapping is None:
            return set()
        if not callee:
            if reason in {"builtin", "external or unavailable import"} and affected:
                boundary = self.point("external_call", node, ast.unparse(node.func))
                self.link(affected, boundary, "external_boundary", node, ast.unparse(node), "값이 외부/내장 호출 인자로 지정됨; 처리·저장·UI·네트워크 결과 미확정")
            elif affected or reason not in {"builtin", "external or unavailable import"}:
                self.unknown(node, reason or "dynamic or unknown callable")
            return set()
        if callee.id in self.injections:
            point = self.point("call_result", node, f"호출 결과 {ast.unparse(node.func)}")
            return self.link(self.injections[callee.id], point, "call_result", node, ast.unparse(node), "해당 함수의 명시 반환값을 이 호출 위치에서 받는 후보")
        if not affected:
            return set()
        evaluated = {id(expression): values for expression, values in arguments}
        seeds = {}
        for expression, name in mapping:
            values = evaluated[id(expression)]
            if values:
                argument = self.point("argument", expression, f"인자 → {name}", ":" + name)
                seeds[name] = self.link(values, argument, "value_argument", expression, ast.unparse(expression), "추적한 값을 명시 호출 인자로 전달하는 후보")
        child_context = self.context + "/" + self.s.id + ":" + self.g.sites[(self.s.id, id(node))]
        outputs = self.g.analyze(callee, seeds=seeds, depth=self.depth + 1, context=child_context, active=self.active)
        if outputs:
            point = self.point("call_result", node, f"호출 결과 {ast.unparse(node.func)}")
            return self.link(outputs, point, "call_result", node, ast.unparse(node), "명시 매개변수 의존 반환값의 호출 결과 후보")
        return set()

    def assign(self, target, values, node):
        if isinstance(target, ast.Name):
            self.env.pop(target.id, None)
            self.types.pop(target.id, None)
            self.invalid_receivers.discard(target.id)
            scope = self.g.resolver.scopes[self.s.id]
            if target.id in scope.globals or target.id in scope.nonlocals:
                if values:
                    self.unknown(node, "global/nonlocal assignment is a value-flow boundary")
                return
            if values:
                variable = self.point("variable", node, f"변수 {target.id}", ":" + target.id)
                self.env[target.id] = self.link(values, variable, "assignment", node, target.id, "현재 문장의 대입 값; 이후 재대입하면 이 연결을 제거")
        elif isinstance(target, (ast.Attribute, ast.Subscript)):
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and (target.value.id in self.types or target.value.id in self.receiver_names):
                receiver = self.g.resolver.receiver_class(self.s, target.value.id)
                cls = self.types.get(target.value.id) or (receiver.id if receiver else None)
                member = self.g.snapshot.symbols.get(self.g.resolver.runtime_member(cls, target.attr))
                if target.attr in {"__class__", "__dict__"} or member and member.kind in {"function", "async_function"}:
                    self.invalid_receivers.add(target.value.id)
                    self.types.pop(target.value.id, None)
            kind = "attribute_write" if isinstance(target, ast.Attribute) else "subscript_write"
            if values or self.root:
                point = self.point(kind, node, f"상태 쓰기 {ast.unparse(target)}")
                self.link(values or {self.g.symbol_node(self.s)}, point, kind, node, ast.unparse(node),
                          "소스에 명시된 속성/첨자 쓰기 후보; 대상 인스턴스·영속 저장·제품 기능 미확정")
            if isinstance(target, ast.Subscript):
                index_values = self.expression(target.slice)
                if index_values:
                    point = self.point(kind, node, f"상태 쓰기 {ast.unparse(target)}")
                    self.link(index_values, point, "state_write_index", node, ast.unparse(target.slice), "쓰기 위치의 첨자 의존 후보; 저장되는 값의 출처와 구분")
        else:
            self.kill(target)
            if values:
                self.unknown(node, "unpacking target cannot be matched to returned elements")

    def condition(self, node, values):
        if values:
            point = self.point("condition", node, ast.unparse(node))
            self.link(values, point, "condition", node, ast.unparse(node), "조건 표현식의 명시 값 의존 후보; 분기 선택/실행 결과 미확정")

    def block(self, statements):
        for node in statements:
            if len(self.g.nodes) >= self.g.cap:
                self.g.truncated = True
                break
            if isinstance(node, DEFINITIONS):
                self.env.pop(node.name, None)
                self.types.pop(node.name, None)
                continue
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                if isinstance(node, ast.AnnAssign) and value is None:
                    continue  # A bare annotation does not replace the current value.
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if len(targets) == 1 and isinstance(targets[0], (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)) and len(targets[0].elts) == len(value.elts):
                    evaluated = [self.expression(item) for item in value.elts]
                    for target, values in zip(targets[0].elts, evaluated):
                        self.assign(target, values, node)
                else:
                    values = self.expression(value)
                    if self.root and self.s.kind in {"module", "class"} and value is not None and not values:
                        values = {self.g.symbol_node(self.s)}
                    for target in targets:
                        self.assign(target, values, node)
                        if isinstance(target, ast.Name) and isinstance(value, ast.Call):
                            cls, _, _ = self.g.resolve(self.s, value, self.types, self.invalid_receivers)
                            if cls and self.g.valid_constructor(self.s, value, cls):
                                self.types[target.id] = cls.id
            elif isinstance(node, ast.AugAssign):
                values = self.expression(node.target) | self.expression(node.value)
                self.assign(node.target, values, node)
            elif isinstance(node, ast.Return):
                values = self.expression(node.value)
                if values or self.root:
                    point = self.point("return", node, "명시 반환값")
                    self.returns |= self.link(values or {self.g.symbol_node(self.s)}, point, "return", node,
                        ast.unparse(node), "이 반환 문장의 값 후보; 실제 실행/모든 경로의 반환을 보장하지 않음")
                break
            elif isinstance(node, ast.Raise):
                self.expression(node.exc)
                self.expression(node.cause)
                break
            elif isinstance(node, ast.Expr):
                self.expression(node.value)
            elif isinstance(node, ast.Assert):
                self.condition(node.test, self.expression(node.test))
            elif isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.TryStar, ast.With, ast.AsyncWith, ast.Match)):
                test = getattr(node, "test", None) or getattr(node, "iter", None)
                if test is not None:
                    self.condition(test, self.expression(test))
                self.unknown(node, "branch/loop/exception/context region not traversed; potentially reassigned bindings killed")
                self.kill(node)
            elif isinstance(node, ast.Delete):
                self.kill(node)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                self.kill(node)
            elif isinstance(node, (ast.Global, ast.Nonlocal)):
                for name in node.names:
                    self.env.pop(name, None)
                self.unknown(node, "global/nonlocal heap binding flow is not supported")
        return self.returns


def interpret_comparison(base_path, target_path, comparison, change_id, max_depth=10, max_nodes=160) -> dict:
    """Interpret one semantic change against the same verified source snapshots."""
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or not 1 <= max_depth <= 100:
        raise ValueError("max_depth는 1~100 사이 정수여야 합니다.")
    if isinstance(max_nodes, bool) or not isinstance(max_nodes, int) or not 2 <= max_nodes <= 2000:
        raise ValueError("max_nodes는 2~2000 사이 정수여야 합니다.")
    if not isinstance(comparison, dict) or comparison.get("mode") != "compare":
        raise ValueError("Python 코드 비교 보고서(mode=compare)가 필요합니다.")
    matches = [c for c in comparison.get("changes", []) if c.get("id") == change_id]
    if len(matches) != 1:
        raise ValueError("비교 보고서에서 변경 ID 하나를 선택하세요.")
    change = matches[0]
    base, _ = comparison_input(Path(base_path))
    target, _ = comparison_input(Path(target_path))
    if base.is_file() != target.is_file():
        raise ValueError("파일끼리 또는 폴더끼리 흐름을 비교하세요.")
    key = target.name if base.is_file() else None
    snapshots = {"base": load_snapshot(base, single_file_key=key), "target": load_snapshot(target, single_file_key=key)}
    root = f"{change['file']}::{change['symbol']}"
    versions, warnings = {}, []
    for side, snapshot in snapshots.items():
        symbol, expected = snapshot.symbols.get(root), change.get(side)
        if (expected is None) != (symbol is None) or symbol and expected.get("ast") != symbol.ast_dump:
            raise ValueError("변경 보고서와 현재 소스 스냅샷이 다릅니다. 코드 비교를 다시 실행하세요.")
        versions[side] = _Graph(snapshot, root, max_depth, max_nodes).build()
        warnings.extend(f"{side}: {warning}" for warning in snapshot.warnings)
        if snapshot.errors:
            warnings.append(f"{side}: 읽기/파싱 오류 {len(snapshot.errors)}개가 있어 흐름이 불완전합니다.")
        if versions[side]["truncated"]:
            warnings.append(f"{side}: 깊이/노드 제한 또는 재귀 때문에 일부 흐름이 생략됐습니다.")
    def connection_key(edge):
        return (edge["source"], edge["target"], edge["kind"], edge["expression"])
    before = {connection_key(e): e for e in versions["base"]["edges"]}
    after = {connection_key(e): e for e in versions["target"]["edges"]}
    connections = {"added": [after[k] for k in sorted(after.keys() - before.keys())],
                   "deleted": [before[k] for k in sorted(before.keys() - after.keys())],
                   "unchanged": [after[k] for k in sorted(before.keys() & after.keys())]}
    features = copy.deepcopy(change.get("features", []))
    for feature in features:
        feature["flow_evidence"] = [dict(side=e["side"], symbol_id=e["symbol_id"], relationship_evidence=True,
            value_flow_reached=e["symbol_id"] in versions[e["side"]]["reached_scope_ids"])
            for e in feature.get("evidence", []) if e.get("side") in versions and e.get("symbol_id")]
    return dict(mode="flow", schema_version=1, run_id=uuid.uuid4().hex, created_at=datetime.now(timezone.utc).isoformat(),
        change_id=change_id, root_symbol=dict(id=root, file=change["file"], symbol=change["symbol"], kind=change["kind"]),
        versions=versions, connection_changes=connections, features=features, warnings=list(dict.fromkeys(warnings)),
        limitations=["명시 AST 문장의 정적 값 의존 후보입니다. 실행 순서·도달 가능성·값·제품 동작·TC 결과를 확정하지 않습니다.",
            "분기·루프·예외/context 본문, 단락 평가, comprehension, async/generator/decorator, 동적 호출은 흐름 경계입니다.",
            "heap 읽기·별칭·전역/nonlocal 값·상속·확장 인자·variadic 바인딩은 추적하지 않습니다. 단순 클래스 생성의 지역 receiver만 후보로 해석합니다.",
            "호출·참조 관계와 값 전달 근거를 구분합니다. 기능·TC는 기존 매핑의 근거만 보존하며 임의 이름 추론이나 실행 검증을 하지 않습니다.",
            "연결 ID는 scope·문장 종류/순서·호출 문맥 기준입니다. 문장 추가/삭제로 연결 대응이 달라질 수 있습니다."],
        summary=dict(nodes=sum(len(g["nodes"]) for g in versions.values()), edges=sum(len(g["edges"]) for g in versions.values()),
            unresolved=sum(len(g["unresolved"]) for g in versions.values()), truncated=any(g["truncated"] for g in versions.values()),
            **{f"connections_{kind}": len(items) for kind, items in connections.items()}))

"""Value-flow candidates, hard boundaries and immutable-source integration."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import stat
import sys
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from artifact_conversion import convert_input
from code_comparison import build_comparison
from code_flow import interpret_comparison


PRODUCER = "def producer(level):\n    return level * 10\n\n"
SINK = "def consume(amount, state):\n    state.balance = amount\n    return amount\n\n"


class CodeFlowTests(unittest.TestCase):
    def setUp(self):
        self.work = ROOT / ".test_tmp" / ("flow_" + uuid4().hex)
        self.work.mkdir(parents=True)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        expected = self.work.absolute()
        if expected.resolve() != expected or expected.parent != (ROOT / ".test_tmp").resolve() or expected.is_symlink() or expected.is_junction():
            raise RuntimeError("Unsafe flow fixture cleanup")
        def readonly_retry(function, path, error):
            target = Path(path)
            if not target.resolve().is_relative_to(expected) or target.is_symlink() or target.is_junction():
                raise RuntimeError("Unsafe flow fixture permission change") from error
            target.chmod(target.stat().st_mode | stat.S_IWRITE)
            function(path)
        shutil.rmtree(expected, onexc=readonly_retry)

    def compare(self, before, after=None, single=False, features=False):
        tag = uuid4().hex
        roots = [self.work / (tag + "_base"), self.work / (tag + "_target")]
        for root, name, code in zip(roots, ("before.py" if single else "app.py", "after.py" if single else "app.py"),
                (before, after if after is not None else before.replace("level * 10", "level * 11"))):
            root.mkdir()
            (root / name).write_text(code, encoding="utf-8")
        manifests = [convert_input(root / name if single else root, output=self.work / (tag + f"_snapshot{i}"))
                     for i, root, name in zip(range(2), roots, ("before.py" if single else "app.py", "after.py" if single else "app.py"))]
        paths = [Path(m["output_path"]) for m in manifests]
        mapping = None
        if features:
            mapping = self.work / (tag + ".json")
            mapping.write_text(json.dumps({"features": [{"id": "REWARD", "name": "명시 매핑",
                "entry_points": [{"file": "app.py", "symbol": "entry"}], "tc_ids": ["TC-REWARD"]}]}), encoding="utf-8")
        report = build_comparison(*paths, features_path=mapping)
        change = next(c for c in report["changes"] if c["symbol"] == "producer")
        return paths, report, change

    def flow(self, source, after=None, **options):
        fixture_keys = {k: options.pop(k) for k in ("single", "features") if k in options}
        paths, report, change = self.compare(source, after, **fixture_keys)
        return interpret_comparison(*paths, report, change["id"], **options)

    def kinds(self, result, side="target"):
        return {e["kind"] for e in result["versions"][side]["edges"]}

    def test_return_assignment_argument_parameter_state_write_and_mapping(self):
        source = PRODUCER + SINK + "def entry(level, state):\n    reward = producer(level)\n    stored = consume(reward, state)\n    return stored\n"
        result = self.flow(source, features=True)
        self.assertTrue({"return", "call_result", "assignment", "value_argument", "parameter_binding", "attribute_write"} <= self.kinds(result))
        self.assertEqual(result["root_symbol"]["id"], "app.py::producer")
        self.assertTrue(any(e["kind"] == "attribute_write" and "state.balance" in e["expression"] for e in result["versions"]["target"]["edges"]))
        self.assertEqual(result["features"][0]["tc_ids"], ["TC-REWARD"])
        self.assertTrue(any(e["symbol_id"] == "app.py::entry" and e["value_flow_reached"] for e in result["features"][0]["flow_evidence"]))
        self.assertTrue(result["connection_changes"]["added"])
        self.assertTrue(result["connection_changes"]["deleted"])
        self.assertTrue(result["connection_changes"]["unchanged"])

    def test_keyword_argument_binding_and_subscript_write(self):
        source = PRODUCER + "def consume(state, *, amount):\n    state['balance'] = amount\n\ndef entry(level, state):\n    reward = producer(level)\n    consume(state, amount=reward)\n"
        result = self.flow(source)
        self.assertTrue({"value_argument", "parameter_binding", "subscript_write"} <= self.kinds(result))
        self.assertTrue(any(n["label"] == "매개변수 amount" for n in result["versions"]["target"]["nodes"]))

    def test_reassignment_kills_taint_in_caller_and_callee(self):
        for entry, sink in (("reward = producer(level)\n    reward = 0\n    consume(reward, state)", SINK),
                ("reward = producer(level)\n    consume(reward, state)", "def consume(amount, state):\n    amount = 0\n    state.balance = amount\n\n")):
            with self.subTest(entry=entry):
                result = self.flow(PRODUCER + sink + "def entry(level, state):\n    " + entry + "\n")
                self.assertNotIn("attribute_write", self.kinds(result))

    def test_callsite_parameter_environments_do_not_leak(self):
        source = PRODUCER + SINK + "def relay(amount):\n    return amount\n\ndef entry(level, state):\n    affected = relay(producer(level))\n    safe = relay(0)\n    consume(safe, state)\n"
        self.assertNotIn("attribute_write", self.kinds(self.flow(source)))

    def test_unknown_callback_does_not_become_named_function(self):
        source = PRODUCER + SINK + "def entry(level, state, callback):\n    reward = producer(level)\n    callback(reward)\n"
        result = self.flow(source)
        self.assertNotIn("attribute_write", self.kinds(result))
        self.assertTrue(any("callback" in n["expression"] for n in result["versions"]["target"]["unresolved"]))

    def test_conditional_rebinding_and_comprehension_are_boundaries(self):
        for code in ("reward = producer(level)\n    if flag:\n        reward = 0\n    consume(reward, state)",
                     "reward = producer(level)\n    values = [consume(reward, state) for reward in (0, 1)]"):
            with self.subTest(code=code):
                result = self.flow(PRODUCER + SINK + "def entry(level, state, flag):\n    " + code + "\n")
                self.assertNotIn("attribute_write", self.kinds(result))
                self.assertTrue(result["versions"]["target"]["unresolved"])

    def test_return_and_raise_stop_unreachable_state_write(self):
        for stop in ("return 0", "raise RuntimeError('stop')"):
            with self.subTest(stop=stop):
                source = PRODUCER + SINK + f"def entry(level, state):\n    reward = producer(level)\n    {stop}\n    consume(reward, state)\n"
                self.assertNotIn("attribute_write", self.kinds(self.flow(source)))

    def test_invalid_argument_binding_does_not_enter_body(self):
        for call in ("consume(reward, state, amount=0)", "consume(amount=reward)", "consume(reward, state, extra=1)", "consume(*[reward, state])"):
            with self.subTest(call=call):
                result = self.flow(PRODUCER + SINK + f"def entry(level, state):\n    reward = producer(level)\n    {call}\n")
                self.assertNotIn("attribute_write", self.kinds(result))
                self.assertTrue(result["versions"]["target"]["unresolved"])

    def test_import_and_definition_binding_replace_old_value(self):
        for replacement in ("import math as reward", "def reward():\n        return 0"):
            with self.subTest(replacement=replacement):
                source = PRODUCER + SINK + "def entry(level, state):\n    reward = producer(level)\n    " + replacement + "\n    consume(reward, state)\n"
                self.assertNotIn("attribute_write", self.kinds(self.flow(source)))

    def test_pattern_capture_and_conditional_walrus_invalidate_bindings(self):
        for replacement in ("match flag:\n        case reward:\n            pass",
                "values = [(reward := 0) for item in (1, 2)]", "flag and (reward := 0)"):
            with self.subTest(replacement=replacement):
                source = PRODUCER + SINK + "def entry(level, state, flag):\n    reward = producer(level)\n    " + replacement + "\n    consume(reward, state)\n"
                result = self.flow(source)
                self.assertNotIn("attribute_write", self.kinds(result))
                self.assertTrue(result["versions"]["target"]["unresolved"])

    def test_simple_constructor_receiver_candidate_and_invalid_constructor(self):
        for ctor, expected in (("Player()", True), ("Player(1)", False)):
            with self.subTest(ctor=ctor):
                source = PRODUCER + "class Player:\n    def receive(self, amount):\n        self.balance = amount\n\ndef entry(level):\n    player = " + ctor + "\n    reward = producer(level)\n    player.receive(reward)\n"
                self.assertEqual("attribute_write" in self.kinds(self.flow(source)), expected)

    def test_receiver_member_change_and_alias_escape_invalidate_constructor_evidence(self):
        for mutation in ("if flag:\n        player.receive = lambda amount: None",
                         "alias = player\n    alias.receive = lambda amount: None",
                         "player.__dict__ = {'receive': lambda amount: None}"):
            with self.subTest(mutation=mutation):
                source = PRODUCER + "class Player:\n    def receive(self, amount):\n        self.balance = amount\n\ndef entry(level, flag):\n    player = Player()\n    " + mutation + "\n    player.receive(producer(level))\n"
                result = self.flow(source)
                self.assertNotIn("attribute_write", self.kinds(result))
                self.assertTrue(result["versions"]["target"]["unresolved"])

    def test_constructor_non_none_return_and_unconditional_raise_do_not_establish_receiver(self):
        for initialization in ("return 1", "raise RuntimeError('stop')"):
            with self.subTest(initialization=initialization):
                source = PRODUCER + "class Player:\n    def __init__(self):\n        " + initialization + "\n    def receive(self, amount):\n        self.balance = amount\n\ndef entry(level):\n    player = Player()\n    player.receive(producer(level))\n"
                result = self.flow(source)
                self.assertNotIn("attribute_write", self.kinds(result))
                self.assertTrue(any("constructor" in u["reason"] for u in result["versions"]["target"]["unresolved"]))

    def test_implicit_method_receiver_alias_does_not_restore_static_member_binding(self):
        source = PRODUCER + "class Player:\n    def receive(self, amount):\n        self.balance = amount\n    def route(self, amount):\n        alias = self\n        alias.receive = lambda value: None\n        self.receive(amount)\n\ndef entry(level):\n    player = Player()\n    player.route(producer(level))\n"
        result = self.flow(source)
        self.assertNotIn("attribute_write", self.kinds(result))
        self.assertTrue(any("receiver identity" in u["reason"] for u in result["versions"]["target"]["unresolved"]))

    def test_async_generator_and_decorator_do_not_return_body_value_on_call(self):
        for producer in ("async def producer(level):\n    return level * 10\n\n", "def producer(level):\n    yield level * 10\n\n",
                         "@unknown\ndef producer(level):\n    return level * 10\n\n"):
            with self.subTest(producer=producer):
                result = self.flow(producer + SINK + "def entry(level, state):\n    consume(producer(level), state)\n")
                self.assertNotIn("attribute_write", self.kinds(result))
                self.assertTrue(result["versions"]["target"]["unresolved"])

    def test_deleted_root_preserves_base_graph_and_target_absence(self):
        before = PRODUCER + SINK + "def entry(level, state):\n    consume(producer(level), state)\n"
        after = SINK + "def entry(level, state):\n    consume(0, state)\n"
        result = self.flow(before, after)
        self.assertTrue(result["versions"]["base"]["root_present"])
        self.assertFalse(result["versions"]["target"]["root_present"])
        self.assertEqual(result["versions"]["target"]["nodes"], [])
        self.assertTrue(result["connection_changes"]["deleted"])

    def test_single_file_normalization_and_source_never_executed(self):
        sentinel = self.work / "executed"
        source = PRODUCER + SINK + "def entry(level, state):\n    consume(producer(level), state)\n" + f"\nfrom pathlib import Path\nPath({str(sentinel)!r}).write_text('executed')\n"
        result = self.flow(source, single=True)
        self.assertEqual(result["root_symbol"]["file"], "after.py")
        self.assertFalse(sentinel.exists())

    def test_depth_node_caps_cycles_and_report_source_mismatch(self):
        source = PRODUCER + SINK + "def entry(level, state):\n    consume(producer(level), state)\n"
        result = self.flow(source, max_depth=1, max_nodes=8)
        self.assertTrue(result["summary"]["truncated"])
        self.assertTrue(all(len(g["nodes"]) <= 8 for g in result["versions"].values()))
        recursive = "def producer(level):\n    return producer(level * 10)\n"
        self.assertTrue(self.flow(recursive)["summary"]["truncated"])
        paths, report, change = self.compare(source)
        report["changes"][0]["target"]["ast"] = "wrong source"
        with self.assertRaises(ValueError):
            interpret_comparison(*paths, report, change["id"])


if __name__ == "__main__":
    unittest.main()

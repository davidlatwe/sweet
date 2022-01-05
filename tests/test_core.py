
from rez.packages import Variant
from sweet.core import SuiteOp, Storage
from sweet.constants import (
    TOOL_VALID,
    TOOL_HIDDEN,
    TOOL_SHADOWED,
    TOOL_MISSING,
)
from sweet import signals
from .util import TestBase, MemPkgRepo


class TestCore(TestBase):

    def __init__(self, *args, **kwargs):
        super(TestCore, self).__init__(*args, **kwargs)
        self.repo = MemPkgRepo("memory@any")

    def setUp(self):
        self.settings = {
            "packages_path": [self.repo.path],
        }
        super(TestCore, self).setUp()

    def tearDown(self):
        self.repo.flush()
        super(TestCore, self).tearDown()

    def test_empty_suite_dict(self):
        sop = SuiteOp()
        s_dict = sop.dump()

        expected = {
            "contexts": {},
            "description": "",
            "live_resolve": True,
            "tools": {},
            "requests": {},
        }
        self.assertEqual(s_dict, expected)

    def test_add_context(self):
        self.repo.add("foo")

        sop = SuiteOp()
        ctx = sop.add_context("foo", ["foo"])
        self.assertEqual("foo", ctx.name)

        s_dict = sop.dump()
        self.assertIn("foo", s_dict["contexts"])

    def test_update_tool_1(self):
        self.repo.add("foo", tools=["food"])
        self.repo.add("bar", tools=["beer"])

        sop = SuiteOp()
        foo = sop.add_context("foo", ["foo"])
        bar = sop.add_context("bar", ["bar", "foo"])

        beer, food_1, food_2 = sop.iter_tools()
        self.assertEqual("beer", beer.name)
        self.assertEqual(bar.name, beer.ctx_name)
        self.assertEqual(TOOL_VALID, beer.status)
        self.assertEqual("food", food_1.name)
        self.assertEqual(bar.name, food_1.ctx_name)
        self.assertEqual(TOOL_VALID, food_1.status)
        self.assertEqual("food", food_2.name)
        self.assertEqual("food", food_2.alias)
        self.assertEqual(foo.name, food_2.ctx_name)
        self.assertEqual(TOOL_SHADOWED, food_2.status)

        sop.update_context(foo.name, tool_name="food", new_alias="fruit")
        food_2 = next(t for t in sop.iter_tools(foo.name) if t.name == "food")

        self.assertEqual("food", food_2.name)
        self.assertEqual("fruit", food_2.alias)
        self.assertEqual(foo.name, food_2.ctx_name)
        self.assertEqual(TOOL_VALID, food_2.status)

    def test_update_tool_2(self):
        """Test updating context with tool alias/hidden preserved"""
        self.repo.add("foo", tools=["food", "fuzz"])
        self.repo.add("bar", tools=["beer"])

        sop = SuiteOp()
        foo = sop.add_context("foo", ["foo"])

        food, fuzz = sop.iter_tools()
        self.assertEqual("food", food.name)

        sop.update_context(foo.name, tool_name=food.name, new_alias="fruit")
        sop.update_context(foo.name, tool_name=fuzz.name, set_hidden=True)
        food, fuzz = sop.iter_tools()

        self.assertEqual("fruit", food.alias)
        self.assertEqual(TOOL_HIDDEN, fuzz.status)

        sop.update_context(foo.name, requests=["foo", "bar"])

        food, beer, fuzz = sop.iter_tools()
        self.assertEqual("fruit", food.alias)
        self.assertEqual("beer", beer.alias)
        self.assertEqual(TOOL_HIDDEN, fuzz.status)

    def test_iterating_contexts(self):
        """Test contexts iterated by priority"""
        self.repo.add("bee", tools=["honey"])

        sop = SuiteOp()
        sop.add_context("a", ["bee"])
        sop.add_context("b", ["bee"])
        sop.add_context("c", ["bee"])

        c, b, a = list(sop.iter_contexts())
        self.assertEqual("a", a.name)
        self.assertEqual("b", b.name)
        self.assertEqual("c", c.name)

        a, b, c = list(sop.iter_contexts(ascending=True))
        self.assertEqual("a", a.name)
        self.assertEqual("b", b.name)
        self.assertEqual("c", c.name)

        honey = next(t for t in sop.iter_tools() if not t.status)
        self.assertEqual(c.name, honey.ctx_name)

    def test_context_reordering(self):
        """Test entire suite contexts can be reordered as expected"""
        sop = SuiteOp()
        sop.add_context("a", [])
        sop.add_context("b", [])
        sop.add_context("c", [])

        c, b, a = list(sop.iter_contexts())
        self.assertEqual("a", a.name)
        self.assertEqual("b", b.name)
        self.assertEqual("c", c.name)

        sop.reorder_contexts(["b", "a", "c"])

        b, a, c = list(sop.iter_contexts())
        self.assertEqual("a", a.name)
        self.assertEqual("b", b.name)
        self.assertEqual("c", c.name)

        sop.add_context("d", [])

        d, b, a, c = list(sop.iter_contexts())
        self.assertEqual("a", a.name)
        self.assertEqual("b", b.name)
        self.assertEqual("c", c.name)
        self.assertEqual("d", d.name)

    def test_tool_by_multi_packages(self):
        """Test tool that provided by more than one package"""
        self.repo.add("foo", tools=["fruit"])
        self.repo.add("bee", tools=["honey"])
        self.repo.add("bez", tools=["honey"])

        sop = SuiteOp()
        sop.add_context("B", ["bee", "bez"])
        sop.add_context("F", ["foo"])

        fruit, honey = sop.iter_tools()
        self.assertTrue(type(fruit.variant) is Variant)
        self.assertTrue(type(honey.variant) is set)
        self.assertTrue(type(honey.variant.pop()) is Variant)

    def test_suite_storage(self):
        tempdir = self.make_tempdir()
        storage = Storage(roots={"test": tempdir})

        self.repo.add("foo", tools=["fruit"])
        sop = SuiteOp()
        sop.add_context("FOO", ["foo"])

        path = storage.suite_path("test", "my-foo")
        sop.save(path)

        saved = next(storage.iter_saved_suites())
        self.assertEqual("test", saved.branch)
        self.assertEqual("my-foo", saved.name)

    def test_signals(self):
        self.repo.add("foo", tools=["fruit"])

        sop = SuiteOp()
        with self.wait_signals([signals.tool_flushed]):
            sop.add_context("FOO", ["foo"])

        with self.wait_signals([signals.tool_flushed,
                                signals.tool_updated]):
            sop.refresh()

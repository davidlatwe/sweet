
import os
from rez.packages import Variant
from sweet.core import SuiteOp, Storage, RollingContext, Constants
from sweet.exceptions import SuiteOpError, ResolvedContextError
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
        }
        self.assertEqual(s_dict, expected)

    def test_add_context(self):
        self.repo.add("foo")

        sop = SuiteOp()
        ctx = sop.add_context("foo", sop.resolve_context(["foo"]))
        self.assertEqual("foo", ctx.name)

        s_dict = sop.dump()
        self.assertIn("foo", s_dict["contexts"])

    def test_rename_context(self):
        sop = SuiteOp()
        sop.add_context("foo", sop.resolve_context([]))
        sop.update_context("foo", new_name="bar")

        ctx = next(sop.iter_contexts())
        self.assertEqual("bar", ctx.name)

    def test_update_tool_1(self):
        self.repo.add("foo", tools=["food"])
        self.repo.add("bar", tools=["beer"])

        sop = SuiteOp()
        foo = sop.add_context("foo", sop.resolve_context(["foo"]))
        bar = sop.add_context("bar", sop.resolve_context(["bar", "foo"]))

        beer, food_1, food_2 = sop.iter_tools()
        self.assertEqual("beer", beer.name)
        self.assertEqual(bar.name, beer.ctx_name)
        self.assertEqual(Constants.TOOL_VALID, beer.status)
        self.assertEqual("food", food_1.name)
        self.assertEqual(bar.name, food_1.ctx_name)
        self.assertEqual(Constants.TOOL_VALID, food_1.status)
        self.assertEqual("food", food_2.name)
        self.assertEqual("food", food_2.alias)
        self.assertEqual(foo.name, food_2.ctx_name)
        self.assertEqual(Constants.TOOL_SHADOWED, food_2.status)

        sop.update_context(foo.name, tool_name="food", new_alias="fruit")
        food_2 = next(t for t in sop.iter_tools(foo.name) if t.name == "food")

        self.assertEqual("food", food_2.name)
        self.assertEqual("fruit", food_2.alias)
        self.assertEqual(foo.name, food_2.ctx_name)
        self.assertEqual(Constants.TOOL_VALID, food_2.status)

    def test_update_tool_2(self):
        """Test updating context with tool alias/hidden preserved"""
        self.repo.add("foo", tools=["food", "fuzz"])
        self.repo.add("bar", tools=["beer"])

        sop = SuiteOp()
        foo = sop.add_context("foo", sop.resolve_context(["foo"]))

        food, fuzz = sop.iter_tools()
        self.assertEqual("food", food.name)

        sop.update_context(foo.name, tool_name=food.name, new_alias="fruit")
        sop.update_context(foo.name, tool_name=fuzz.name, set_hidden=True)
        food, fuzz = sop.iter_tools()

        self.assertEqual("fruit", food.alias)
        self.assertEqual(Constants.TOOL_HIDDEN, fuzz.status)

        _context = sop.resolve_context(["foo", "bar"])
        sop.update_context(foo.name, context=_context)

        food, beer, fuzz = sop.iter_tools()
        self.assertEqual("fruit", food.alias)
        self.assertEqual("beer", beer.alias)
        self.assertEqual(Constants.TOOL_HIDDEN, fuzz.status)

    def test_iterating_contexts(self):
        """Test contexts iterated by priority"""
        self.repo.add("bee", tools=["honey"])

        sop = SuiteOp()
        sop.add_context("a", sop.resolve_context(["bee"]))
        sop.add_context("b", sop.resolve_context(["bee"]))
        sop.add_context("c", sop.resolve_context(["bee"]))

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
        sop.add_context("a", sop.resolve_context([]))
        sop.add_context("b", sop.resolve_context([]))
        sop.add_context("c", sop.resolve_context([]))

        c, b, a = list(sop.iter_contexts())
        self.assertEqual("a", a.name)
        self.assertEqual("b", b.name)
        self.assertEqual("c", c.name)

        sop.reorder_contexts(["b", "a", "c"])

        b, a, c = list(sop.iter_contexts())
        self.assertEqual("a", a.name)
        self.assertEqual("b", b.name)
        self.assertEqual("c", c.name)

        sop.add_context("d", sop.resolve_context([]))

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
        sop.add_context("B", sop.resolve_context(["bee", "bez"]))
        sop.add_context("F", sop.resolve_context(["foo"]))

        fruit, honey_bee, honey_bez = sop.iter_tools()

        self.assertTrue(isinstance(fruit.variant, Variant))
        self.assertTrue(fruit.ambiguous is False)
        self.assertTrue(isinstance(honey_bee.variant, Variant))
        self.assertTrue(honey_bee.ambiguous is True)
        self.assertTrue(isinstance(honey_bez.variant, Variant))
        self.assertTrue(honey_bez.ambiguous is True)

    def test_suite_storage(self):
        tempdir = self.make_tempdir()
        storage = Storage(roots={"test": tempdir})

        self.repo.add("foo", tools=["fruit"])
        sop = SuiteOp()
        sop.add_context("FOO", sop.resolve_context(["foo"]))

        path = storage.suite_path("test", "my-foo")
        sop.save(path)

        saved = next(storage.iter_saved_suites())
        self.assertEqual("test", saved.branch)
        self.assertEqual("my-foo", saved.name)

    def test_failed_context_loaded_1(self):
        broken = RollingContext(["bad_rxt_loaded"])
        sop = SuiteOp()
        sop.add_context("BAD", sop.resolve_context([]))
        sop._suite.contexts["BAD"]["context"] = broken  # force it for testing

        self.assertRaises(ResolvedContextError, list, sop.iter_tools())
        tools = list(sop.iter_tools())  # should not raise any error afterward
        self.assertEqual(0, len(tools))

        tempdir = self.make_tempdir()
        storage = Storage(roots={"test": tempdir})

        path = storage.suite_path("test", "my-bad")
        self.assertRaises(SuiteOpError, sop.save, path)

    def test_failed_context_loaded_2(self):
        tempdir = self.make_tempdir()
        storage = Storage(roots={"test": tempdir})

        self.repo.add("foo", tools=["fruit"])
        sop = SuiteOp()
        sop.add_context("FOO", sop.resolve_context(["foo"]))

        path = storage.suite_path("test", "my-foo")
        sop.save(path)

        rxt = sop._suite._context_path("FOO", path)
        os.remove(rxt)

        sop.load(path)
        ctx = next(sop.iter_contexts())
        self.assertFalse(ctx.context.success)

    def test_tool_missing_in_edit(self):
        tempdir = self.make_tempdir()
        storage = Storage(roots={"test": tempdir})

        self.repo.add("foo", version=1, tools=["fruit"])

        sop = SuiteOp()
        sop.add_context("FOO", sop.resolve_context(["foo"]))

        path = storage.suite_path("test", "my-foo")
        sop.save(path)

        sop.load(path)
        sop.drop_context("FOO")
        tool = next(sop.iter_tools())
        self.assertEqual(Constants.TOOL_MISSING, tool.status)

    def test_tool_missing_on_pkg_update(self):
        tempdir = self.make_tempdir()
        storage = Storage(roots={"test": tempdir})

        self.repo.add("foo", version=1, tools=["fruit"])

        sop = SuiteOp()
        sop.add_context("FOO", sop.resolve_context(["foo"]))

        path = storage.suite_path("test", "my-foo")
        sop.save(path)

        # tool removed in version 2
        self.repo.add("foo", version=2, tools=[])

        sop.load(path)
        tool = next(sop.iter_tools())

        self.assertEqual("1", str(tool.variant.version))
        self.assertEqual(Constants.TOOL_MISSING, tool.status)

        # add back tool in version 3
        self.repo.add("foo", version=3, tools=["fruit"])

        sop.load(path)
        tool = next(sop.iter_tools())

        self.assertEqual("3", str(tool.variant.version))
        self.assertEqual(Constants.TOOL_VALID, tool.status)

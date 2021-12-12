
from .util import TestBase, MemPkgRepo
from rez.packages import Variant
from sweet.core import SuiteOp, Constants


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
        s_dict = sop.to_dict()

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
        ctx = sop.add_context("foo", requests=["foo"])
        self.assertEqual("foo", ctx.name)

        s_dict = sop.to_dict()
        self.assertIn("foo", s_dict["contexts"])

    def test_update_tool_1(self):
        self.repo.add("foo", tools=["food"])
        self.repo.add("bar", tools=["beer"])

        sop = SuiteOp()
        foo = sop.add_context("foo", requests=["foo"])
        bar = sop.add_context("bar", requests=["bar", "foo"])

        beer, food_1, food_2 = list(sop.iter_tools())
        self.assertEqual("beer", beer.name)
        self.assertEqual(bar.name, beer.ctx_name)
        self.assertEqual(Constants.st_valid, beer.invalid)
        self.assertEqual("food", food_1.name)
        self.assertEqual(bar.name, food_1.ctx_name)
        self.assertEqual(Constants.st_valid, food_1.invalid)
        self.assertEqual("food", food_2.name)
        self.assertEqual("food", food_2.alias)
        self.assertEqual(foo.name, food_2.ctx_name)
        self.assertEqual(Constants.st_shadowed, food_2.invalid)

        sop.update_tool(foo.name, "food", new_alias="fruit")

        beer, food_1, food_2 = list(sop.iter_tools())
        self.assertEqual("food", food_2.name)
        self.assertEqual("fruit", food_2.alias)
        self.assertEqual(foo.name, food_2.ctx_name)
        self.assertEqual(Constants.st_valid, food_2.invalid)

    def test_update_tool_2(self):
        """Test updating context with tool alias/hidden preserved"""
        self.repo.add("foo", tools=["food", "fuzz"])
        self.repo.add("bar", tools=["beer"])

        sop = SuiteOp()
        foo = sop.add_context("foo", requests=["foo"])

        food, fuzz = list(sop.iter_tools())
        self.assertEqual("food", food.name)

        sop.update_tool(foo.name, food.name, new_alias="fruit")
        sop.update_tool(foo.name, fuzz.name, set_hidden=True)

        food, fuzz = list(sop.iter_tools())
        self.assertEqual("fruit", food.alias)
        self.assertEqual(Constants.st_hidden, fuzz.invalid)

        sop.update_context(foo.name, requests=["foo", "bar"])

        food, beer, fuzz = list(sop.iter_tools())
        self.assertEqual("fruit", food.alias)
        self.assertEqual("beer", beer.alias)
        self.assertEqual(Constants.st_hidden, fuzz.invalid)

    def test_iterating_contexts(self):
        """Test contexts iterated by priority"""
        self.repo.add("bee", tools=["honey"])

        sop = SuiteOp()
        sop.add_context("a", requests=["bee"])
        sop.add_context("b", requests=["bee"])
        sop.add_context("c", requests=["bee"])

        c, b, a = list(sop.iter_contexts())
        self.assertEqual("a", a.name)
        self.assertEqual("b", b.name)
        self.assertEqual("c", c.name)

        a, b, c = list(sop.iter_contexts(ascending=True))
        self.assertEqual("a", a.name)
        self.assertEqual("b", b.name)
        self.assertEqual("c", c.name)

        honey = next(t for t in sop.iter_tools() if not t.invalid)
        self.assertEqual(c.name, honey.ctx_name)

    def test_tool_by_multi_packages(self):
        """Test tool that provided by more than one package"""
        self.repo.add("foo", tools=["fruit"])
        self.repo.add("bee", tools=["honey"])
        self.repo.add("bez", tools=["honey"])

        sop = SuiteOp()
        sop.add_context("B", requests=["bee", "bez"])
        sop.add_context("F", requests=["foo"])

        fruit, honey = list(sop.iter_tools())
        self.assertTrue(type(fruit.variant) is Variant)
        self.assertTrue(type(honey.variant) is set)
        self.assertTrue(type(honey.variant.pop()) is Variant)

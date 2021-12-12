
from .util import TestBase, MemPkgRepo
from rez.packages import Variant
from sweet.core import SuiteOp


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
        self.assertEqual("foo", sop.lookup_context(ctx.ctx_id))

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
        self.assertFalse(beer.shadowed)
        self.assertEqual("food", food_1.name)
        self.assertEqual(bar.name, food_1.ctx_name)
        self.assertFalse(food_1.shadowed)
        self.assertEqual("food", food_2.name)
        self.assertEqual("food", food_2.alias)
        self.assertEqual(foo.name, food_2.ctx_name)
        self.assertTrue(food_2.shadowed)

        sop.update_tool(foo.ctx_id, "food", new_alias="fruit")

        beer, food_1, food_2 = list(sop.iter_tools())
        self.assertEqual("food", food_2.name)
        self.assertEqual("fruit", food_2.alias)
        self.assertEqual(foo.name, food_2.ctx_name)
        self.assertFalse(food_2.shadowed)

    def test_update_tool_2(self):
        """Test updating context with tool alias/hidden preserved"""
        self.repo.add("foo", tools=["food", "fuzz"])
        self.repo.add("bar", tools=["beer"])

        sop = SuiteOp()
        foo = sop.add_context("foo", requests=["foo"])

        food, fuzz = list(sop.iter_tools())
        self.assertEqual("food", food.name)

        sop.update_tool(foo.ctx_id, food.name, new_alias="fruit")
        sop.update_tool(foo.ctx_id, fuzz.name, set_hidden=True)

        food, fuzz = list(sop.iter_tools())
        self.assertEqual("fruit", food.alias)
        self.assertTrue(fuzz.hidden)

        sop.update_context(foo.ctx_id, requests=["foo", "bar"])

        food, beer, fuzz = list(sop.iter_tools())
        self.assertEqual("fruit", food.alias)
        self.assertEqual("beer", beer.alias)
        self.assertTrue(fuzz.hidden)

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

        honey = next(t for t in sop.iter_tools() if not t.shadowed)
        self.assertEqual(c.ctx_id, honey.ctx_id)

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

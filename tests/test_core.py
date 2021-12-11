
from .util import TestBase, MemPkgRepo
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
        self.assertEqual(foo.name, food_2.ctx_name)
        self.assertTrue(food_2.shadowed)
        self.assertFalse(food_2.aliased)

        sop.update_tool(foo.ctx_id, "food", new_alias="fruit")

        beer, food_1, food_2 = list(sop.iter_tools())
        self.assertEqual("fruit", food_2.name)
        self.assertTrue(food_2.aliased)
        self.assertEqual(foo.name, food_2.ctx_name)
        self.assertFalse(food_2.shadowed)

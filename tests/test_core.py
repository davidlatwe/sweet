
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
        ctx_id = sop.add_context("foo", requests=["foo"])
        self.assertEqual("foo", sop.lookup_context(ctx_id))

        c_name = sop.read_context(ctx_id, "name")
        self.assertEqual(ctx_id, c_name)

        s_dict = sop.to_dict()
        self.assertIn("foo", s_dict["contexts"])

    def test_update_tool_1(self):
        self.repo.add("foo", tools=["food"])
        self.repo.add("bar", tools=["beer"])

        sop = SuiteOp()
        foo_id = sop.add_context("foo", requests=["foo"])
        bar_id = sop.add_context("bar", requests=["bar", "foo"])

        beer, food_1, food_2 = list(sop.iter_tools())
        self.assertEqual("beer", beer.alias)
        self.assertEqual(bar_id, beer.ctx_id)
        self.assertFalse(beer.shadowed)
        self.assertEqual("food", food_1.alias)
        self.assertEqual(bar_id, food_1.ctx_id)
        self.assertFalse(food_1.shadowed)
        self.assertEqual("food", food_2.alias)
        self.assertEqual(foo_id, food_2.ctx_id)
        self.assertTrue(food_2.shadowed)

        sop.update_tool(foo_id, "food", new_alias="fruit")

        beer, food_1, food_2 = list(sop.iter_tools())
        self.assertEqual("fruit", food_2.alias)
        self.assertEqual(foo_id, food_2.ctx_id)
        self.assertFalse(food_2.shadowed)

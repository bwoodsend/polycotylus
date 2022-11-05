import unittest

import bare_minimum


class TestBareMinimum(unittest.TestCase):

    def test_add_1(self):
        self.assertEqual(bare_minimum.add_1(1), 2)

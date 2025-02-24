import unittest

import os, inspect, sys
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
if __name__ == '__main__':
    print(parent_dir)
    sys.path.insert(0, os.path.join(parent_dir, 'src'))

from pydocmaker.util import flatten_list, txtcolor, bcolors


class TestTxtColor(unittest.TestCase):

    def test_valid_color(self):
        result = txtcolor("test", "red")
        self.assertEqual(result, f"{bcolors.FAIL.value}test{bcolors.ENDC.value}")

    def test_invalid_color(self):
        result = txtcolor("test", "invalid_color")
        self.assertEqual(result, "test")

    def test_empty_string(self):
        result = txtcolor("", "red")
        self.assertEqual(result, f"{bcolors.FAIL.value}{bcolors.ENDC.value}")

class TestFlattenList(unittest.TestCase):
    def test_flatten_list(self):
        self.assertEqual(flatten_list([1, 2, [3, 4], [5, [6, 7]]]), [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(flatten_list([1, 2, 3, 4, 5]), [1, 2, 3, 4, 5])
        self.assertEqual(flatten_list([[1], [2], [3], [4], [5]]), [1, 2, 3, 4, 5])
        self.assertEqual(flatten_list([]), [])

if __name__ == '__main__':
    unittest.main()
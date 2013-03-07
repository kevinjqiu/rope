import unittest

from ropetest import testutils
from rope.refactor.wrap_line import WrapLine


class WrapLineTest(unittest.TestCase):
    def setUp(self):
        super(WrapLineTest, self).setUp()
        self.project = testutils.sample_project()
        self.pycore = self.project.pycore

    def tearDown(self):
        testutils.remove_project(self.project)
        super(WrapLineTest, self).tearDown()

    def _assert_wrap_import_lines(self, original, expected, max_width=40):
        testmod = testutils.create_module(self.project, 'testmod')
        testmod.write(original)
        changes = WrapLine(self.project, testmod).get_changes(max_width)
        self.project.do(changes)
        result = testmod.read()
        self.assertEquals(expected, result)

    def test_from_imports_token_too_long(self):
        self._assert_wrap_import_lines(
            'from testmod import thisisaverylongtokensolongthatitdoesntfitinoneline',
            'from testmod import thisisaverylongtokensolongthatitdoesntfitinoneline',
        )

    def test_from_imports_token_and_indentation_exceeds_max_width(self):
        self._assert_wrap_import_lines(
            'from testmod import foo, baaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
            'from testmod import foo, baaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        )

    def test_from_imports_boundary(self):
        self._assert_wrap_import_lines(
            'from testmod import foo, bar, quux, foo1',
            'from testmod import foo, bar, quux, foo1',
        )

    def test_from_imports(self):
        self._assert_wrap_import_lines(
            'from testmod import foo, bar, quux, foo1, bar1, quux\n'
            'def main(): pass',
            'from testmod import (\n'
            '    foo, bar, quux, foo1, bar1, quux)\n'
            'def main(): pass',
        )

    def test_from_imports_with_alias(self):
        self._assert_wrap_import_lines(
            'from testmod import foo as foo1, bar, quux, foo2, bar1, quux\n'
            'def main(): pass',
            'from testmod import (\n'
            '    foo as foo1, bar, quux, foo2,\n'
            '    bar1, quux)\n'
            'def main(): pass',
        )


def suite():
    result = unittest.TestSuite()
    result.addTests(unittest.makeSuite(WrapLineTest))
    return result


if __name__ == '__main__':
    unittest.main()

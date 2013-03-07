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

    def test_from_imports(self):
        testmod = testutils.create_module(self.project, 'testmod')
        testmod.write(
            'from testmod import foo, bar, quux, foo1, bar1, quux\n'
            'def main(): pass'
        )
        changes = WrapLine(self.project, testmod).get_changes(40)
        self.project.do(changes)
        result = testmod.read()
        self.assertEquals(
            'from testmod import (\n'
            '    foo, bar, quux, foo1, bar1, quux)\n'
            'def main(): pass',
            result)

    def test_from_imports_with_alias(self):
        testmod = testutils.create_module(self.project, 'testmod')
        testmod.write(
            'from testmod import foo as foo1, bar, quux, foo2, bar1, quux\n'
            'def main(): pass'
        )
        changes = WrapLine(self.project, testmod).get_changes(40)
        self.project.do(changes)
        result = testmod.read()
        self.assertEquals(
            'from testmod import (\n'
            '    foo as foo1, bar, quux, foo2,\n'
            '    bar1, quux)\n'
            'def main(): pass',
            result)


def suite():
    result = unittest.TestSuite()
    result.addTests(unittest.makeSuite(WrapLineTest))
    return result


if __name__ == '__main__':
    unittest.main()

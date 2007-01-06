import unittest

from ropetest import testutils
from rope.base.codeanalyze import (StatementRangeFinder, ArrayLinesAdapter,
                                   SourceLinesAdapter, WordRangeFinder,
                                   ScopeNameFinder, LogicalLineFinder)
from rope.base.project import Project


class StatementRangeFinderTest(unittest.TestCase):

    def setUp(self):
        super(StatementRangeFinderTest, self).setUp()

    def tearDown(self):
        super(StatementRangeFinderTest, self).tearDown()

    def get_range_finder(self, code, line):
        result = StatementRangeFinder(ArrayLinesAdapter(code.split('\n')), line)
        result.analyze()
        return result

    def test_simple_statement_finding(self):
        finder = self.get_range_finder('a = 10', 1)
        self.assertEquals(1,  finder.get_statement_start())

    def test_get_start(self):
        finder = self.get_range_finder('a = 10\nb = 12\nc = 14', 1)
        self.assertEquals(1,  finder.get_statement_start())

    def test_get_block_end(self):
        finder = self.get_range_finder('a = 10\nb = 12\nc = 14', 1)
        self.assertEquals(3,  finder.get_block_end())

    def test_get_last_open_parens(self):
        finder = self.get_range_finder('a = 10', 1)
        self.assertTrue(finder.last_open_parens() is None)

    def test_get_last_open_parens2(self):
        finder = self.get_range_finder('a = (10 +', 1)
        self.assertEquals((1, 4), finder.last_open_parens())

    def test_is_line_continued(self):
        finder = self.get_range_finder('a = 10', 1)
        self.assertFalse(finder.is_line_continued())

    def test_is_line_continued2(self):
        finder = self.get_range_finder('a = (10 +', 1)
        self.assertTrue(finder.is_line_continued())

    def test_source_lines_simple(self):
        to_lines = SourceLinesAdapter('line1\nline2\n')
        self.assertEquals('line1', to_lines.get_line(1))
        self.assertEquals('line2', to_lines.get_line(2))
        self.assertEquals('', to_lines.get_line(3))
        self.assertEquals(3, to_lines.length())

    def test_source_lines_get_line_number(self):
        to_lines = SourceLinesAdapter('line1\nline2\n')
        self.assertEquals(1, to_lines.get_line_number(0))
        self.assertEquals(1, to_lines.get_line_number(5))
        self.assertEquals(2, to_lines.get_line_number(7))
        self.assertEquals(3, to_lines.get_line_number(12))

    def test_source_lines_get_line_start(self):
        to_lines = SourceLinesAdapter('line1\nline2\n')
        self.assertEquals(0, to_lines.get_line_start(1))
        self.assertEquals(6, to_lines.get_line_start(2))
        self.assertEquals(12, to_lines.get_line_start(3))

    def test_source_lines_get_line_end(self):
        to_lines = SourceLinesAdapter('line1\nline2\n')
        self.assertEquals(5, to_lines.get_line_end(1))
        self.assertEquals(11, to_lines.get_line_end(2))
        self.assertEquals(12, to_lines.get_line_end(3))

    def test_source_lines_last_line_with_no_new_line(self):
        to_lines = SourceLinesAdapter('line1')
        self.assertEquals(1, to_lines.get_line_number(5))


class WordRangeFinderTest(unittest.TestCase):

    def setUp(self):
        super(WordRangeFinderTest, self).setUp()

    def tearDown(self):
        super(WordRangeFinderTest, self).tearDown()

    def test_inside_parans(self):
        word_finder = WordRangeFinder('a_func(a_var)')
        self.assertEquals('a_var', word_finder.get_primary_at(10))

    def test_simple_names(self):
        word_finder = WordRangeFinder('a_var = 10')
        self.assertEquals('a_var', word_finder.get_primary_at(3))

    def test_function_calls(self):
        word_finder = WordRangeFinder('sample_function()')
        self.assertEquals('sample_function', word_finder.get_primary_at(10))

    def test_attribute_accesses(self):
        word_finder = WordRangeFinder('a_var.an_attr')
        self.assertEquals('a_var.an_attr', word_finder.get_primary_at(10))

    def test_word_finder_on_word_beginning(self):
        code = 'print a_var\n'
        word_finder = WordRangeFinder(code)
        self.assertEquals('a_var', word_finder.get_word_at(code.index('a_var')))

    def test_word_finder_on_primary_beginning(self):
        code = 'print a_var\n'
        word_finder = WordRangeFinder(code)
        self.assertEquals('a_var', word_finder.get_primary_at(code.index('a_var')))

    def test_word_finder_on_word_ending(self):
        code = 'print a_var\n'
        word_finder = WordRangeFinder(code)
        self.assertEquals('a_var', word_finder.get_word_at(code.index('a_var') + 5))

    def test_word_finder_on_primary_ending(self):
        code = 'print a_var\n'
        word_finder = WordRangeFinder(code)
        self.assertEquals('a_var', word_finder.get_primary_at(code.index('a_var') + 5))

    def test_word_finder_on_primaries_with_dots_inside_parens(self):
        code = '(a_var.\nattr)'
        word_finder = WordRangeFinder(code)
        self.assertEquals('a_var.\nattr', word_finder.get_primary_at(code.index('attr') + 1))

    def test_strings(self):
        word_finder = WordRangeFinder('"a string".split()')
        self.assertEquals('"a string".split', word_finder.get_primary_at(14))

    def test_function_calls2(self):
        word_finder = WordRangeFinder('file("afile.txt").read()')
        self.assertEquals('file("afile.txt").read',
                          word_finder.get_primary_at(18))

    def test_parens(self):
        word_finder = WordRangeFinder('("afile.txt").split()')
        self.assertEquals('("afile.txt").split',
                          word_finder.get_primary_at(18))

    def test_function_with_no_param(self):
        word_finder = WordRangeFinder('AClass().a_func()')
        self.assertEquals('AClass().a_func', word_finder.get_primary_at(12))

    def test_function_with_multiple_param(self):
        word_finder = WordRangeFinder('AClass(a_param, another_param, "a string").a_func()')
        self.assertEquals('AClass(a_param, another_param, "a string").a_func',
                          word_finder.get_primary_at(44))

    def test_param_expressions(self):
        word_finder = WordRangeFinder('AClass(an_object.an_attr).a_func()')
        self.assertEquals('an_object.an_attr',
                          word_finder.get_primary_at(20))

    def test_string_parens(self):
        word_finder = WordRangeFinder('a_func("(").an_attr')
        self.assertEquals('a_func("(").an_attr',
                          word_finder.get_primary_at(16))

    def test_extra_spaces(self):
        word_finder = WordRangeFinder('a_func  (  "(" ) .   an_attr')
        self.assertEquals('a_func  (  "(" ) .   an_attr',
                          word_finder.get_primary_at(26))

    def test_functions_on_ending_parens(self):
        word_finder = WordRangeFinder('A()')
        self.assertEquals('A()', word_finder.get_primary_at(2))

    def test_splitted_statement(self):
        word_finder = WordRangeFinder('an_object.an_attr')
        self.assertEquals(('an_object', 'an_at', 10),
                          word_finder.get_splitted_primary_before(15))

    def test_empty_splitted_statement(self):
        word_finder = WordRangeFinder('an_attr')
        self.assertEquals(('', 'an_at', 0),
                          word_finder.get_splitted_primary_before(5))

    def test_empty_splitted_statement2(self):
        word_finder = WordRangeFinder('an_object.')
        self.assertEquals(('an_object', '', 10),
                          word_finder.get_splitted_primary_before(10))

    def test_empty_splitted_statement3(self):
        word_finder = WordRangeFinder('')
        self.assertEquals(('', '', 0),
                          word_finder.get_splitted_primary_before(0))

    def test_empty_splitted_statement4(self):
        word_finder = WordRangeFinder('a_var = ')
        self.assertEquals(('', '', 8),
                          word_finder.get_splitted_primary_before(8))

    def test_operators_inside_parens(self):
        word_finder = WordRangeFinder('(a_var + another_var).reverse()')
        self.assertEquals('(a_var + another_var).reverse',
                          word_finder.get_primary_at(25))

    def test_dictionaries(self):
        word_finder = WordRangeFinder('print {1: "one", 2: "two"}.keys()')
        self.assertEquals('print {1: "one", 2: "two"}.keys',
                          word_finder.get_primary_at(29))

    def test_following_parens(self):
        code = 'a_var = a_func()()'
        word_finder = WordRangeFinder(code)
        self.assertEquals('a_func()()',
                          word_finder.get_primary_at(code.index(')(') + 3))

    # TODO: eliminating comments
    def xxx_test_comments_for_finding_statements(self):
        word_finder = WordRangeFinder('# var2 . \n  var3')
        self.assertEquals('var3',
                          word_finder.get_primary_at(14))

    def test_comments_for_finding_statements2(self):
        word_finder = WordRangeFinder('var1 + "# var2".\n  var3')
        self.assertEquals('"# var2".\n  var3',
                          word_finder.get_primary_at(21))

    def test_import_statement_finding(self):
        code = 'import mod\na_var = 10\n'
        word_finder = WordRangeFinder(code)
        self.assertTrue(word_finder.is_import_statement(code.index('mod') + 1))
        self.assertFalse(word_finder.is_import_statement(code.index('a_var') + 1))


class ScopeNameFinderTest(unittest.TestCase):

    def setUp(self):
        super(ScopeNameFinderTest, self).setUp()
        self.project_root = 'sample_project'
        testutils.remove_recursively(self.project_root)
        self.project = Project(self.project_root)
        self.pycore = self.project.get_pycore()

    def tearDown(self):
        testutils.remove_recursively(self.project_root)
        super(ScopeNameFinderTest, self).tearDown()

    def test_global_name_in_class_body(self):
        code = 'a_var = 10\nclass Sample(object):\n    a_var = a_var\n'
        scope = self.pycore.get_string_scope(code)
        name_finder = ScopeNameFinder(scope.pyobject)
        self.assertEquals(scope.get_name('a_var'), name_finder.get_pyname_at(len(code) - 3))

    def test_class_variable_attribute_in_class_body(self):
        code = 'a_var = 10\nclass Sample(object):\n    a_var = a_var\n'
        scope = self.pycore.get_string_scope(code)
        name_finder = ScopeNameFinder(scope.pyobject)
        a_var_pyname = scope.get_name('Sample').get_object().get_attribute('a_var')
        self.assertEquals(a_var_pyname, name_finder.get_pyname_at(len(code) - 12))

    def test_class_variable_attribute_in_class_body2(self):
        code = 'a_var = 10\nclass Sample(object):\n    a_var \\\n= a_var\n'
        scope = self.pycore.get_string_scope(code)
        name_finder = ScopeNameFinder(scope.pyobject)
        a_var_pyname = scope.get_name('Sample').get_object().get_attribute('a_var')
        self.assertEquals(a_var_pyname, name_finder.get_pyname_at(len(code) - 12))

    def test_class_method_attribute_in_class_body(self):
        code = 'class Sample(object):\n    def a_method(self):\n        pass\n'
        scope = self.pycore.get_string_scope(code)
        name_finder = ScopeNameFinder(scope.pyobject)
        a_method_pyname = scope.get_name('Sample').get_object().get_attribute('a_method')
        self.assertEquals(a_method_pyname,
                          name_finder.get_pyname_at(code.index('a_method') + 2))

    def test_inner_class_attribute_in_class_body(self):
        code = 'class Sample(object):\n    class AClass(object):\n        pass\n'
        scope = self.pycore.get_string_scope(code)
        name_finder = ScopeNameFinder(scope.pyobject)
        a_class_pyname = scope.get_name('Sample').get_object().get_attribute('AClass')
        self.assertEquals(a_class_pyname,
                          name_finder.get_pyname_at(code.index('AClass') + 2))

    def test_class_method_in_class_body_but_not_indexed(self):
        code = 'class Sample(object):\n    def a_func(self, a_func):\n        pass\n'
        scope = self.pycore.get_string_scope(code)
        a_func_pyname = scope.get_scopes()[0].get_scopes()[0].get_name('a_func')
        name_finder = ScopeNameFinder(scope.pyobject)
        self.assertEquals(a_func_pyname, name_finder.get_pyname_at(code.index(', a_func') + 3))

    def test_function_but_not_indexed(self):
        code = 'def a_func(a_func):\n    pass\n'
        scope = self.pycore.get_string_scope(code)
        a_func_pyname = scope.get_name('a_func')
        name_finder = ScopeNameFinder(scope.pyobject)
        self.assertEquals(a_func_pyname, name_finder.get_pyname_at(code.index('a_func') + 3))

    def test_modules_after_from_statements(self):
        root_folder = self.project.get_root_folder()
        mod = self.pycore.create_module(root_folder, 'mod')
        mod.write('def a_func():\n    pass\n')
        code = 'from mod import a_func\n'
        scope = self.pycore.get_string_scope(code)
        name_finder = ScopeNameFinder(scope.pyobject)
        mod_pyobject = self.pycore.resource_to_pyobject(mod)
        found_pyname = name_finder.get_pyname_at(code.index('mod') + 1)
        self.assertEquals(mod_pyobject, found_pyname.get_object())

    @testutils.run_only_for_25
    def test_relative_modules_after_from_statements(self):
        pkg1 = self.pycore.create_package(self.project.get_root_folder(), 'pkg1')
        pkg2 = self.pycore.create_package(pkg1, 'pkg2')
        mod1 = self.pycore.create_module(pkg1, 'mod1')
        mod2 = self.pycore.create_module(pkg2, 'mod2')
        mod1.write('def a_func():\n    pass\n')
        code = 'from ..mod1 import a_func\n'
        mod2.write(code)
        mod2_scope = self.pycore.resource_to_pyobject(mod2).get_scope()
        name_finder = ScopeNameFinder(mod2_scope.pyobject)
        mod1_pyobject = self.pycore.resource_to_pyobject(mod1)
        found_pyname = name_finder.get_pyname_at(code.index('mod1') + 1)
        self.assertEquals(mod1_pyobject, found_pyname.get_object())

    def test_relative_modules_after_from_statements2(self):
        mod1 = self.pycore.create_module(self.project.get_root_folder(), 'mod1')
        pkg1 = self.pycore.create_package(self.project.get_root_folder(), 'pkg1')
        pkg2 = self.pycore.create_package(pkg1, 'pkg2')
        mod2 = self.pycore.create_module(pkg2, 'mod2')
        mod1.write('import pkg1.pkg2.mod2')

        mod1_scope = self.pycore.resource_to_pyobject(mod1).get_scope()
        name_finder = ScopeNameFinder(mod1_scope.pyobject)
        pkg2_pyobject = self.pycore.resource_to_pyobject(pkg2)
        found_pyname = name_finder.get_pyname_at(mod1.read().index('pkg2') + 1)
        self.assertEquals(pkg2_pyobject, found_pyname.get_object())


class LogicalLineFinderTest(unittest.TestCase):

    def setUp(self):
        super(LogicalLineFinderTest, self).setUp()

    def tearDown(self):
        super(LogicalLineFinderTest, self).tearDown()

    def _get_logical_line_finder(self, code):
        return LogicalLineFinder(SourceLinesAdapter(code))

    def test_normal_lines(self):
        code = 'a_var = 10'
        line_finder = self._get_logical_line_finder(code)
        self.assertEquals((1, 1), line_finder.get_logical_line_in(1))

    def test_normal_lines2(self):
        code = 'another = 10\na_var = 20\n'
        line_finder = self._get_logical_line_finder(code)
        self.assertEquals((1, 1), line_finder.get_logical_line_in(1))
        self.assertEquals((2, 2), line_finder.get_logical_line_in(2))

    def test_implicit_continuation(self):
        code = 'a_var = 3 + \\\n    4 + \\\n    5'
        line_finder = self._get_logical_line_finder(code)
        self.assertEquals((1, 3), line_finder.get_logical_line_in(2))

    def test_explicit_continuation(self):
        code = 'print 2\na_var = (3 + \n    4, \n    5)\n'
        line_finder = self._get_logical_line_finder(code)
        self.assertEquals((2, 4), line_finder.get_logical_line_in(2))

    def test_explicit_continuation_comments(self):
        code = '#\na_var = 3\n'
        line_finder = self._get_logical_line_finder(code)
        self.assertEquals((2, 2), line_finder.get_logical_line_in(2))

    def test_multiple_indented_ifs(self):
        code = 'if True:\n    if True:\n        if True:\n            pass\n    a = 10\n'
        line_finder = self._get_logical_line_finder(code)
        self.assertEquals((5, 5), line_finder.get_logical_line_in(5))


def suite():
    result = unittest.TestSuite()
    result.addTests(unittest.makeSuite(StatementRangeFinderTest))
    result.addTests(unittest.makeSuite(WordRangeFinderTest))
    result.addTests(unittest.makeSuite(ScopeNameFinderTest))
    result.addTests(unittest.makeSuite(LogicalLineFinderTest))
    return result

if __name__ == '__main__':
    unittest.main()


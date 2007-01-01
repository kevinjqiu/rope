import unittest
import rope.base.codeanalyze
import rope.refactor.rename
import rope.base.exceptions
import rope.base.project

import ropetest.testutils as testutils


class ExtractMethodTest(unittest.TestCase):

    def setUp(self):
        super(ExtractMethodTest, self).setUp()
        self.project_root = 'sample_project'
        testutils.remove_recursively(self.project_root)
        self.project = rope.base.project.Project(self.project_root)
        self.pycore = self.project.get_pycore()
        self.refactoring = self.project.get_pycore().get_refactoring()

    def tearDown(self):
        testutils.remove_recursively(self.project_root)
        super(ExtractMethodTest, self).tearDown()
        
    def do_extract_method(self, source_code, start, end, extracted):
        testmod = self.pycore.create_module(self.project.get_root_folder(), 'testmod')
        testmod.write(source_code)
        self.refactoring.extract_method(testmod, start, end, extracted)
        return testmod.read()

    def do_extract_variable(self, source_code, start, end, extracted):
        testmod = self.pycore.create_module(self.project.get_root_folder(), 'testmod')
        testmod.write(source_code)
        self.refactoring.extract_variable(testmod, start, end, extracted)
        return testmod.read()

    def _convert_line_range_to_offset(self, code, start, end):
        lines = rope.base.codeanalyze.SourceLinesAdapter(code)
        return lines.get_line_start(start), lines.get_line_end(end)
    
    def test_simple_extract_function(self):
        code = "def a_func():\n    print 'one'\n    print 'two'\n"
        start, end = self._convert_line_range_to_offset(code, 2, 2)
        refactored = self.do_extract_method(code, start, end, 'extracted')
        expected = "def a_func():\n    extracted()\n    print 'two'\n\n" \
                   "def extracted():\n    print 'one'\n"
        self.assertEquals(expected, refactored)

    def test_extract_function_at_the_end_of_file(self):
        code = "def a_func():\n    print 'one'"
        start, end = self._convert_line_range_to_offset(code, 2, 2)
        refactored = self.do_extract_method(code, start, end, 'extracted')
        expected = "def a_func():\n    extracted()\n" \
                   "def extracted():\n    print 'one'\n"
        self.assertEquals(expected, refactored)

    def test_extract_function_after_scope(self):
        code = "def a_func():\n    print 'one'\n    print 'two'\n\nprint 'hey'\n"
        start, end = self._convert_line_range_to_offset(code, 2, 2)
        refactored = self.do_extract_method(code, start, end, 'extracted')
        expected = "def a_func():\n    extracted()\n    print 'two'\n\n" \
                   "def extracted():\n    print 'one'\n\nprint 'hey'\n"
        self.assertEquals(expected, refactored)

    def test_simple_extract_function_with_parameter(self):
        code = "def a_func():\n    a_var = 10\n    print a_var\n"
        start, end = self._convert_line_range_to_offset(code, 3, 3)
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "def a_func():\n    a_var = 10\n    new_func(a_var)\n\n" \
                   "def new_func(a_var):\n    print a_var\n"
        self.assertEquals(expected, refactored)

    def test_not_unread_variables_as_parameter(self):
        code = "def a_func():\n    a_var = 10\n    print 'hey'\n"
        start, end = self._convert_line_range_to_offset(code, 3, 3)
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "def a_func():\n    a_var = 10\n    new_func()\n\n" \
                   "def new_func():\n    print 'hey'\n"
        self.assertEquals(expected, refactored)

    def test_simple_extract_function_with_two_parameter(self):
        code = "def a_func():\n    a_var = 10\n    another_var = 20\n" \
               "    third_var = a_var + another_var\n"
        start, end = self._convert_line_range_to_offset(code, 4, 4)
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "def a_func():\n    a_var = 10\n    another_var = 20\n" \
                   "    new_func(a_var, another_var)\n\n" \
                   "def new_func(a_var, another_var):\n    third_var = a_var + another_var\n"
        self.assertEquals(expected, refactored)

    def test_simple_extract_function_with_return_value(self):
        code = "def a_func():\n    a_var = 10\n    print a_var\n"
        start, end = self._convert_line_range_to_offset(code, 2, 2)
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "def a_func():\n    a_var = new_func()\n    print a_var\n\n" \
                   "def new_func():\n    a_var = 10\n    return a_var\n"
        self.assertEquals(expected, refactored)

    def test_extract_function_with_multiple_return_values(self):
        code = "def a_func():\n    a_var = 10\n    another_var = 20\n" \
               "    third_var = a_var + another_var\n"
        start, end = self._convert_line_range_to_offset(code, 2, 3)
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "def a_func():\n    a_var, another_var = new_func()\n" \
                   "    third_var = a_var + another_var\n\n" \
                   "def new_func():\n    a_var = 10\n    another_var = 20\n" \
                   "    return a_var, another_var\n"
        self.assertEquals(expected, refactored)

    def test_simple_extract_method(self):
        code = "class AClass(object):\n\n" \
               "    def a_func(self):\n        print 'one'\n        print 'two'\n"
        start, end = self._convert_line_range_to_offset(code, 4, 4)
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "class AClass(object):\n\n" \
                   "    def a_func(self):\n        self.new_func()\n        print 'two'\n\n" \
                   "    def new_func(self):\n        print 'one'\n"
        self.assertEquals(expected, refactored)

    def test_extract_method_with_args_and_returns(self):
        code = "class AClass(object):\n" \
               "    def a_func(self):\n" \
               "        a_var = 10\n" \
               "        another_var = a_var * 3\n" \
               "        third_var = a_var + another_var\n"
        start, end = self._convert_line_range_to_offset(code, 4, 4)
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "class AClass(object):\n" \
                   "    def a_func(self):\n" \
                   "        a_var = 10\n" \
                   "        another_var = self.new_func(a_var)\n" \
                   "        third_var = a_var + another_var\n\n" \
                   "    def new_func(self, a_var):\n" \
                   "        another_var = a_var * 3\n" \
                   "        return another_var\n"
        self.assertEquals(expected, refactored)

    def test_extract_method_with_self_as_argument(self):
        code = "class AClass(object):\n" \
               "    def a_func(self):\n" \
               "        print self\n"
        start, end = self._convert_line_range_to_offset(code, 3, 3)
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "class AClass(object):\n" \
                   "    def a_func(self):\n" \
                   "        self.new_func()\n\n" \
                   "    def new_func(self):\n" \
                   "        print self\n"
        self.assertEquals(expected, refactored)

    def test_extract_method_with_multiple_methods(self):
        code = "class AClass(object):\n" \
               "    def a_func(self):\n" \
               "        print self\n\n" \
               "    def another_func(self):\n" \
               "        pass\n"
        start, end = self._convert_line_range_to_offset(code, 3, 3)
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "class AClass(object):\n" \
                   "    def a_func(self):\n" \
                   "        self.new_func()\n\n" \
                   "    def new_func(self):\n" \
                   "        print self\n\n" \
                   "    def another_func(self):\n" \
                   "        pass\n"
        self.assertEquals(expected, refactored)

    def test_extract_function_with_function_returns(self):
        code = "def a_func():\n    def inner_func():\n        pass\n    inner_func()\n"
        start, end = self._convert_line_range_to_offset(code, 2, 3)
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "def a_func():\n    inner_func = new_func()\n    inner_func()\n\n" \
                   "def new_func():\n    def inner_func():\n        pass\n    return inner_func\n"
        self.assertEquals(expected, refactored)

    def test_simple_extract_global_function(self):
        code = "print 'one'\nprint 'two'\nprint 'three'\n"
        start, end = self._convert_line_range_to_offset(code, 2, 2)
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "print 'one'\n\ndef new_func():\n    print 'two'\n\nnew_func()\nprint 'three'\n"
        self.assertEquals(expected, refactored)

    def test_extract_global_function_inside_ifs(self):
        code = 'if True:\n    a = 10\n'
        start, end = self._convert_line_range_to_offset(code, 2, 2)
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = 'if True:\n\n    def new_func():\n        a = 10\n\n    new_func()\n'
        self.assertEquals(expected, refactored)

    def test_extract_function_while_inner_function_reads(self):
        code = "def a_func():\n    a_var = 10\n    " \
               "def inner_func():\n        print a_var\n    return inner_func\n"
        start, end = self._convert_line_range_to_offset(code, 3, 4)
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "def a_func():\n    a_var = 10\n" \
                   "    inner_func = new_func(a_var)\n    return inner_func\n\n" \
                   "def new_func(a_var):\n    def inner_func():\n        print a_var\n" \
                   "    return inner_func\n"
        self.assertEquals(expected, refactored)

    @testutils.assert_raises(rope.base.exceptions.RefactoringException)
    def test_extract_method_bad_range(self):
        code = "def a_func():\n    pass\na_var = 10\n"
        start, end = self._convert_line_range_to_offset(code, 2, 3)
        self.do_extract_method(code, start, end, 'new_func')

    @testutils.assert_raises(rope.base.exceptions.RefactoringException)
    def test_extract_method_bad_range2(self):
        code = "class AClass(object):\n    pass\n"
        start, end = self._convert_line_range_to_offset(code, 1, 1)
        self.do_extract_method(code, start, end, 'new_func')

    @testutils.assert_raises(rope.base.exceptions.RefactoringException)
    def test_extract_method_containing_return(self):
        code = "def a_func(arg):\n    return arg * 2\n"
        start, end = self._convert_line_range_to_offset(code, 2, 2)
        self.do_extract_method(code, start, end, 'new_func')

    @testutils.assert_raises(rope.base.exceptions.RefactoringException)
    def test_extract_method_containing_yield(self):
        code = "def a_func(arg):\n    yield arg * 2\n"
        start, end = self._convert_line_range_to_offset(code, 2, 2)
        self.do_extract_method(code, start, end, 'new_func')

    @testutils.assert_raises(rope.base.exceptions.RefactoringException)
    def test_extract_method_containing_uncomplete_lines(self):
        code = 'a_var = 20\nanother_var = 30\n'
        start = code.index('20')
        end = code.index('30') + 2
        self.do_extract_method(code, start, end, 'new_func')

    @testutils.assert_raises(rope.base.exceptions.RefactoringException)
    def test_extract_method_containing_uncomplete_lines2(self):
        code = 'a_var = 20\nanother_var = 30\n'
        start = code.index('20')
        end = code.index('another') + 5
        self.do_extract_method(code, start, end, 'new_func')

    def test_extract_function_and_argument_as_paramenter(self):
        code = 'def a_func(arg):\n    print arg\n'
        start, end = self._convert_line_range_to_offset(code, 2, 2)
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = 'def a_func(arg):\n    new_func(arg)\n\n' \
                   'def new_func(arg):\n    print arg\n'
        self.assertEquals(expected, refactored)

    def test_extract_function_and_end_as_the_start_of_a_line(self):
        code = 'print "hey"\nif True:\n    pass\n'
        start = 0
        end = code.index('\n') + 1
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = '\ndef new_func():\n    print "hey"\n\nnew_func()\nif True:\n    pass\n'
        self.assertEquals(expected, refactored)

    def test_extract_function_and_indented_blocks(self):
        code = 'def a_func(arg):\n    if True:\n' \
               '        if True:\n            print arg\n'
        start, end = self._convert_line_range_to_offset(code, 3, 4)
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = 'def a_func(arg):\n    if True:\n        new_func(arg)\n\n' \
                   'def new_func(arg):\n    if True:\n        print arg\n'
        self.assertEquals(expected, refactored)
    
    def test_extract_method_and_multi_line_headers(self):
        code = 'def a_func(\n           arg):\n    print arg\n'
        start, end = self._convert_line_range_to_offset(code, 3, 3)
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = 'def a_func(\n           arg):\n    new_func(arg)\n\n' \
                   'def new_func(arg):\n    print arg\n'
        self.assertEquals(expected, refactored)
    
    def test_single_line_extract_function(self):
        code = 'a_var = 10 + 20\n'
        start = code.index('10')
        end = code.index('20') + 2
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "\ndef new_func():\n    return 10 + 20\n\na_var = new_func()\n"
        self.assertEquals(expected, refactored)

    def test_single_line_extract_function2(self):
        code = 'def a_func():\n    a = 10\n    b = a * 20\n'
        start = code.rindex('a')
        end = code.index('20') + 2
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = 'def a_func():\n    a = 10\n    b = new_func(a)\n' \
                   '\ndef new_func(a):\n    return a * 20\n'
        self.assertEquals(expected, refactored)

    def test_single_line_extract_method_and_logical_lines(self):
        code = 'a_var = 10 +\\\n    20\n'
        start = code.index('10')
        end = code.index('20') + 2
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "\ndef new_func():\n    return 10 + 20\n\na_var = new_func()\n"
        self.assertEquals(expected, refactored)

    def test_single_line_extract_method_and_logical_lines2(self):
        code = 'a_var = (10,\\\n    20)\n'
        start = code.index('10') - 1
        end = code.index('20') + 3
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "\ndef new_func():\n    return (10, 20)\n\na_var = new_func()\n"
        self.assertEquals(expected, refactored)

    def test_single_line_extract_method(self):
        code = "class AClass(object):\n\n" \
               "    def a_func(self):\n        a = 10\n        b = a * a\n"
        start = code.rindex('=') + 2
        end = code.rindex('a') + 1
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "class AClass(object):\n\n" \
                   "    def a_func(self):\n        a = 10\n        b = self.new_func(a)\n\n" \
                   "    def new_func(self, a):\n        return a * a\n"
        self.assertEquals(expected, refactored)

    def test_single_line_extract_function_if_condition(self):
        code = 'if True:\n    pass\n'
        start = code.index('True')
        end = code.index('True') + 4
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = "\ndef new_func():\n    return True\n\nif new_func():\n    pass\n"
        self.assertEquals(expected, refactored)

    def test_unneeded_params(self):
        code = 'class A(object):\n    def a_func(self):\n        a_var = 10\n        a_var += 2\n'
        start = code.rindex('2')
        end = code.rindex('2') + 1
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = 'class A(object):\n' \
                   '    def a_func(self):\n        a_var = 10\n        a_var += self.new_func()\n\n' \
                   '    def new_func(self):\n        return 2\n'
        self.assertEquals(expected, refactored)

    def test_breaks_and_continues_inside_loops(self):
        code = 'def a_func():\n    for i in range(10):\n        continue\n'
        start = code.index('for')
        end = len(code) - 1
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = 'def a_func():\n    new_func()\n\n' \
                   'def new_func():\n    for i in range(10):\n        continue\n'
        self.assertEquals(expected, refactored)

    @testutils.assert_raises(rope.base.exceptions.RefactoringException)
    def test_breaks_and_continues_outside_loops(self):
        code = 'def a_func():\n    for i in range(10):\n        a = i\n        continue\n'
        start = code.index('a = i')
        end = len(code) - 1
        refactored = self.do_extract_method(code, start, end, 'new_func')

    def test_variable_writes_followed_by_variable_reads_after_extraction(self):
        code = 'def a_func():\n    a = 1\n    a = 2\n    b = a\n'
        start = code.index('a = 1')
        end = code.index('a = 2') - 1
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = 'def a_func():\n    new_func()\n    a = 2\n    b = a\n\n' \
                   'def new_func():\n    a = 1\n'
        self.assertEquals(expected, refactored)

    def test_variable_writes_followed_by_variable_reads_inside_extraction(self):
        code = 'def a_func():\n    a = 1\n    a = 2\n    b = a\n'
        start = code.index('a = 2')
        end = len(code) - 1
        refactored = self.do_extract_method(code, start, end, 'new_func')
        expected = 'def a_func():\n    a = 1\n    new_func()\n\n' \
                   'def new_func():\n    a = 2\n    b = a\n'
        self.assertEquals(expected, refactored)

    def test_extract_variable(self):
        code = 'a_var = 10 + 20\n'
        start = code.index('10')
        end = code.index('20') + 2
        refactored = self.do_extract_variable(code, start, end, 'new_var')
        expected = 'new_var = 10 + 20\na_var = new_var\n'
        self.assertEquals(expected, refactored)

    def test_extract_variable_multiple_lines(self):
        code = 'a = 1\nb = 2\n'
        start = code.index('1')
        end = code.index('1') + 1
        refactored = self.do_extract_variable(code, start, end, 'c')
        expected = 'c = 1\na = c\nb = 2\n'
        self.assertEquals(expected, refactored)

    def test_extract_variable_in_the_middle_of_statements(self):
        code = 'a = 1 + 2\n'
        start = code.index('1')
        end = code.index('1') + 1
        refactored = self.do_extract_variable(code, start, end, 'c')
        expected = 'c = 1\na = c + 2\n'
        self.assertEquals(expected, refactored)

    def test_extract_variable_for_a_tuple(self):
        code = 'a = 1, 2\n'
        start = code.index('1')
        end = code.index('2') + 1
        refactored = self.do_extract_variable(code, start, end, 'c')
        expected = 'c = 1, 2\na = c\n'
        self.assertEquals(expected, refactored)

    def test_extract_variable_for_a_string(self):
        code = 'def a_func():\n    a = "hey!"\n'
        start = code.index('"')
        end = code.rindex('"') + 1
        refactored = self.do_extract_variable(code, start, end, 'c')
        expected = 'def a_func():\n    c = "hey!"\n    a = c\n'
        self.assertEquals(expected, refactored)

    def test_extract_variable_inside_ifs(self):
        code = 'if True:\n    a = 1 + 2\n'
        start = code.index('1')
        end = code.rindex('2') + 1
        refactored = self.do_extract_variable(code, start, end, 'b')
        expected = 'if True:\n    b = 1 + 2\n    a = b\n'
        self.assertEquals(expected, refactored)

    def test_extract_variable_inside_ifs_and_logical_lines(self):
        code = 'if True:\n    a = (3 + \n1 + 2)\n'
        start = code.index('1')
        end = code.index('2') + 1
        refactored = self.do_extract_variable(code, start, end, 'b')
        expected = 'if True:\n    b = 1 + 2\n    a = (3 + \nb)\n'
        self.assertEquals(expected, refactored)

    def test_extract_variable_starting_from_the_start_of_the_line(self):
        code = 'a_dict = {1: 1}\na_dict.values().count(1)\n'
        start = code.rindex('a_dict')
        end = code.index('count') - 1
        refactored = self.do_extract_variable(code, start, end, 'values')
        expected = 'a_dict = {1: 1}\nvalues = a_dict.values()\nvalues.count(1)\n'
        self.assertEquals(expected, refactored)

    def test_extract_variable_on_the_last_line_of_a_function(self):
        code = 'def f():\n    a_var = {}\n    a_var.keys()\n'
        start = code.rindex('a_var')
        end = code.index('.keys')
        refactored = self.do_extract_variable(code, start, end, 'new_var')
        expected = 'def f():\n    a_var = {}\n    new_var = a_var\n    new_var.keys()\n'
        self.assertEquals(expected, refactored)

    def test_extract_variable_on_the_indented_function_statement(self):
        code = 'def f():\n    if True:\n        a_var = 1 + 2\n'
        start = code.index('1')
        end = code.index('2') + 1
        refactored = self.do_extract_variable(code, start, end, 'new_var')
        expected = 'def f():\n    if True:\n        new_var = 1 + 2\n        a_var = new_var\n'
        self.assertEquals(expected, refactored)

    def test_extract_method_on_the_last_line_of_a_function(self):
        code = 'def f():\n    a_var = {}\n    a_var.keys()\n'
        start = code.rindex('a_var')
        end = code.index('.keys')
        refactored = self.do_extract_method(code, start, end, 'new_f')
        expected = 'def f():\n    a_var = {}\n    new_f(a_var).keys()\n\n' \
                   'def new_f(a_var):\n    return a_var\n'
        self.assertEquals(expected, refactored)

    @testutils.assert_raises(rope.base.exceptions.RefactoringException)
    def test_raising_exception_when_on_incomplete_variables(self):
        code = 'a_var = 10 + 20\n'
        start = code.index('10') + 1
        end = code.index('20') + 2
        refactored = self.do_extract_method(code, start, end, 'new_func')

    @testutils.assert_raises(rope.base.exceptions.RefactoringException)
    def test_raising_exception_when_on_incomplete_variables_on_end(self):
        code = 'a_var = 10 + 20\n'
        start = code.index('10')
        end = code.index('20') + 1
        refactored = self.do_extract_method(code, start, end, 'new_func')

    @testutils.assert_raises(rope.base.exceptions.RefactoringException)
    def test_raising_exception_on_bad_parens(self):
        code = 'a_var = (10 + 20) + 30\n'
        start = code.index('20')
        end = code.index('30') + 2
        refactored = self.do_extract_method(code, start, end, 'new_func')

    @testutils.assert_raises(rope.base.exceptions.RefactoringException)
    def test_raising_exception_on_bad_operators(self):
        code = 'a_var = 10 + 20 + 30\n'
        start = code.index('10')
        end = code.rindex('+') + 1
        refactored = self.do_extract_method(code, start, end, 'new_func')

    # FIXME: Extract method should be more intelligent about bad ranges
    @testutils.assert_raises(rope.base.exceptions.RefactoringException)
    def xxx_test_raising_exception_on_function_parens(self):
        code = 'a = range(10)'
        start = code.index('(')
        end = code.rindex(')') + 1
        refactored = self.do_extract_method(code, start, end, 'new_func')


if __name__ == '__main__':
    unittest.main()

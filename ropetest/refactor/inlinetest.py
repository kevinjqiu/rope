import unittest
import rope.exceptions
import rope.project
import ropetest


class InlineLocalVariableTest(unittest.TestCase):

    def setUp(self):
        super(InlineLocalVariableTest, self).setUp()
        self.project_root = 'sample_project'
        ropetest.testutils.remove_recursively(self.project_root)
        self.project = rope.project.Project(self.project_root)
        self.pycore = self.project.get_pycore()
        self.refactoring = self.project.get_pycore().get_refactoring()
        self.mod = self.pycore.create_module(self.project.get_root_folder(), 'mod')

    def tearDown(self):
        ropetest.testutils.remove_recursively(self.project_root)
        super(InlineLocalVariableTest, self).tearDown()
    
    def _inline_local_variable(self, code, offset):
        self.mod.write(code)
        self.refactoring.inline_local_variable(self.mod, offset)
        return self.mod.read()
    
    def test_simple_case(self):
        code = 'a_var = 10\nanother_var = a_var\n'
        refactored = self._inline_local_variable(code, code.index('a_var') + 1)
        self.assertEquals('another_var = 10\n', refactored)        

    def test_empty_case(self):
        code = 'a_var = 10\n'
        refactored = self._inline_local_variable(code, code.index('a_var') + 1)
        self.assertEquals('', refactored)        

    def test_long_definition(self):
        code = 'a_var = 10 + (10 + 10)\nanother_var = a_var\n'
        refactored = self._inline_local_variable(code, code.index('a_var') + 1)
        self.assertEquals('another_var = 10 + (10 + 10)\n', refactored)        

    def test_explicit_continuation(self):
        code = 'a_var = (10 +\n 10)\nanother_var = a_var\n'
        refactored = self._inline_local_variable(code, code.index('a_var') + 1)
        self.assertEquals('another_var = (10 + 10)\n', refactored)        

    def test_implicit_continuation(self):
        code = 'a_var = 10 +\\\n       10\nanother_var = a_var\n'
        refactored = self._inline_local_variable(code, code.index('a_var') + 1)
        self.assertEquals('another_var = 10 + 10\n', refactored)        

    @ropetest.testutils.assert_raises(rope.exceptions.RefactoringException)
    def test_on_classes(self):
        code = 'def AClass(object):\n    pass\n'
        refactored = self._inline_local_variable(code, code.index('AClass') + 1)

    @ropetest.testutils.assert_raises(rope.exceptions.RefactoringException)
    def test_multiple_assignments(self):
        code = 'a_var = 10\na_var = 20\n'
        refactored = self._inline_local_variable(code, code.index('a_var') + 1)

    @ropetest.testutils.assert_raises(rope.exceptions.RefactoringException)
    def test_on_parameters(self):
        code = 'def a_func(a_param):\n    pass\n'
        refactored = self._inline_local_variable(code, code.index('a_param') + 1)

    @ropetest.testutils.assert_raises(rope.exceptions.RefactoringException)
    def test_tuple_assignments(self):
        code = 'a_var, another_var = (20, 30)\n'
        refactored = self._inline_local_variable(code, code.index('a_var') + 1)

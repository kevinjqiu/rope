import rope.base.codeanalyze
import rope.base.evaluate
import rope.base.builtins
import rope.base.oi.objectinfer
import rope.base.pyscopes
from rope.base import (defpynames as pynames, exceptions,
                       ast, astutils, pyobjects)
from rope.base.pyobjects import *


class PyFunction(pyobjects.PyFunction):

    def __init__(self, pycore, ast_node, parent):
        AbstractFunction.__init__(self)
        PyDefinedObject.__init__(self, pycore, ast_node, parent)
        self.arguments = self.ast_node.args
        self.decorators = self.ast_node.decorators
        self.parameter_pyobjects = pynames._Inferred(
            self._infer_parameters, self.get_module()._get_concluded_data())
        self.returned = pynames._Inferred(self._infer_returned)
        self.parameter_pynames = None

    def _create_structural_attributes(self):
        return {}

    def _create_concluded_attributes(self):
        return {}

    def _create_scope(self):
        return rope.base.pyscopes.FunctionScope(self.pycore, self,
                                                _FunctionVisitor)

    def _infer_parameters(self):
        pyobjects = rope.base.oi.objectinfer.infer_parameter_objects(self)
        self._handle_special_args(pyobjects)
        return pyobjects

    def _infer_returned(self, args=None):
        return rope.base.oi.objectinfer.infer_returned_object(self, args)

    def _handle_special_args(self, pyobjects):
        if len(pyobjects) == len(self.arguments.args):
            if self.arguments.vararg:
                pyobjects.append(rope.base.builtins.get_list())
            if self.arguments.kwarg:
                pyobjects.append(rope.base.builtins.get_dict())

    def _set_parameter_pyobjects(self, pyobjects):
        if pyobjects is not None:
            self._handle_special_args(pyobjects)
        self.parameter_pyobjects.set(pyobjects)

    def get_parameters(self):
        if self.parameter_pynames is None:
            result = {}
            for index, name in enumerate(self.get_param_names()):
                # TODO: handle tuple parameters
                result[name] = pynames.ParameterName(self, index)
            self.parameter_pynames = result
        return self.parameter_pynames

    def get_parameter(self, index):
        if index < len(self.parameter_pyobjects.get()):
            return self.parameter_pyobjects.get()[index]

    def get_returned_object(self, args):
        return self.returned.get(args)

    def get_name(self):
        return self.get_ast().name

    def get_param_names(self, special_args=True):
        # TODO: handle tuple parameters
        result = [node.id for node in self.arguments.args
                  if isinstance(node, ast.Name)]
        if special_args:
            if self.arguments.vararg:
                result.append(self.arguments.vararg)
            if self.arguments.kwarg:
                result.append(self.arguments.kwarg)
        return result

    def get_kind(self):
        """Get function type

        It returns one of 'function', 'method', 'staticmethod' or
        'classmethod' strs.

        """
        scope = self.parent.get_scope()
        if isinstance(self.parent, PyClass):
            for decorator in self.get_ast().decorators:
                pyname = rope.base.evaluate.get_statement_result(scope,
                                                                 decorator)
                if pyname == rope.base.builtins.builtins['staticmethod']:
                    return 'staticmethod'
                if pyname == rope.base.builtins.builtins['classmethod']:
                    return 'classmethod'
            return 'method'
        return 'function'


class PyClass(pyobjects.PyClass):

    def __init__(self, pycore, ast_node, parent):
        AbstractClass.__init__(self)
        PyDefinedObject.__init__(self, pycore, ast_node, parent)
        self.parent = parent
        self._superclasses = self.get_module()._get_concluded_data()
        self.defineds = None

    def get_superclasses(self):
        if self._superclasses.get() is None:
            self._superclasses.set(self._get_bases())
        return self._superclasses.get()

    def get_name(self):
        return self.get_ast().name

    def _get_defined_objects(self):
        if self.defineds is None:
            self._get_structural_attributes()
        return self.defineds

    def _create_structural_attributes(self):
        new_visitor = _ClassVisitor(self.pycore, self)
        for child in ast.get_child_nodes(self.ast_node):
            ast.walk(child, new_visitor)
        self.defineds = new_visitor.defineds
        return new_visitor.names

    def _create_concluded_attributes(self):
        result = {}
        for base in reversed(self.get_superclasses()):
            result.update(base.get_attributes())
        return result

    def _get_bases(self):
        result = []
        for base_name in self.ast_node.bases:
            base = rope.base.evaluate.get_statement_result(
                self.parent.get_scope(), base_name)
            if base is not None and \
               base.get_object().get_type() == get_base_type('Type'):
                result.append(base.get_object())
        return result

    def _create_scope(self):
        return rope.base.pyscopes.ClassScope(self.pycore, self)


class PyModule(pyobjects.PyModule):

    def __init__(self, pycore, source_code,
                 resource=None, force_errors=False):
        if isinstance(source_code, unicode):
            source_code = source_code.encode('utf-8')
        self.source_code = source_code
        try:
            ast_node = ast.parse(source_code.rstrip(' \t'))
        except SyntaxError, e:
            ignore = pycore.project.prefs.get('ignore_syntax_errors', False)
            if force_errors or not ignore:
                filename = 'string'
                if resource:
                    filename = resource.path
                raise exceptions.ModuleSyntaxError(filename, e.lineno, e.msg)
            else:
                ast_node = ast.parse('\n')
        self.star_imports = []
        self.defineds = None
        super(PyModule, self).__init__(pycore, ast_node, resource)

    def _get_defined_objects(self):
        if self.defineds is None:
            self._get_structural_attributes()
        return self.defineds

    def _create_concluded_attributes(self):
        result = {}
        for star_import in self.star_imports:
            result.update(star_import.get_names())
        return result

    def _create_structural_attributes(self):
        visitor = _GlobalVisitor(self.pycore, self)
        ast.walk(self.ast_node, visitor)
        self.defineds = visitor.defineds
        return visitor.names

    def _create_scope(self):
        return rope.base.pyscopes.GlobalScope(self.pycore, self)

    _lines = None
    @property
    def lines(self):
        """return a `SourceLinesAdapter`"""
        if self._lines is None:
            self._lines = rope.base.codeanalyze.\
                          SourceLinesAdapter(self.source_code)
        return self._lines

    _logical_lines = None
    @property
    def logical_lines(self):
        """return a `LogicalLinesFinder`"""
        if self._logical_lines is None:
            self._logical_lines = \
                rope.base.codeanalyze.CachingLogicalLineFinder(self.lines)
        return self._logical_lines


class PyPackage(pyobjects.PyPackage):

    def __init__(self, pycore, resource=None):
        self.resource = resource
        if resource is not None and resource.has_child('__init__.py'):
            ast_node = pycore.resource_to_pyobject(
                resource.get_child('__init__.py')).get_ast()
        else:
            ast_node = ast.parse('\n')
        super(PyPackage, self).__init__(pycore, ast_node, resource)

    def _create_structural_attributes(self):
        result = {}
        if self.resource is None:
            return result
        for name, resource in self._get_child_resources().items():
            result[name] = pynames.ImportedModule(self, resource=resource)
        return result

    def _create_concluded_attributes(self):
        result = {}
        init_dot_py = self._get_init_dot_py()
        if init_dot_py:
            init_object = self.pycore.resource_to_pyobject(init_dot_py)
            result.update(init_object.get_attributes())
        return result

    def _get_child_resources(self):
        result = {}
        for child in self.resource.get_children():
            if child.is_folder():
                result[child.name] = child
            elif child.name.endswith('.py') and \
                 child.name != '__init__.py':
                name = child.name[:-3]
                result[name] = child
        return result

    def _get_init_dot_py(self):
        if self.resource is not None and self.resource.has_child('__init__.py'):
            return self.resource.get_child('__init__.py')
        else:
            return None

    def _create_scope(self):
        return self.get_module().get_scope()

    def get_module(self):
        init_dot_py = self._get_init_dot_py()
        if init_dot_py:
            return self.pycore.resource_to_pyobject(init_dot_py)
        return self


class _AssignVisitor(object):

    def __init__(self, scope_visitor):
        self.scope_visitor = scope_visitor
        self.assigned_ast = None

    def _Assign(self, node):
        self.assigned_ast = node.value
        for child_node in node.targets:
            ast.walk(child_node, self)

    def _assigned(self, name, assignment=None):
        old_pyname = self.scope_visitor.names.get(name, None)
        if not isinstance(old_pyname, pynames.AssignedName):
            self.scope_visitor.names[name] = pynames.AssignedName(
                module=self.scope_visitor.get_module())
        if assignment is not None:
            self.scope_visitor.names[name].assignments.append(assignment)

    def _Name(self, node):
        assignment = None
        if self.assigned_ast is not None:
            assignment = pynames._Assigned(self.assigned_ast)
        self._assigned(node.id, assignment)

    def _Tuple(self, node):
        names = astutils.get_name_levels(node)
        for name, levels in names:
            assignment = None
            if self.assigned_ast is not None:
                assignment = pynames._Assigned(self.assigned_ast, levels)
            self._assigned(name, assignment)

    def _Attribute(self, node):
        pass

    def _Subscript(self, node):
        pass

    def _Slice(self, node):
        pass


class _ScopeVisitor(object):

    def __init__(self, pycore, owner_object):
        self.pycore = pycore
        self.owner_object = owner_object
        self.names = {}
        self.defineds = []

    def get_module(self):
        if self.owner_object is not None:
            return self.owner_object.get_module()
        else:
            return None

    def _ClassDef(self, node):
        pyclass = PyClass(self.pycore, node, self.owner_object)
        self.names[node.name] = pynames.DefinedName(pyclass)
        self.defineds.append(pyclass)

    def _FunctionDef(self, node):
        pyfunction = PyFunction(self.pycore, node, self.owner_object)
        self.names[node.name] = pynames.DefinedName(pyfunction)
        self.defineds.append(pyfunction)

    def _Assign(self, node):
        ast.walk(node, _AssignVisitor(self))

    def _For(self, node):
        names = rope.base.evaluate._get_evaluated_names(
            node.target, node.iter, evaluation='.__iter__().next()',
            lineno=node.lineno, module=self.get_module())
        self.names.update(names)
        for child in node.body + node.orelse:
            ast.walk(child, self)

    def _With(self, node):
        # ???: What if there are no optional vars?
        names = rope.base.evaluate._get_evaluated_names(
            node.optional_vars, node.context_expr, evaluation='.__enter__()',
            lineno=node.lineno, module=self.get_module())
        self.names.update(names)
        for child in node.body:
            ast.walk(child, self)

    def _Import(self, node):
        for import_pair in node.names:
            module_name = import_pair.name
            alias = import_pair.asname
            first_package = module_name.split('.')[0]
            if alias is not None:
                self.names[alias] = \
                    pynames.ImportedModule(self.get_module(), module_name)
            else:
                self.names[first_package] = \
                    pynames.ImportedModule(self.get_module(), first_package)

    def _ImportFrom(self, node):
        level = 0
        if node.level:
            level = node.level
        imported_module = pynames.ImportedModule(self.get_module(),
                                                 node.module, level)
        if len(node.names) == 1 and node.names[0].name == '*':
            self.owner_object.star_imports.append(
                pynames.StarImport(imported_module))
        else:
            for imported_name in node.names:
                imported = imported_name.name
                alias = imported_name.asname
                if alias is not None:
                    imported = alias
                self.names[imported] = pynames.ImportedName(imported_module,
                                                            imported_name.name)

    def _Global(self, node):
        module = self.get_module()
        for name in node.names:
            if module is not None:
                try:
                    pyname = module.get_attribute(name)
                except exceptions.AttributeNotFoundError:
                    pyname = pynames.AssignedName(node.lineno)
            self.names[name] = pyname


class _GlobalVisitor(_ScopeVisitor):

    def __init__(self, pycore, owner_object):
        super(_GlobalVisitor, self).__init__(pycore, owner_object)


class _ClassVisitor(_ScopeVisitor):

    def __init__(self, pycore, owner_object):
        super(_ClassVisitor, self).__init__(pycore, owner_object)

    def _FunctionDef(self, node):
        pyfunction = PyFunction(self.pycore, node, self.owner_object)
        self.names[node.name] = pynames.DefinedName(pyfunction)
        self.defineds.append(pyfunction)
        if len(node.args.args) > 0:
            first = node.args.args[0]
            if isinstance(first, ast.Name):
                new_visitor = _ClassInitVisitor(self, first.id)
                for child in ast.get_child_nodes(node):
                    ast.walk(child, new_visitor)

    def _ClassDef(self, node):
        pyclass = PyClass(self.pycore, node, self.owner_object)
        self.names[node.name] = pynames.DefinedName(pyclass)
        self.defineds.append(pyclass)


class _FunctionVisitor(_ScopeVisitor):

    def __init__(self, pycore, owner_object):
        super(_FunctionVisitor, self).__init__(pycore, owner_object)
        self.returned_asts = []
        self.generator = False

    def _Return(self, node):
        if node.value is not None:
            self.returned_asts.append(node.value)

    def _Yield(self, node):
        if node.value is not None:
            self.returned_asts.append(node.value)
        self.generator = True


class _ClassInitVisitor(_AssignVisitor):

    def __init__(self, scope_visitor, self_name):
        super(_ClassInitVisitor, self).__init__(scope_visitor)
        self.self_name = self_name

    def _Attribute(self, node):
        if not isinstance(node.ctx, ast.Store):
            return
        if isinstance(node.value, ast.Name) and \
           node.value.id == self.self_name:
            if node.attr not in self.scope_visitor.names:
                self.scope_visitor.names[node.attr] = pynames.AssignedName(
                    lineno=node.lineno, module=self.scope_visitor.get_module())
            self.scope_visitor.names[node.attr].assignments.append(
                pynames._Assigned(self.assigned_ast))

    def _Tuple(self, node):
        if not isinstance(node.ctx, ast.Store):
            return
        for child in ast.get_child_nodes(node):
            ast.walk(child, self)

    def _Name(self, node):
        pass

    def _FunctionDef(self, node):
        pass

    def _ClassDef(self, node):
        pass

    def _For(self, node):
        pass

    def _With(self, node):
        pass

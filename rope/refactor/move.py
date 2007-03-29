"""A module containing classes for move refactoring

`create_move()` is a factory for creating move refactoring objects
based on inputs.

"""
from rope.base import pyobjects, codeanalyze, exceptions, pynames
from rope.base.change import ChangeSet, ChangeContents, MoveResource
from rope.refactor import (importutils, rename, occurrences,
                           sourceutils, functionutils, inline)


def create_move(project, resource, offset=None):
    """A factory for creating Move objects

    Based on `resource` and `offset`, return one of `MoveModule`,
    `MoveGlobal` or `MoveMethod` for performing move refactoring.

    """
    if offset is None:
        return MoveModule(project, resource)
    pyname = codeanalyze.get_pyname_at(project.pycore, resource, offset)
    if pyname is None:
        raise exceptions.RefactoringError(
            'Move only works on classes, functions, modules and methods.')
    pyobject = pyname.get_object()
    if isinstance(pyobject, pyobjects.PyModule) or \
       isinstance(pyobject, pyobjects.PyPackage):
        return MoveModule(project, pyobject.get_resource())
    if isinstance(pyobject, pyobjects.PyFunction) and \
       isinstance(pyobject.parent, pyobjects.PyClass):
        return MoveMethod(project, resource, offset)
    if isinstance(pyobject, pyobjects.PyDefinedObject) and \
       isinstance(pyobject.parent, pyobjects.PyModule):
        return MoveGlobal(project, resource, offset)
    raise exceptions.RefactoringError(
        'Move only works on global classes/functions, modules and methods.')


class MoveMethod(object):
    """For moving methods

    It makes a new method in the destination class and changes
    the body of the old method to call the new method.  You can
    inline the old method to change all of its occurrences.

    """

    def __init__(self, project, resource, offset):
        self.pycore = project.pycore
        pyname = codeanalyze.get_pyname_at(project.pycore, resource, offset)
        self.method_name = codeanalyze.get_name_at(resource, offset)
        self.pyfunction = pyname.get_object()

    def get_changes(self, dest_attr, new_name):
        """Return the changes needed for this refactoring

        :parameters:
            - `dest_attr`: the name of the destination attribute
            - `new_name`: the name of the new method

        """
        changes = ChangeSet('Moving method <%s>' % self.method_name)
        resource1, start1, end1, new_content1 = \
            self._get_changes_made_by_old_class(dest_attr, new_name)
        collector1 = sourceutils.ChangeCollector(resource1.read())
        collector1.add_change(start1, end1, new_content1)

        resource2, start2, end2, new_content2 = \
            self._get_changes_made_by_new_class(dest_attr, new_name)
        if resource1 == resource2:
            collector1.add_change(start2, end2, new_content2)
        else:
            collector2 = sourceutils.ChangeCollector(resource2.read())
            collector2.add_change(start2, end2, new_content2)
            result = collector2.get_changed()
            import_tools = importutils.ImportTools(self.pycore)
            new_imports = self._get_used_imports(import_tools)
            if new_imports:
                goal_pymodule = self.pycore.get_string_module(result, resource2)
                result = _add_imports_to_module(import_tools, goal_pymodule,
                                                new_imports)
            changes.add_change(ChangeContents(resource2, result))

        changes.add_change(ChangeContents(resource1,
                                          collector1.get_changed()))
        return changes

    def get_method_name(self):
        return self.method_name

    def _get_used_imports(self, import_tools):
        module_imports = import_tools.get_module_imports(
            self.pyfunction.get_module())
        return module_imports.get_used_imports(self.pyfunction)

    def _get_changes_made_by_old_class(self, dest_attr, new_name):
        pymodule = self.pyfunction.get_module()
        indents = sourceutils.get_indents(
            pymodule.lines, self.pyfunction.get_scope().get_start())
        body = 'return self.%s.%s(%s)\n' % (dest_attr, new_name,
                                            self._get_passed_arguments_string())
        region = sourceutils.get_body_region(self.pyfunction)
        return (pymodule.get_resource(), region[0], region[1],
                sourceutils.fix_indentation(body, indents + 4))

    def _get_changes_made_by_new_class(self, dest_attr, new_name):
        old_pyclass = self.pyfunction.parent
        if dest_attr not in old_pyclass.get_attributes():
            raise exceptions.RefactoringError(
                'Destination attribute <%s> not found' % dest_attr)
        pyclass = old_pyclass.get_attribute(dest_attr).get_object().get_type()
        if not isinstance(pyclass, pyobjects.PyClass):
            raise exceptions.RefactoringError(
                'Unknown class type for attribute <%s>' % dest_attr)
        pymodule = pyclass.get_module()
        resource = pyclass.get_module().get_resource()
        start, end = sourceutils.get_body_region(pyclass)
        pre_blanks = '\n'
        if pymodule.source_code[start:end].strip() != 'pass':
            pre_blanks = '\n\n'
            start = end
        indents = sourceutils.get_indents(pymodule.lines,
                                          pyclass.get_scope().get_start())
        body = pre_blanks + sourceutils.fix_indentation(
            self.get_new_method(new_name), indents + 4)
        return resource, start, end, body

    def get_new_method(self, name):
        return '%s\n%s' % (
            self._get_new_header(name),
            sourceutils.fix_indentation(self._get_body(), 4))

    def _get_unchanged_body(self):
        return sourceutils.get_body(self.pyfunction)

    def _get_body(self, host='host'):
        self_name = self._get_self_name()
        body = self_name + ' = None\n' + self._get_unchanged_body()
        pymodule = self.pycore.get_string_module(body)
        finder = occurrences.FilteredFinder(
            self.pycore, self_name, [pymodule.get_attribute(self_name)])
        result = rename.rename_in_module(finder, host, pymodule=pymodule)
        if result is None:
            result = body
        return result[result.index('\n') + 1:]

    def _get_self_name(self):
        return self.pyfunction.get_param_names()[0]

    def _get_new_header(self, name):
        header = 'def %s(self' % name
        if self._is_host_used():
            header += ', host'
        definition_info = functionutils.DefinitionInfo.read(self.pyfunction)
        others = definition_info.arguments_to_string(1)
        if others:
            header += ', ' + others
        return header + '):'

    def _get_passed_arguments_string(self):
        result = ''
        if self._is_host_used():
            result = 'self'
        definition_info = functionutils.DefinitionInfo.read(self.pyfunction)
        others = definition_info.arguments_to_string(1)
        if others:
            result += ', ' + others
        return result

    def _is_host_used(self):
        return self._get_body('__old_self') != self._get_unchanged_body()


class _Mover(object):

    def __init__(self, pycore, source, pyname, old_name):
        self.pycore = pycore
        self.source = source
        self.old_pyname = pyname
        self.old_name = old_name
        self.import_tools = importutils.ImportTools(self.pycore)
        self._check_exceptional_conditions()

    def _check_exceptional_conditions(self):
        pass

    def _remove_old_pyname_imports(self, pymodule):
        old_source = pymodule.source_code
        module_with_imports = self.import_tools.get_module_imports(pymodule)
        class CanSelect(object):
            changed = False
            old_name = self.old_name
            old_pyname = self.old_pyname
            def __call__(self, name):
                try:
                    if name == self.old_name and \
                       pymodule.get_attribute(name).get_object() == \
                       self.old_pyname.get_object():
                        self.changed = True
                        return False
                except exceptions.AttributeNotFoundError:
                    pass
                return True
        can_select = CanSelect()
        module_with_imports.filter_names(can_select)
        new_source = module_with_imports.get_changed_source()
        if old_source != new_source:
            pymodule = self.pycore.get_string_module(new_source,
                                                     pymodule.get_resource())
        return pymodule, can_select.changed

    def _rename_in_module(self, pymodule, new_name, imports=False,
                          skipstart=None, skipend=None, skiptext=''):
        occurrence_finder = occurrences.FilteredFinder(
            self.pycore, self.old_name, [self.old_pyname], imports=imports)
        source = rename.rename_in_module(occurrence_finder, new_name,
                                         pymodule=pymodule, replace_primary=True)
        if source is None:
            return pymodule, False
        else:
            return self.pycore.get_string_module(source, pymodule.get_resource()), True

    def get_changes(self, dest):
        raise NotImplementedError()


class MoveGlobal(_Mover):
    """For moving global function and classes"""

    def __init__(self, project, resource, offset):
        pycore = project.pycore
        pyname = codeanalyze.get_pyname_at(pycore, resource, offset)
        old_name = pyname.get_object().get_name()
        pymodule = pyname.get_object().get_module()
        source = pymodule.get_resource()

        super(MoveGlobal, self).__init__(pycore, source, pyname, old_name)
        scope = pyname.get_object().get_scope()

    def _check_exceptional_conditions(self):
        if self.old_pyname is None or \
           not isinstance(self.old_pyname.get_object(), pyobjects.PyDefinedObject):
            raise exceptions.RefactoringError(
                'Move refactoring should be performed on a class/function.')
        moving_pyobject = self.old_pyname.get_object()
        if not self._is_global(moving_pyobject):
            raise exceptions.RefactoringError(
                'Move refactoring should be performed on a global class/function.')

    def _is_global(self, pyobject):
        return pyobject.get_scope().parent == pyobject.get_module().get_scope()

    def get_changes(self, dest):
        if dest.is_folder() and dest.has_child('__init__.py'):
            dest = dest.get_child('__init__.py')
        if dest.is_folder():
            raise exceptions.RefactoringError(
                'Move destination for non-modules should not be folders.')
        if self.source == dest:
            raise exceptions.RefactoringError(
                'Moving global elements to the same module.')
        changes = ChangeSet('Moving global <%s>' % self.old_name)
        self._change_destination_module(changes, dest)
        self._change_source_module(changes, dest)
        self._change_other_modules(changes, dest)
        return changes

    def _new_name(self, dest):
        return importutils.get_module_name(self.pycore, dest) + '.' + self.old_name

    def _new_import(self, dest):
        return self.import_tools.get_import_for_module(
            self.pycore.resource_to_pyobject(dest))

    def _change_source_module(self, changes, dest):
        handle = _ChangeMoveOccurrencesHandle(self._new_name(dest))
        occurrence_finder = occurrences.FilteredFinder(
            self.pycore, self.old_name, [self.old_pyname])
        start, end = self._get_moving_region()
        renamer = inline.ModuleSkipRenamer(occurrence_finder, self.source,
                                           handle, start, end)
        source = renamer.get_changed_module()
        if handle.occurred:
            pymodule = self.pycore.get_string_module(source, self.source)
            # Adding new import
            source = _add_imports_to_module(self.import_tools, pymodule,
                                            [self._new_import(dest)])
        changes.add_change(ChangeContents(self.source, source))

    def _change_destination_module(self, changes, dest):
        # Changing occurrences
        pymodule = self.pycore.resource_to_pyobject(dest)
        pymodule, has_changed = self._rename_in_module(pymodule, self.old_name)

        moving, imports = self._get_moving_element_with_imports()
        pymodule, has_changed = self._remove_old_pyname_imports(pymodule)
        pymodule, has_changed = self._add_imports_to_module2(pymodule, imports)

        module_with_imports = self.import_tools.get_module_imports(pymodule)
        source = pymodule.source_code
        if module_with_imports.get_import_statements():
            start = pymodule.lines.get_line_end(
                module_with_imports.get_import_statements()[-1].end_line - 1)
            result = source[:start + 1] + '\n\n'
        else:
            result = ''
            start = -1
        result += moving + source[start + 1:]

        # Organizing imports
        source = result
        pymodule = self.pycore.get_string_module(source, dest)
        source = self.import_tools.organize_imports(pymodule)
        changes.add_change(ChangeContents(dest, source))

    def _get_moving_element_with_imports(self):
        moving = self._get_moving_element()
        source_pymodule = self.pycore.resource_to_pyobject(self.source)
        new_imports = self._get_used_imports_by_the_moving_element()
        new_imports.append(self.import_tools.
                           get_from_import_for_module(source_pymodule, '*'))

        pymodule = self.pycore.get_string_module(moving, self.source)
        pymodule, has_changed = self._add_imports_to_module2(pymodule, new_imports)

        source = self.import_tools.relatives_to_absolutes(pymodule)
        if source is not None:
            pymodule = self.pycore.get_string_module(source, self.source)
        source = self.import_tools.froms_to_imports(pymodule)
        module_with_imports = self._get_module_with_imports(source, self.source)
        imports = [import_stmt.import_info
                   for import_stmt in module_with_imports.get_import_statements()]
        start = 1
        if module_with_imports.get_import_statements():
            start = module_with_imports.get_import_statements()[-1].end_line
        lines = codeanalyze.SourceLinesAdapter(source)
        moving = source[lines.get_line_start(start):]
        return moving, imports

    def _get_module_with_imports(self, source_code, resource):
        pymodule = self.pycore.get_string_module(source_code, resource)
        return self.import_tools.get_module_imports(pymodule)

    def _get_moving_element(self):
        start, end = self._get_moving_region()
        moving = self.source.read()[start:end]
        return moving.rstrip() + '\n'

    def _get_moving_region(self):
        pymodule = self.pycore.resource_to_pyobject(self.source)
        lines = pymodule.lines
        scope = self.old_pyname.get_object().get_scope()
        start = lines.get_line_start(scope.get_start())
        end_line = scope.get_end()
        for i in range(end_line + 1, lines.length()):
            if lines.get_line(i).strip() == '':
                end_line = i
            else:
                break
        end = min(lines.get_line_end(end_line) + 1, len(pymodule.source_code))
        return start, end

    def _get_used_imports_by_the_moving_element(self):
        pymodule = self.pycore.resource_to_pyobject(self.source)
        module_with_imports = self.import_tools.get_module_imports(pymodule)
        return module_with_imports.get_used_imports(self.old_pyname.get_object())

    def _change_other_modules(self, changes, dest):
        for file_ in self.pycore.get_python_files():
            if file_ in (self.source, dest):
                continue
            is_changed = False
            should_import = False
            pymodule = self.pycore.resource_to_pyobject(file_)
            # Changing occurrences
            pymodule, has_changed = self._rename_in_module(
                pymodule, self._new_name(dest))
            if has_changed:
                should_import = True
                is_changed = True
            # Removing out of date imports
            pymodule, has_changed = self._remove_old_pyname_imports(pymodule)
            if has_changed:
                is_changed = True
            # Adding new import
            if should_import:
                source = _add_imports_to_module(self.import_tools, pymodule,
                                                [self._new_import(dest)])
            if is_changed:
                changes.add_change(ChangeContents(file_, source))

    def _add_imports_to_module2(self, pymodule, new_imports):
        source = _add_imports_to_module(self.import_tools, pymodule,
                                        new_imports)
        if source is None:
            return pymodule, False
        else:
            return self.pycore.get_string_module(source, pymodule.get_resource()), True


class MoveModule(_Mover):
    """For moving modules and packages"""

    def __init__(self, project, resource):
        pycore = project.pycore
        if not resource.is_folder() and resource.name == '__init__.py':
            resource = resource.parent
        dummy_pymodule = pycore.get_string_module('')
        pyname = pynames.ImportedModule(
            dummy_pymodule, resource=resource)
        source = pyname.get_object().get_resource()
        if source.is_folder():
            old_name = source.name
        else:
            old_name = source.name[:-3]
        super(MoveModule, self).__init__(pycore, source, pyname, old_name)

    def get_changes(self, dest):
        moving_pyobject = self.old_pyname.get_object()
        if not dest.is_folder():
            raise exceptions.RefactoringError(
                'Move destination for modules should be packages.')
        changes = ChangeSet('Moving module <%s>' % self.old_name)
        self._change_other_modules(changes, dest)
        self._change_moving_module(changes, dest)
        return changes

    def _new_import(self, dest):
        return importutils.NormalImport([(self._new_name(dest), None)])

    def _new_name(self, dest):
        package = importutils.get_module_name(self.pycore, dest)
        if package:
            new_name = package + '.' + self.old_name
        else:
            new_name = self.old_name
        return new_name

    def _change_moving_module(self, changes, dest):
        if not self.source.is_folder():
            is_changed = False
            pymodule = self.pycore.resource_to_pyobject(self.source)
            source = self.import_tools.relatives_to_absolutes(pymodule)
            if source is not None:
                pymodule = self.pycore.get_string_module(source, self.source)
                is_changed = True
            source = self._change_occurrences_in_module(
                pymodule, self._new_import(dest), self._new_name(dest))
            if source is not None:
                is_changed = True
            else:
                source = pymodule.source_code
            if is_changed:
                changes.add_change(ChangeContents(self.source, source))
        changes.add_change(MoveResource(self.source, dest.path))

    def _change_other_modules(self, changes, dest):
        for module in self.pycore.get_python_files():
            if module in (self.source, dest):
                continue
            pymodule = self.pycore.resource_to_pyobject(module)
            source = self._change_occurrences_in_module(
                pymodule, self._new_import(dest), self._new_name(dest))
            if source is not None:
                changes.add_change(ChangeContents(module, source))

    def _change_occurrences_in_module(self, pymodule, new_import, new_name):
        is_changed = False
        should_import = False
        pymodule, has_changed = self._rename_in_module(pymodule, new_name,
                                                       imports=True)
        if has_changed:
            is_changed = True
        pymodule, has_changed = self._remove_old_pyname_imports(pymodule)
        if has_changed:
            should_import = True
            is_changed = True
        if should_import:
            source = _add_imports_to_module(self.import_tools, pymodule,
                                            [new_import])
        else:
            source = pymodule.source_code
        if is_changed:
            return source


def _add_imports_to_module(import_tools, pymodule, new_imports):
    module_with_imports = import_tools.get_module_imports(pymodule)
    for new_import in new_imports:
        module_with_imports.add_import(new_import)
    return module_with_imports.get_changed_source()


class _ChangeMoveOccurrencesHandle(object):

    def __init__(self, new_name):
        self.new_name = new_name
        self.occurred = False

    def occurred_inside_skip(self, change_collector, occurrence):
        pass

    def occurred_outside_skip(self, change_collector, occurrence):
        start, end = occurrence.get_primary_range()
        change_collector.add_change(start, end, self.new_name)
        self.occurred = True

import rope.codeanalyze
import rope.pyobjects
import rope.importutils
import rope.exceptions
from rope.refactor.change import (ChangeSet, ChangeFileContents,
                                  MoveResource, CreateFolder)


class MoveRefactoring(object):
    
    def __init__(self, pycore, resource, offset, dest_resource):
        self.pycore = pycore
        self.dest_resource = dest_resource
        if dest_resource.is_folder():
            self.dest_resource = dest_resource.get_child('__init__.py')
        self.old_pyname = rope.codeanalyze.get_pyname_at(self.pycore, resource, offset)
        
        self._check_exceptional_conditions()
        
        self.old_name = self.old_pyname.get_object()._get_ast().name
        self.pymodule = self.old_pyname.get_object().get_module()
        self.resource = self.pymodule.get_resource()
        self.import_tools = rope.importutils.ImportTools(self.pycore)
        self.new_import = self.import_tools.get_import_for_module(
            self.pycore.resource_to_pyobject(self.dest_resource))
        self.new_imported_name = self.new_import.names_and_aliases[0][0] + '.' + self.old_name

    def _check_exceptional_conditions(self):
        if self.old_pyname is None or \
           not isinstance(self.old_pyname.get_object(), rope.pyobjects.PyDefinedObject):
            raise rope.exceptions.RefactoringException(
                'Move refactoring should be performed on a class/function')
        if not self._is_global(self.old_pyname.get_object()):
            raise rope.exceptions.RefactoringException(
                'Move refactoring should be performed on a global class/function')
    
    def _is_global(self, pyobject):
        return pyobject.get_scope().parent == pyobject.get_module().get_scope()

    def move(self):
        changes = ChangeSet()
        self._change_destination_module(changes)
        self._change_source_module(changes)
        self._change_other_modules(changes)
        return changes
    
    def _change_source_module(self, changes):
        source = self.resource.read()
        uses_moving = False
        # Changing occurances
        pymodule = self.pycore.resource_to_pyobject(self.resource)
        source = self._rename_in_module(pymodule, self.new_imported_name)
        if source is None:
            source = pymodule.source_code
        else:
            uses_moving = True
        
        lines = rope.codeanalyze.SourceLinesAdapter(source)
        scope = self.old_pyname.get_object().get_scope()
        start = lines.get_line_start(scope.get_start())
        end = lines.get_line_end(scope.get_end())
        source = source[:start] + source[end + 1:]
        
        if uses_moving:
            pymodule = self.pycore.get_string_module(source, self.resource)
            # Adding new import
            source = self._add_imports_to_module(pymodule, [self.new_import])
        
        changes.add_change(ChangeFileContents(self.resource, source))
    
    def _change_destination_module(self, changes):
        source = self.dest_resource.read()
        # Changing occurances
        pymodule = self.pycore.resource_to_pyobject(self.dest_resource)
        source = self._rename_in_module(pymodule, self.old_name)
        if source is None:
            source = pymodule.source_code
        else:
            pymodule = self.pycore.get_string_module(source, self.dest_resource)
        
        module_with_imports = self.import_tools.get_module_with_imports(pymodule)
        def can_select(name):
            try:
                if name == self.old_name and \
                   pymodule.get_attribute(name).get_object() == self.old_pyname.get_object():
                    return False
            except rope.exceptions.AttributeNotFoundException:
                pass
            return True
        module_with_imports.filter_names(can_select)
        moving, imports = self._get_moving_element_with_imports()
        for import_info in imports:
            module_with_imports.add_import(import_info)
        source = module_with_imports.get_changed_source()
        
        pymodule = self.pycore.get_string_module(source, self.dest_resource)
        module_with_imports = self.import_tools.get_module_with_imports(pymodule)
        if module_with_imports.get_import_statements():
            lines = rope.codeanalyze.SourceLinesAdapter(source)
            start = lines.get_line_end(module_with_imports.
                                       get_import_statements()[-1].end_line - 1)
            result = source[:start + 1] + '\n\n'
        else:
            result = ''
            start = -1
        result += moving + '\n' + source[start + 1:]
        
        changes.add_change(ChangeFileContents(self.dest_resource, result))
    
    def _get_moving_element_with_imports(self):
        moving = self._get_moving_element()
        module_with_imports = self._get_module_with_imports(moving, self.resource)
        for import_info in self._get_used_imports_by_the_moving_element():
            module_with_imports.add_import(import_info)
        source_pymodule = self.pycore.resource_to_pyobject(self.resource)
        new_import = self.import_tools.get_from_import_for_module(source_pymodule, '*')
        module_with_imports.add_import(new_import)
        
        pymodule = self.pycore.get_string_module(
            module_with_imports.get_changed_source(), self.resource)
        source = self.import_tools.transform_relative_imports_to_absolute(pymodule)
        if source is not None:
            pymodule = self.pycore.get_string_module(source, self.resource)
        source = self.import_tools.transform_froms_to_normal_imports(pymodule)
        module_with_imports = self._get_module_with_imports(source, self.resource)
        imports = [import_stmt.import_info 
                   for import_stmt in module_with_imports.get_import_statements()]
        start = 1
        if imports:
            start = module_with_imports.get_import_statements()[-1].end_line
        lines = rope.codeanalyze.SourceLinesAdapter(source)
        moving = source[lines.get_line_start(start):]
        return moving, imports
    
    def _get_module_with_imports(self, source_code, resource):
        pymodule = self.pycore.get_string_module(source_code, resource)
        return self.import_tools.get_module_with_imports(pymodule)

    def _get_moving_element(self):
        lines = rope.codeanalyze.SourceLinesAdapter(self.resource.read())
        scope = self.old_pyname.get_object().get_scope()
        start = lines.get_line_start(scope.get_start())
        end = lines.get_line_end(scope.get_end())
        moving = self.resource.read()[start:end]
        return moving
        
    def _get_used_imports_by_the_moving_element(self):
        pymodule = self.pycore.resource_to_pyobject(self.resource)
        module_with_imports = self.import_tools.get_module_with_imports(pymodule)
        return module_with_imports.get_used_imports(self.old_pyname.get_object())
    
    def _change_other_modules(self, changes):
        for file_ in self.pycore.get_python_files():
            if file_ in (self.resource, self.dest_resource):
                continue
            # Changing occurances
            pymodule = self.pycore.resource_to_pyobject(file_)
            source = self._rename_in_module(pymodule, self.new_imported_name)
            if source is None:
                continue
            # Removing out of date imports
            pymodule = self.pycore.get_string_module(source, file_)
            source = self._remove_old_pyname_imports(pymodule)
            # Adding new import
            pymodule = self.pycore.get_string_module(source, file_)
            source = self._add_imports_to_module(pymodule, [self.new_import])
            
            changes.add_change(ChangeFileContents(file_, source))

    def _rename_in_module(self, pymodule, new_name):
        rename_in_module = rope.refactor.rename.RenameInModule(
            self.pycore, [self.old_pyname], self.old_name,
            new_name, replace_primary=True)
        return rename_in_module.get_changed_module(pymodule=pymodule)
    
    def _add_imports_to_module(self, pymodule, new_imports):
        module_with_imports = self.import_tools.get_module_with_imports(pymodule)
        for new_import in new_imports:
            module_with_imports.add_import(new_import)
        return module_with_imports.get_changed_source()
    
    def _remove_old_pyname_imports(self, pymodule):
        module_with_imports = self.import_tools.get_module_with_imports(pymodule)
        def can_select(name):
            try:
                if name == self.old_name and \
                   pymodule.get_attribute(name).get_object() == self.old_pyname.get_object():
                    return False
            except rope.exceptions.AttributeNotFoundException:
                pass
            return True
        module_with_imports.filter_names(can_select)
        return module_with_imports.get_changed_source()


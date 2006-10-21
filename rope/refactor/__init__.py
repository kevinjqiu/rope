import rope.importutils
from rope.refactor.change import (ChangeSet, ChangeFileContents,
                                  MoveResource, CreateFolder)
from rope.refactor.rename import RenameRefactoring
from rope.refactor.extract import ExtractMethodRefactoring
from rope.refactor.introduce_factory import IntroduceFactoryRefactoring
from rope.refactor.move import MoveRefactoring
from rope.refactor.inline import InlineRefactoring
from rope.refactor.encapsulate_field import EncapsulateFieldRefactoring
from rope.refactor.localtofield import ConvertLocalToFieldRefactoring


class PythonRefactoring(object):

    def __init__(self, pycore):
        self.pycore = pycore
        self._undo = Undo()

    def local_rename(self, resource, offset, new_name):
        changes = RenameRefactoring(self.pycore, resource, offset).\
                  local_rename(new_name)
        self.add_and_commit_changes(changes)
    
    def rename(self, resource, offset, new_name):
        changes = RenameRefactoring(self.pycore, resource, offset).\
                  rename(new_name)
        self.add_and_commit_changes(changes)
    
    def extract_method(self, resource, start_offset, end_offset,
                       extracted_name):
        changes = ExtractMethodRefactoring(self.pycore, resource,
                                           start_offset, end_offset).\
                                           extract_method(extracted_name)
        self.add_and_commit_changes(changes)
    
    def extract_variable(self, resource, start_offset, end_offset,
                         extracted_name):
        changes = ExtractMethodRefactoring(self.pycore, resource,
                                           start_offset, end_offset).\
                                           extract_variable(extracted_name)
        self.add_and_commit_changes(changes)
    
    def transform_module_to_package(self, resource):
        changes = ChangeSet()
        new_content = self._transform_relatives_to_absolute(resource)
        if new_content is not None:
            changes.add_change(ChangeFileContents(resource, new_content))
        parent = resource.get_parent()
        name = resource.get_name()[:-3]
        changes.add_change(CreateFolder(parent, name))
        new_path = parent.get_path() + '/%s/__init__.py' % name
        changes.add_change(MoveResource(resource, new_path))
        self.add_and_commit_changes(changes)
    
    def _transform_relatives_to_absolute(self, resource):
        pymodule = self.pycore.resource_to_pyobject(resource)
        import_tools = rope.importutils.ImportTools(self.pycore)
        return import_tools.transform_relative_imports_to_absolute(pymodule)
    
    def introduce_factory(self, resource, offset, factory_name, global_factory=False):
        factory_introducer = IntroduceFactoryRefactoring(self.pycore,
                                                         resource, offset)
        changes = factory_introducer.introduce_factory(factory_name,
                                                       global_factory)
        self.add_and_commit_changes(changes)
    
    def move(self, resource, offset, dest_resource):
        changes = MoveRefactoring(self.pycore, resource, offset).\
                  move(dest_resource)
        self.add_and_commit_changes(changes)
    
    def inline_local_variable(self, resource, offset):
        changes = InlineRefactoring(self.pycore, resource, offset).inline()
        self.add_and_commit_changes(changes)
    
    def encapsulate_field(self, resource, offset):
        changes = EncapsulateFieldRefactoring(self.pycore, resource, offset).\
                  encapsulate_field()
        self.add_and_commit_changes(changes)
    
    def convert_local_variable_to_field(self, resource, offset):
        changes = ConvertLocalToFieldRefactoring(self.pycore, resource, offset).\
                  convert_local_variable_to_field()
        self.add_and_commit_changes(changes)
        
    def add_and_commit_changes(self, changes):
        self._undo.add_change(changes)
        changes.do()
        
    def undo(self):
        self._undo.undo()
    
    def redo(self):
        self._undo.redo()

    def get_import_organizer(self):
        return ImportOrganizer(self)


class ImportOrganizer(object):
    
    def __init__(self, refactoring):
        self.refactoring = refactoring
        self.pycore = refactoring.pycore
        self.import_tools = rope.importutils.ImportTools(self.pycore)
    
    def _perform_command_on_module_with_imports(self, resource, method):
        pymodule = self.pycore.resource_to_pyobject(resource)
        module_with_imports = self.import_tools.get_module_with_imports(pymodule)
        method(module_with_imports)
        result = module_with_imports.get_changed_source()
        return result
    
    def organize_imports(self, resource):
        source = resource.read()
        pymodule = self.pycore.get_string_module(source, resource)
        module_with_imports = self.import_tools.get_module_with_imports(pymodule)
        module_with_imports.remove_unused_imports()
        module_with_imports.remove_duplicates()
        source = module_with_imports.get_changed_source()
        if source is not None:
            changes = ChangeSet()
            changes.add_change(ChangeFileContents(resource, source))
            self.refactoring.add_and_commit_changes(changes)

    def expand_star_imports(self, resource):
        source = self._perform_command_on_module_with_imports(
            resource, rope.importutils.ModuleWithImports.expand_stars)
        if source is not None:
            changes = ChangeSet()
            changes.add_change(ChangeFileContents(resource, source))
            self.refactoring.add_and_commit_changes(changes)

    def transform_froms_to_imports(self, resource):
        pymodule = self.pycore.resource_to_pyobject(resource)
        result = self.import_tools.transform_froms_to_normal_imports(pymodule)
        if result is not None:
            changes = ChangeSet()
            changes.add_change(ChangeFileContents(resource, result))
            self.refactoring.add_and_commit_changes(changes)

    def transform_relatives_to_absolute(self, resource):
        pymodule = self.pycore.resource_to_pyobject(resource)
        result = self.import_tools.transform_relative_imports_to_absolute(pymodule)
        if result is not None:
            changes = ChangeSet()
            changes.add_change(ChangeFileContents(resource, result))
            self.refactoring.add_and_commit_changes(changes)
    

class NoRefactoring(object):
    pass


class Undo(object):
    
    def __init__(self):
        self._undo_list = []
        self._redo_list = []
    
    def add_change(self, change):
        self._undo_list.append(change)
        del self._redo_list[:]
    
    def undo(self):
        change = self._undo_list.pop()
        self._redo_list.append(change)
        change.undo()
    
    def redo(self):
        change = self._redo_list.pop()
        self._undo_list.append(change)
        change.do()

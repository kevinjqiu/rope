import os
import re

import rope.base.project
from rope.base import exceptions


class PyObjectToTextual(object):

    def __init__(self, project):
        self.project = project

    def transform(self, pyobject):
        """Transform a `PyObject` to textual form"""
        if pyobject is None:
            return ('none',)
        object_type = type(pyobject)
        try:
            method = getattr(self, object_type.__name__ + '_to_textual')
            return method(pyobject)
        except AttributeError:
            return ('unknown',)

    def PyObject_to_textual(self, pyobject):
        if isinstance(pyobject.get_type(), rope.base.pyobjects.AbstractClass):
            result = self.transform(pyobject.get_type())
            if result[0] == 'defined':
                return ('instance', result)
            return result
        return ('unknown',)

    def PyFunction_to_textual(self, pyobject):
        return self._defined_to_textual(pyobject)

    def PyClass_to_textual(self, pyobject):
        return self._defined_to_textual(pyobject)

    def _defined_to_textual(self, pyobject):
        address = []
        while pyobject.parent is not None:
            address.insert(0, pyobject.get_name())
            pyobject = pyobject.parent
        return ('defined', self._get_pymodule_path(pyobject.get_module()),
                '.'.join(address))

    def PyModule_to_textual(self, pyobject):
        return ('defined', self._get_pymodule_path(pyobject))

    def PyPackage_to_textual(self, pyobject):
        return ('defined', self._get_pymodule_path(pyobject))

    def List_to_textual(self, pyobject):
        return ('builtin', 'list', self.transform(pyobject.holding))

    def Dict_to_textual(self, pyobject):
        return ('builtin', 'dict', self.transform(pyobject.keys),
                self.transform(pyobject.values))

    def Tuple_to_textual(self, pyobject):
        objects = [self.transform(holding) for holding in pyobject.get_holding_objects()]
        return tuple(['builtin', 'tuple'] + objects)

    def Set_to_textual(self, pyobject):
        return ('builtin', 'set', self.transform(pyobject.holding))

    def Iterator_to_textual(self, pyobject):
        return ('builtin', 'iter', self.transform(pyobject.holding))

    def Generator_to_textual(self, pyobject):
        return ('builtin', 'generator', self.transform(pyobject.holding))

    def Str_to_textual(self, pyobject):
        return ('builtin', 'str')

    def File_to_textual(self, pyobject):
        return ('builtin', 'file')

    def BuiltinFunction_to_textual(self, pyobject):
        return ('builtin', 'function', pyobject.get_name())

    def _get_pymodule_path(self, pymodule):
        resource = pymodule.get_resource()
        return resource.real_path


class TextualToPyObject(object):

    def __init__(self, project):
        self.project = project

    def transform(self, textual):
        """Transform an object from textual form to `PyObject`"""
        type = textual[0]
        try:
            method = getattr(self, type + '_to_pyobject')
            return method(textual)
        except AttributeError:
            return None

    def builtin_to_pyobject(self, textual):
        name = textual[1]
        method = getattr(self, 'builtin_%s_to_pyobject' % textual[1], None)
        if method is not None:
            return method(textual)

    def builtin_str_to_pyobject(self, textual):
        return rope.base.builtins.get_str()

    def builtin_list_to_pyobject(self, textual):
        holding = self.transform(textual[2])
        return rope.base.builtins.get_list(holding)

    def builtin_dict_to_pyobject(self, textual):
        keys = self.transform(textual[2])
        values = self.transform(textual[3])
        return rope.base.builtins.get_dict(keys, values)

    def builtin_tuple_to_pyobject(self, textual):
        objects = []
        for holding in textual[2:]:
            objects.append(self.transform(holding))
        return rope.base.builtins.get_tuple(*objects)

    def builtin_set_to_pyobject(self, textual):
        holding = self.transform(textual[2])
        return rope.base.builtins.get_set(holding)

    def builtin_iter_to_pyobject(self, textual):
        holding = self.transform(textual[2])
        return rope.base.builtins.get_iterator(holding)

    def builtin_generator_to_pyobject(self, textual):
        holding = self.transform(textual[2])
        return rope.base.builtins.get_generator(holding)

    def builtin_file_to_pyobject(self, textual):
        return rope.base.builtins.get_file()

    def builtin_function_to_pyobject(self, textual):
        if textual[2] in rope.base.builtins.builtins:
            return rope.base.builtins.builtins[textual[2]].get_object()

    def unknown_to_pyobject(self, textual):
        return None

    def none_to_pyobject(self, textual):
        return None

    def _module_to_pyobject(self, textual):
        path = textual[1]
        return self._get_pymodule(path)

    def _hierarchical_defined_to_pyobject(self, textual):
        path = textual[1]
        names = textual[2].split('.')
        pymodule = self._get_pymodule(path)
        pyobject = pymodule
        for name in names:
            if pyobject is None:
                return None
            if isinstance(pyobject, rope.base.pyobjects.PyDefinedObject):
                try:
                    pyobject = pyobject.get_scope().get_name(name).get_object()
                except exceptions.NameNotFoundError:
                    return None
            else:
                return None
        return pyobject

    def defined_to_pyobject(self, textual):
        if len(textual) == 2 or textual[2] == '':
            return self._module_to_pyobject(textual)
        else:
            return self._hierarchical_defined_to_pyobject(textual)

    def instance_to_pyobject(self, textual):
        type = self.transform(textual[1])
        if type is not None:
            return rope.base.pyobjects.PyObject(type)

    def _get_pymodule(self, path):
        resource = self.file_to_resource(path)
        if resource is not None:
            return self.project.get_pycore().resource_to_pyobject(resource)

    def file_to_resource(self, path):
        try:
            root = os.path.abspath(self.project.address)
            if path.startswith(root):
                relative_path = path[len(root):]
                if relative_path.startswith('/') or relative_path.startswith(os.sep):
                    relative_path = relative_path[1:]
                resource = self.project.get_resource(relative_path)
            else:
                resource = rope.base.project.get_no_project().get_resource(path)
            return resource
        except exceptions.RopeError:
            return None


class DOITextualToPyObject(TextualToPyObject):

    def _function_to_pyobject(self, textual):
        path = textual[1]
        lineno = int(textual[2])
        pymodule = self._get_pymodule(path)
        if pymodule is not None:
            scope = pymodule.get_scope()
            inner_scope = scope.get_inner_scope_for_line(lineno)
            return inner_scope.pyobject

    def _class_to_pyobject(self, textual):
        path, name = textual[1:]
        pymodule = self._get_pymodule(path)
        if pymodule is None:
            return None
        module_scope = pymodule.get_scope()
        suspected = None
        if name in module_scope.get_names():
            suspected = module_scope.get_name(name).get_object()
        if suspected is not None and \
           isinstance(suspected, rope.base.pyobjects.PyClass):
            return suspected
        else:
            lineno = self._find_occurrence(name, pymodule.get_resource().read())
            if lineno is not None:
                inner_scope = module_scope.get_inner_scope_for_line(lineno)
                return inner_scope.pyobject

    def defined_to_pyobject(self, textual):
        if len(textual) == 2:
            return self._module_to_pyobject(textual)
        else:
            if textual[2].isdigit():
                result = self._function_to_pyobject(textual)
            else:
                result = self._class_to_pyobject(textual)
            if not isinstance(result, rope.base.pyobjects.PyModule):
                return result

    def _find_occurrence(self, name, source):
        pattern = re.compile(r'^\s*class\s*' + name + r'\b')
        lines = source.split('\n')
        for i in range(len(lines)):
            if pattern.match(lines[i]):
                return i + 1
from rope.base import change, taskhandle, builtins, ast
from rope.refactor import patchedast, similarfinder, sourceutils
from rope.refactor.importutils import module_imports


class Restructure(object):
    """A class to perform python restructurings"""

    def __init__(self, project, pattern, goal):
        self.pycore = project.pycore
        self.pattern = pattern
        self.goal = goal
        self.template = similarfinder.CodeTemplate(self.goal)

    def get_changes(self, checks={}, imports=[],
                    task_handle=taskhandle.NullTaskHandle()):
        """Get the changes needed by this restructuring
        
        `checks` is the checks that should hold for changing an
        occurrence.  `imports` are the imports that should be added
        modules that have at least one occurrence.

        """
        changes = change.ChangeSet('Restructuring <%s> to <%s>' %
                                   (self.pattern, self.goal))
        files = self.pycore.get_python_files()
        job_set = task_handle.create_jobset('Collecting Changes', len(files))
        for resource in files:
            job_set.started_job('Working on <%s>' % resource.path)
            pymodule = self.pycore.resource_to_pyobject(resource)
            finder = similarfinder.CheckingFinder(pymodule, checks)
            computer = _ChangeComputer(pymodule, self.template,
                                       list(finder.get_matches(self.pattern)))
            result = computer.get_changed()
            if result is not None:
                imported_source = self._add_imports(resource, result, imports)
                changes.add_change(change.ChangeContents(resource,
                                                         imported_source))
            job_set.finished_job()
        return changes

    def _add_imports(self, resource, source, imports):
        if not imports:
            return source
        import_infos = self._get_import_infos(resource, imports)
        pymodule = self.pycore.get_string_module(source, resource)
        imports = module_imports.ModuleImports(self.pycore, pymodule)
        for import_info in import_infos:
            imports.add_import(import_info)
        return imports.get_changed_source()

    def _get_import_infos(self, resource, imports):
        pymodule = self.pycore.get_string_module('\n'.join(imports),
                                                 resource)
        imports = module_imports.ModuleImports(self.pycore, pymodule)
        return [imports.import_info
                for imports in imports.get_import_statements()]

    def make_checks(self, string_checks):
        """Convert str to str dicts to str to PyObject dicts

        This function is here to ease writing a UI.

        """
        checks = {}
        for key, value in string_checks.items():
            is_pyname = not key.endswith('.object') and \
                        not key.endswith('.type')
            evaluated = self._evaluate(value, is_pyname=is_pyname)
            if evaluated is not None:
                checks[key] = evaluated
        return checks

    def _evaluate(self, code, is_pyname=True):
        attributes = code.split('.')
        pyname = None
        if attributes[0] in ('__builtin__', '__builtins__'):
            class _BuiltinsStub(object):
                def get_attribute(self, name):
                    return builtins.builtins[name]
            pyobject = _BuiltinsStub()
        else:
            pyobject = self.pycore.get_module(attributes[0])
        for attribute in attributes[1:]:
            pyname = pyobject.get_attribute(attribute)
            if pyname is None:
                return None
            pyobject = pyname.get_object()
        return pyname if is_pyname else pyobject


class _ChangeComputer(object):

    def __init__(self, pymodule, goal, matches):
        self.pymodule = pymodule
        self.source = pymodule.source_code
        self.goal = goal
        self.matches = matches
        self.matched_asts = {}
        self._nearest_roots = {}
        if self._is_expression():
            for match in self.matches:
                self.matched_asts[match.ast] = match

    def get_changed(self):
        if self._is_expression():
            result = self._get_node_text(self.pymodule.get_ast())
            if result == self.source:
                return None
            return result
        else:
            collector = sourceutils.ChangeCollector(self.source)
            last_end = -1
            for match in self.matches:
                start, end = match.get_region()
                if start < last_end:
                    if not self._is_expression():
                        continue
                last_end = end
                replacement = self._get_matched_text(match)
                collector.add_change(start, end, replacement)
            return collector.get_changed()

    def _is_expression(self):
        return self.matches and isinstance(self.matches[0],
                                           similarfinder.ExpressionMatch)

    def _get_matched_text(self, match):
        mapping = {}
        for name in self.goal.get_names():
            node = match.get_ast(name)
            if node is None:
                raise similarfinder.BadNameInCheckError(
                    'Unknown name <%s>' % name)
            force = self._is_expression() and match.ast == node
            mapping[name] = self._get_node_text(node, force)
        unindented = self.goal.substitute(mapping)
        return self._auto_indent(match.get_region()[0], unindented)

    def _get_node_text(self, node, force=False):
        if not force and node in self.matched_asts:
            return self._get_matched_text(self.matched_asts[node])
        start, end = patchedast.node_region(node)
        main_text = self.source[start:end]
        collector = sourceutils.ChangeCollector(main_text)
        for node in self._get_nearest_roots(node):
            sub_start, sub_end = patchedast.node_region(node)
            collector.add_change(sub_start - start, sub_end - start,
                                 self._get_node_text(node))
        result = collector.get_changed()
        if result is None:
            return main_text
        return result

    def _auto_indent(self, offset, text):
        lineno = self.pymodule.lines.get_line_number(offset)
        indents = sourceutils.get_indents(self.pymodule.lines, lineno)
        result = []
        for index, line in enumerate(text.splitlines(True)):
            if index != 0 and line.strip():
                result.append(' ' * indents)
            result.append(line)
        return ''.join(result)

    def _get_nearest_roots(self, node):
        if node not in self._nearest_roots:
            result = []
            for child in ast.get_child_nodes(node):
                if child in self.matched_asts:
                    result.append(child)
                else:
                    result.extend(self._get_nearest_roots(child))
            self._nearest_roots[node] = result
        return self._nearest_roots[node]

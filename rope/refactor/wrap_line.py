from rope.base import codeanalyze
from rope.base.change import ChangeSet, ChangeContents


class WrapLine(object):
    def __init__(self, project, resource, offset=None):
        self.project = project
        self.pycore = project.pycore
        self.resource = resource
        self.indent_size = self.project.prefs.get('indent_size', 4)

    def get_changes(self, max_width=None):
        if max_width is None:
            max_width = self.project.prefs.get('max_line_width', 79)

        pymodule = self.pycore.resource_to_pyobject(self.resource)

        changes = ChangeSet('Wrap line')
        change_collector = codeanalyze.ChangeCollector(pymodule.source_code)

        for node in pymodule.get_ast().body:
            line = pymodule.lines.get_line(node.lineno)
            if len(line) <= max_width:
                continue

            method = 'wrap_%s' % node.__class__.__name__
            if hasattr(self, method):
                wrapped = getattr(self, method)(node, max_width)
                start = pymodule.lines.get_line_start(node.lineno)
                end = pymodule.lines.get_line_end(node.lineno)
                change_collector.add_change(start, end, wrapped)

        if change_collector.get_changed():
            changes.add_change(ChangeContents(
                self.resource, change_collector.get_changed()
            ))
        return changes

    def wrap_ImportFrom(self, node, max_width):
        names = node.names
        lines = ['from %s import (' % node.module]

        current_line = ' ' * self.indent_size

        while len(names) > 0:
            name = names.pop(0)
            segment = name.name
            if name.asname:
                segment += ' as %s' % name.asname
            if len(segment) > max_width \
                    or (len(current_line.strip()) == 0 and len(current_line + segment + ', ') > max_width):
                return
            segment = '%s, ' % segment

            if len(current_line + segment) < max_width:
                current_line += segment
            else:
                names.insert(0, name)
                lines.append(current_line.rstrip())
                current_line = ' ' * 4
        current_line = current_line.rsplit(', ', 1)[0] + ')'
        lines.append(current_line)

        return '\n'.join(lines)

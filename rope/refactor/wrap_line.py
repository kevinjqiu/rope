import _ast

from rope.base import codeanalyze
from rope.base.change import ChangeSet, ChangeContents


class WrapLine(object):
    def __init__(self, project, resource, offset=None):
        self.project = project
        self.pycore = project.pycore
        self.resource = resource

    def get_changes(self, max_width):
        pymodule = self.pycore.resource_to_pyobject(self.resource)
        # right now I'm only wrapping from imports
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

        changes.add_change(ChangeContents(
            self.resource, change_collector.get_changed()
        ))
        return changes

    def wrap_ImportFrom(self, node, max_width):
        return ''

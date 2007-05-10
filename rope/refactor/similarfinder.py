"""This module can be used for finding similar code"""
import compiler.ast
import re

from rope.base import codeanalyze
from rope.refactor import patchedast, sourceutils


class SimilarFinder(object):
    """A class for finding similar expressions and statements"""

    def __init__(self, source, start=0, end=None):
        self.source = source
        self.start = start
        self.end = len(self.source)
        if end is not None:
            self.end = end
        self.ast = patchedast.get_patched_ast(self.source)

    def get_matches(self, code):
        wanted = self._create_pattern(code)
        matches = _ASTMatcher(self.ast, wanted).find_matches()
        for match in matches:
            start, end = match.get_region()
            if self.start <= start and end <= self.end:
                yield match

    def get_match_regions(self, code):
        for match in self.get_matches(code):
            yield match.get_region()

    def _create_pattern(self, expression):
        expression = self._replace_wildcards(expression)
        ast = compiler.parse(expression)
        # Module.Stmt
        nodes = ast.node.nodes
        if len(nodes) == 1 and isinstance(nodes[0], compiler.ast.Discard):
            # Discard
            wanted = nodes[0].expr
        else:
            wanted = nodes
        return wanted

    def _replace_wildcards(self, expression):
        ropevar = _RopeVariable()
        template = _Template(expression)
        mapping = {}
        for name in template.get_names():
            if name.startswith('?'):
                mapping[name] = ropevar.get_any(name)
            else:
                mapping[name] = ropevar.get_normal(name)
        return template.substitute(mapping)


class _ASTMatcher(object):

    def __init__(self, body, pattern):
        """Searches the given pattern in the body AST.

        body is an AST node and pattern can be either an AST node or
        a list of ASTs nodes
        """
        self.body = body
        self.pattern = pattern
        self.matches = None
        self.ropevar = _RopeVariable()

    def find_matches(self):
        if self.matches is None:
            self.matches = []
            patchedast.call_for_nodes(self.body, self._check_node,
                                      recursive=True)
        return self.matches

    def _check_node(self, node):
        if isinstance(self.pattern, list):
            self._check_statements(node)
        else:
            self._check_expression(node)

    def _check_expression(self, node):
        mapping = {}
        if self._match_nodes(self.pattern, node, mapping):
            self.matches.append(ExpressionMatch(node, mapping))

    def _check_statements(self, node):
        if not isinstance(node, compiler.ast.Stmt):
            return
        for index in range(len(node.nodes)):
            if len(node.nodes) - index >= len(self.pattern):
                current_stmts = node.nodes[index:index + len(self.pattern)]
                mapping = {}
                if self._match_stmts(current_stmts, mapping):
                    self.matches.append(StatementMatch(current_stmts, mapping))

    def _match_nodes(self, expected, node, mapping):
        if isinstance(expected, compiler.ast.Name):
           if self.ropevar.is_normal(expected.name):
               return self._match_normal_var(expected, node, mapping)
           if self.ropevar.is_any(expected.name):
               return self._match_any_var(expected, node, mapping)
        if expected.__class__ != node.__class__:
            return False

        children1 = expected.getChildren()
        children2 = node.getChildren()
        if len(children1) != len(children2):
            return False
        for child1, child2 in zip(children1, children2):
            if isinstance(child1, compiler.ast.Node):
                if not self._match_nodes(child1, child2, mapping):
                    return False
            else:
                if child1 != child2:
                    return False
        return True

    def _match_stmts(self, current_stmts, mapping):
        if len(current_stmts) != len(self.pattern):
            return False
        for stmt, expected in zip(current_stmts, self.pattern):
            if not self._match_nodes(expected, stmt, mapping):
                return False
        return True

    def _match_normal_var(self, node1, node2, mapping):
        if isinstance(node2, compiler.ast.Name) and \
           self.ropevar.get_base(node1.name) == node2.name:
            mapping[self.ropevar.get_base(node1.name)] = node2
            return True
        return False

    def _match_any_var(self, node1, node2, mapping):
        name = self.ropevar.get_base(node1.name)
        if name not in mapping:
            mapping[name] = node2
            return True
        else:
            return self._match_nodes(mapping[name], node2, {})


class Match(object):

    def __init__(self, mapping):
        self.mapping = mapping

    def get_region(self):
        """Returns match region"""

    def get_ast(self, name):
        """The ast node that has matched rope variables"""
        return self.mapping.get(name, None)

class ExpressionMatch(Match):

    def __init__(self, ast, mapping):
        super(ExpressionMatch, self).__init__(mapping)
        self.ast = ast

    def get_region(self):
        return self.ast.region


class StatementMatch(Match):

    def __init__(self, ast_list, mapping):
        super(StatementMatch, self).__init__(mapping)
        self.ast_list = ast_list

    def get_region(self):
        return self.ast_list[0].region[0], self.ast_list[-1].region[1]


class _Template(object):

    def __init__(self, template):
        self.template = template
        self._find_names()

    def get_names(self):
        return self.names.keys()

    def _find_names(self):
        self.names = {}
        for match in _Template._get_pattern().finditer(self.template):
            if 'name' in match.groupdict() and \
               match.group('name') is not None:
                start, end = match.span('name')
                name = self.template[start + 2:end - 1]
                if name not in self.names:
                    self.names[name] = []
                self.names[name].append((start, end))

    @classmethod
    def _get_pattern(cls):
        if cls._match_pattern is None:
            pattern = codeanalyze.get_comment_pattern() + '|' + \
                      codeanalyze.get_string_pattern() + '|' + \
                      r'(?P<name>\$\{\S*\})'
            cls._match_pattern = re.compile(pattern)
        return cls._match_pattern

    _match_pattern = None

    def substitute(self, mapping):
        collector = sourceutils.ChangeCollector(self.template)
        for name, occurrences in self.names.items():
            for region in occurrences:
                collector.add_change(region[0], region[1], mapping[name])
        result = collector.get_changed()
        if result is None:
            return self.template
        return result


class _RopeVariable(object):
    """Transform and identify rope inserted wildcards"""

    _normal_prefix = '__rope__variable_normal_'
    _any_prefix = '__rope_variable_any_'

    def get_normal(self, name):
        return self._normal_prefix + name

    def get_any(self, name):
        return self._any_prefix + name[1:]

    def is_normal(self, name):
        return name.startswith(self._normal_prefix)

    def is_any(self, name):
        return name.startswith(self._any_prefix)

    def get_base(self, name):
        if self.is_normal(name):
            return name[len(self._normal_prefix):]
        if self.is_any(name):
            return '?' + name[len(self._any_prefix):]

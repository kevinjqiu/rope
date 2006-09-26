import compiler
import re

import rope.pyobjects
import rope.pynames
import rope.exceptions


class WordRangeFinder(object):

    def __init__(self, source_code):
        self.source_code = source_code
    
    def _find_word_start(self, offset):
        current_offset = offset
        while current_offset >= 0 and (self.source_code[current_offset].isalnum() or
                                       self.source_code[current_offset] in '_'):
            current_offset -= 1;
        return current_offset + 1
    
    def _find_word_end(self, offset):
        current_offset = offset + 1
        while current_offset < len(self.source_code) and \
              (self.source_code[current_offset].isalnum() or
               self.source_code[current_offset] in '_'):
            current_offset += 1;
        return current_offset - 1

    def _find_last_non_space_char(self, offset):
        if offset <= 0:
            return 0
        current_offset = offset
        while current_offset >= 0 and self.source_code[current_offset] in ' \t\n':
            while current_offset >= 0 and self.source_code[current_offset] in ' \t':
                current_offset -= 1
            if current_offset >= 0 and self.source_code[current_offset] == '\n':
                current_offset -= 1
                if current_offset >= 0 and self.source_code[current_offset] == '\\':
                    current_offset -= 1
        return current_offset
    
    def get_word_before(self, offset):
        return self.source_code[self._find_word_start(offset - 1):offset]
    
    def get_word_at(self, offset):
        return self.source_code[self._find_word_start(offset - 1):
                                self._find_word_end(offset - 1) + 1]
    
    def _find_string_start(self, offset):
        kind = self.source_code[offset]
        current_offset = offset - 1
        while self.source_code[current_offset] != kind:
            current_offset -= 1
        return current_offset
    
    def _find_parens_start(self, offset):
        current_offset = self._find_last_non_space_char(offset - 1)
        while current_offset >= 0 and self.source_code[current_offset] not in '[({':
            if self.source_code[current_offset] in ':,':
                pass
            else:
                current_offset = self._find_primary_start(current_offset)
            current_offset = self._find_last_non_space_char(current_offset - 1)
        return current_offset

    def _find_atom_start(self, offset):
        old_offset = offset
        if self.source_code[offset] in '\n\t ':
            offset = self._find_last_non_space_char(offset)
        if self.source_code[offset] in '\'"':
            return self._find_string_start(offset)
        if self.source_code[offset] in ')]}':
            return self._find_parens_start(offset)
        if self.source_code[offset].isalnum() or self.source_code[offset] == '_':
            return self._find_word_start(offset)
        return old_offset
    
    def _find_primary_without_dot_start(self, offset):
        last_parens = offset
        current_offset = self._find_last_non_space_char(offset)
        while current_offset > 0 and self.source_code[current_offset] in ')]}':
            last_parens = current_offset = self._find_parens_start(current_offset)
            current_offset = self._find_last_non_space_char(current_offset - 1)

        if current_offset > 0 and self.source_code[current_offset] in '\'"':
            return self._find_string_start(current_offset)
        elif current_offset > 0 and (self.source_code[current_offset].isalnum() or \
                                     self.source_code[current_offset] == '_'):
            return self._find_word_start(current_offset)
        return last_parens

    def _find_primary_start(self, offset):
        current_offset = offset + 1
        if self.source_code[offset] != '.':
            current_offset = self._find_primary_without_dot_start(offset)
        while current_offset > 0 and \
              self.source_code[self._find_last_non_space_char(current_offset - 1)] == '.':
            dot_position = self._find_last_non_space_char(current_offset - 1)
            current_offset = self._find_primary_without_dot_start(dot_position - 1)
            
            first_char = self.source_code[current_offset]
            if first_char != '_' and not first_char.isalnum():
                break

        return current_offset
    
    def get_primary_at(self, offset):
        return self.source_code[self._find_primary_start(offset - 1):
                                self._find_word_end(offset - 1) + 1].strip()

    def get_splitted_primary_before(self, offset):
        """returns expression, starting, starting_offset
        
        This function is used in `rope.codeassist.assist` function.
        """
        if offset == 0:
            return ('', '', 0)
        word_start = self._find_atom_start(offset - 1)
        real_start = self._find_primary_start(offset - 1)
        if self.source_code[word_start:offset].strip() == '':
            word_start = offset
        if self.source_code[real_start:offset].strip() == '':
            real_start = offset
        if real_start == word_start:
            return ('', self.source_code[word_start:offset], word_start)
        else:
            if self.source_code[offset - 1] == '.':
                return (self.source_code[real_start:offset - 1], '', offset)
            last_dot_position = word_start
            if self.source_code[word_start] != '.':
                last_dot_position = self._find_last_non_space_char(word_start - 1)
            last_char_position = self._find_last_non_space_char(last_dot_position - 1)
            return (self.source_code[real_start:last_char_position + 1],
                    self.source_code[word_start:offset], word_start)
    
    def _get_line_start(self, offset):
        while offset > 0 and self.source_code[offset] != '\n':
            offset -= 1
        return offset
    
    def _get_line_end(self, offset):
        while offset < len(self.source_code) and self.source_code[offset] != '\n':
            offset += 1
        return offset
    
    def _is_followed_by_equals(self, offset):
        while offset < len(self.source_code) and self.source_code[offset] in ' \\':
            if self.source_code[offset] == '\\':
                offset = self._get_line_end(offset)
            offset += 1
        if offset + 1 < len(self.source_code) and \
           self.source_code[offset] == '=' and self.source_code[offset + 1] != '=' :
            return True
        return False
    
    def is_name_assigned_here(self, offset):
        word_start = self._find_word_start(offset - 1)
        word_end = self._find_word_end(offset - 1) + 1
        if '.' in self.source_code[word_start:word_end]:
            return False
        line_start = self._get_line_start(word_start)
        line = self.source_code[line_start:word_start].strip()
        if line == '' and self._is_followed_by_equals(word_end):
            return True
        return False

    def is_a_class_or_function_name_in_header(self, offset):
        word_start = self._find_word_start(offset - 1)
        word_end = self._find_word_end(offset - 1) + 1
        line_start = self._get_line_start(word_start)
        prev_word = self.source_code[line_start:word_start].strip()
        return prev_word in ['def', 'class']
    
    def _find_first_non_space_char(self, offset):
        if offset >= len(self.source_code):
            return len(offset)
        current_offset = offset
        while current_offset < len(self.source_code) and\
              self.source_code[current_offset] in ' \t\n':
            while current_offset < len(self.source_code) and \
                  self.source_code[current_offset] in ' \t\n':
                current_offset += 1
            if current_offset + 1 < len(self.source_code) and self.source_code[current_offset] == '\\':
                current_offset += 2
        return current_offset
    
    def is_a_function_being_called(self, offset):
        word_start = self._find_word_start(offset - 1)
        word_end = self._find_word_end(offset - 1) + 1
        next_char = self._find_first_non_space_char(word_end)
        return not self.is_a_class_or_function_name_in_header(offset) and \
               next_char < len(self.source_code) and self.source_code[next_char] == '('
    
    def is_from_statement_module(self, offset):
        stmt_start = self._find_primary_start(offset)
        line_start = self._get_line_start(stmt_start)
        prev_word = self.source_code[line_start:stmt_start].strip()
        return prev_word == 'from'

    def is_a_name_after_from_import(self, offset):
        stmt_start = self._find_primary_start(offset)
        prev_word_start = self._find_word_start(stmt_start - 2)
        prev_word = self.source_code[prev_word_start:stmt_start].strip()
        if prev_word != 'import':
            return False
        prev_word_start2 = self._find_primary_start(prev_word_start - 2)
        prev_word_start3 = self._find_primary_start(prev_word_start2 - 2)
        prev_word3 = self.source_code[prev_word_start3:prev_word_start2].strip()
        line_start = self._get_line_start(prev_word_start3)
        till_line_start = self.source_code[line_start:prev_word_start3].strip()
        return prev_word3 == 'from' and till_line_start == ''


class StatementEvaluator(object):

    def __init__(self, scope):
        self.scope = scope
        self.result = None

    def visitName(self, node):
        self.result = self.scope.lookup(node.name)
    
    def visitGetattr(self, node):
        pyname = StatementEvaluator.get_statement_result(self.scope, node.expr)
        if pyname is not None:
            try:
                self.result = pyname.get_object().get_attribute(node.attrname)
            except rope.exceptions.AttributeNotFoundException:
                self.result = None

    def visitCallFunc(self, node):
        pyname = StatementEvaluator.get_statement_result(self.scope, node.node)
        if pyname is None:
            return
        pyobject = pyname.get_object()
        if pyobject.get_type() == rope.pyobjects.PyObject.get_base_type('Type'):
            self.result = rope.pynames.AssignedName(pyobject=rope.pyobjects.PyObject(type_=pyobject))
        elif pyobject.get_type() == rope.pyobjects.PyObject.get_base_type('Function'):
            self.result = rope.pynames.AssignedName(pyobject=pyobject._get_returned_object())
        elif '__call__' in pyobject.get_attributes():
            call_function = pyobject.get_attribute('__call__')
            self.result = rope.pynames.AssignedName(
                pyobject=call_function.get_object()._get_returned_object())
    
    def visitAdd(self, node):
        pass

    def visitAnd(self, node):
        pass

    def visitBackquote(self, node):
        pass

    def visitBitand(self, node):
        pass

    def visitBitor(self, node):
        pass

    def visitXor(self, node):
        pass

    def visitCompare(self, node):
        pass
    
    def visitDict(self, node):
        pass
    
    def visitFloorDiv(self, node):
        pass
    
    def visitList(self, node):
        pass
    
    def visitListComp(self, node):
        pass

    def visitMul(self, node):
        pass
    
    def visitNot(self, node):
        pass
    
    def visitOr(self, node):
        pass
    
    def visitPower(self, node):
        pass
    
    def visitRightShift(self, node):
        pass
    
    def visitLeftShift(self, node):
        pass
    
    def visitSlice(self, node):
        pass
    
    def visitSliceobj(self, node):
        pass
    
    def visitTuple(self, node):
        pass
    
    def visitSubscript(self, node):
        pass

    @staticmethod
    def get_statement_result(scope, node):
        evaluator = StatementEvaluator(scope)
        compiler.walk(node, evaluator)
        return evaluator.result


class ScopeNameFinder(object):
    
    def __init__(self, pymodule):
        self.source_code = pymodule.source_code
        self.module_scope = pymodule.get_scope()
        self.lines = self.source_code.split('\n')
        self.word_finder = WordRangeFinder(self.source_code)

    def _get_location(self, offset):
        lines = ArrayLinesAdapter(self.lines)
        current_pos = 0
        lineno = 1
        while current_pos + len(lines.get_line(lineno)) < offset:
            current_pos += len(lines.get_line(lineno)) + 1
            lineno += 1
        return (lineno, offset - current_pos)

    def _is_defined_in_class_body(self, holding_scope, offset, lineno):
        if lineno == holding_scope.get_start() and \
           holding_scope.parent is not None and \
           holding_scope.parent.pyobject.get_type() == rope.pyobjects.PyObject.get_base_type('Type') and \
           self.word_finder.is_a_class_or_function_name_in_header(offset):
            return True
        if lineno != holding_scope.get_start() and \
           holding_scope.pyobject.get_type() == rope.pyobjects.PyObject.get_base_type('Type') and \
           self.word_finder.is_name_assigned_here(offset):
            return True
        return False
    
    def _is_function_name_in_function_header(self, holding_scope, offset, lineno):
        if lineno == holding_scope.get_start() and \
           holding_scope.pyobject.get_type() == rope.pyobjects.PyObject.get_base_type('Function') and \
           self.word_finder.is_a_class_or_function_name_in_header(offset):
            return True
        return False

    def get_pyname_at(self, offset):
        lineno = self._get_location(offset)[0]
        holding_scope = self.module_scope.get_inner_scope_for_line(lineno)
        # class body
        if self._is_defined_in_class_body(holding_scope, offset, lineno):
            class_scope = holding_scope
            if lineno == holding_scope.get_start():
                class_scope = holding_scope.parent
            name = self.word_finder.get_primary_at(offset).strip()
            try:
                return class_scope.pyobject.get_attribute(name)
            except rope.exceptions.AttributeNotFoundException:
                return None
        if self._is_function_name_in_function_header(holding_scope, offset, lineno):
            name = self.word_finder.get_primary_at(offset).strip()
            return holding_scope.parent.get_name(name)
        if self.word_finder.is_from_statement_module(offset):
            module = self.word_finder.get_primary_at(offset)
            module_pyname = self._find_module(module)
            return module_pyname
        name = self.word_finder.get_primary_at(offset)
        result = self.get_pyname_in_scope(holding_scope, name)
        return result
    
    def _find_module(self, module_name):
        current_folder = None
        if self.module_scope.pyobject.get_resource():
            current_folder = self.module_scope.pyobject.get_resource().get_parent()
        dot_count = 0
        if module_name.startswith('.'):
            for c in module_name:
                if c == '.':
                    dot_count += 1
                else:
                    break
        return rope.pynames.ImportedModule(self.module_scope.pyobject,
                                           module_name[dot_count:], dot_count)

    def get_pyname_in_scope(self, holding_scope, name):
        ast = compiler.parse(name)
        result = StatementEvaluator.get_statement_result(holding_scope, ast)
        return result


def get_name_and_pyname_at(pycore, resource, offset):
    pymodule = pycore.resource_to_pyobject(resource)
    source_code = pymodule.source_code
    word_finder = rope.codeanalyze.WordRangeFinder(source_code)
    name = word_finder.get_primary_at(offset).split('.')[-1]
    pyname_finder = rope.codeanalyze.ScopeNameFinder(pymodule)
    pyname = pyname_finder.get_pyname_at(offset)
    return (name, pyname)


def get_pyname_at(pycore, resource, offset):
    pymodule = pycore.resource_to_pyobject(resource)
    source_code = pymodule.source_code
    pyname_finder = rope.codeanalyze.ScopeNameFinder(pymodule)
    pyname = pyname_finder.get_pyname_at(offset)
    return pyname


class Lines(object):

    def get_line(self, line_number):
        pass

    def length(self):
        pass


class SourceLinesAdapter(Lines):
    
    def __init__(self, source_code):
        self.source_code = source_code
        self.line_starts = None
        self._initialize_line_starts()
    
    def _initialize_line_starts(self):
        self.line_starts = []
        self.line_starts.append(0)
        for i, c in enumerate(self.source_code):
            if c == '\n':
                self.line_starts.append(i + 1)
        self.line_starts.append(len(self.source_code) + 1)
    
    def get_line(self, line_number):
        return self.source_code[self.line_starts[line_number - 1]:self.line_starts[line_number] - 1]
    
    def length(self):
        return len(self.line_starts) - 1

    def get_line_number(self, offset):
        down = 0
        up = len(self.line_starts)
        current = (down + up) / 2
        while down <= current < up:
            if self.line_starts[current] <= offset < self.line_starts[current + 1]:
                return current + 1
            if offset < self.line_starts[current]:
                up = current - 1
            else:
                down = current + 1
            current = (down + up) / 2
        return current + 1

    def get_line_start(self, line_number):
        return self.line_starts[line_number - 1]

    def get_line_end(self, line_number):
        return self.line_starts[line_number] - 1


class ArrayLinesAdapter(Lines):

    def __init__(self, lines):
        self.lines = lines
    
    def get_line(self, line_number):
        return self.lines[line_number - 1]
    
    def length(self):
        return len(self.lines)


class StatementRangeFinder(object):
    """A method object for finding the range of a statement"""

    def __init__(self, lines, lineno):
        self.lines = lines
        self.lineno = lineno
        self.in_string = ''
        self.open_parens = 0
        self.explicit_continuation = False
        self.parens_openings = []

    def _analyze_line(self, current_line_number):
        current_line = self.lines.get_line(current_line_number)
        for i, char in enumerate(current_line):
            if char in '\'"':
                if self.in_string == '':
                    self.in_string = char
                    if char * 3 == current_line[i:i + 3]:
                        self.in_string = char * 3
                elif self.in_string == current_line[i:i + len(self.in_string)] and \
                     not (i > 0 and current_line[i - 1] == '\\' and
                          not (i > 1 and current_line[i - 2:i] == '\\\\')):
                    self.in_string = ''
            if self.in_string != '':
                continue
            if char == '#':
                break
            if char in '([{':
                self.open_parens += 1
                self.parens_openings.append((current_line_number, i))
            if char in ')]}':
                self.open_parens -= 1
                if self.parens_openings:
                    self.parens_openings.pop()
        if current_line.rstrip().endswith('\\'):
            self.explicit_continuation = True
        else:
            self.explicit_continuation = False

    def _get_block_start(self):
        """Aproximating block start for `analyze` method"""
        pattern = StatementRangeFinder.get_block_start_patterns()
        for i in reversed(range(1, self.lineno + 1)):
            if pattern.search(self.lines.get_line(i)) is not None:
                return i
        return 1

    def analyze(self):
        last_statement = 1
        for current_line_number in range(self._get_block_start(), self.lineno + 1):
            if not self.explicit_continuation and self.open_parens == 0 and self.in_string == '':
                last_statement = current_line_number
            self._analyze_line(current_line_number)
        last_indents = self.get_line_indents(last_statement)
        end_line = self.lineno
        for i in range(self.lineno + 1, self.lines.length() + 1):
            if self.get_line_indents(i) >= last_indents:
                end_line = i
            else:
                break
        self.block_end = end_line
        self.statement_start = last_statement

    def get_statement_start(self):
        return self.statement_start

    def get_block_end(self):
        return self.block_end

    def last_open_parens(self):
        if not self.parens_openings:
            return None
        return self.parens_openings[-1]

    def is_line_continued(self):
        return self.open_parens != 0 or self.explicit_continuation

    def get_line_indents(self, line_number):
        indents = 0
        for char in self.lines.get_line(line_number):
            if char == ' ':
                indents += 1
            else:
                break
        return indents
    
    @classmethod
    def get_block_start_patterns(cls):
        if not hasattr(cls, '__block_start_pattern'):
            pattern = '^\\s*(def|class|if|else|elif|try|except|for|while|with)\\s'
            cls.__block_start_pattern = re.compile(pattern, re.M)
        return cls.__block_start_pattern


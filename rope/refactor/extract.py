import compiler

import rope.codeanalyze
import rope.pyobjects
from rope.exceptions import RefactoringException
from rope.refactor import sourcetools
from rope.refactor.change import ChangeSet, ChangeFileContents


class ExtractMethodRefactoring(object):
    
    def __init__(self, pycore):
        self.pycore = pycore
    
    def extract_method(self, resource, start_offset, end_offset,
                       extracted_name):
        new_contents = _ExtractMethodPerformer(self, resource, start_offset,
                                               end_offset, extracted_name).extract()
        changes = ChangeSet()
        changes.add_change(ChangeFileContents(resource, new_contents))
        return changes
        

class _ExtractMethodPerformer(object):
    """Perform extract method refactoring
    
    We devide program source code into these parts::
      ...[pre]
        scope_start
        start_line
          start
          end
        end_line
        scope_end
      ...[post]
    
    For extract function the new method is inserted in start_line,
    while in extract method it is inserted in scope_end.
    
    Note that start and end are in the same line for one line
    extractions, so start_line and end_line are in the same line
    two.

    """
    
    def __init__(self, refactoring, resource, start_offset,
                 end_offset, extracted_name):
        self.refactoring = refactoring
        source_code = resource.read()
        self.source_code = source_code
        self.extracted_name = extracted_name
        
        self.lines = rope.codeanalyze.SourceLinesAdapter(source_code)
        self.start = self._choose_closest_line_end(source_code, start_offset)
        self.end = self._choose_closest_line_end(source_code, end_offset)
        
        start_line = self.lines.get_line_number(self.start)
        end_line = self.lines.get_line_number(self.end)

        self.start_line = self.lines.get_line_start(start_line)
        self.end_line = self.lines.get_line_end(end_line)
                
        start_line = self.lines.get_line_number(start_offset)
        self.first_line_indents = self._get_indents(start_line)
        self.scope = self.refactoring.pycore.get_string_scope(source_code, resource)
        self.holding_scope = self.scope.get_inner_scope_for_line(start_line)
        if self.holding_scope.get_kind() != 'Module' and \
           self.holding_scope.get_start() == start_line:
            self.holding_scope = self.holding_scope.parent
        self.scope_start = self.lines.get_line_start(self.holding_scope.get_start())
        self.scope_end = self.lines.get_line_end(self.holding_scope.get_end()) + 1
        
        self.is_one_line = self._is_one_line_extract(start_line, end_line - 1)

        self.scope_indents = self._get_indents(self.holding_scope.get_start()) + 4
        if self._is_global():
            self.scope_indents = 0
        self._check_exceptional_conditions()
        self.info_collector = self._create_info_collector()
    
    def _is_one_line_extract(self, start_line, end_line):
        line_finder = rope.codeanalyze.LogicalLineFinder(self.lines)
        return self.start != self.start_line and \
               (line_finder.get_logical_line_in(start_line) == 
                line_finder.get_logical_line_in(end_line))

    def _is_global(self):
        return self.holding_scope.pyobject.get_type() == \
               rope.pyobjects.PyObject.get_base_type('Module')

    def _is_method(self):
        return self.holding_scope.parent is not None and \
               self.holding_scope.parent.pyobject.get_type() == \
               rope.pyobjects.PyObject.get_base_type('Type')
    
    def _check_exceptional_conditions(self):
        if self.holding_scope.pyobject.get_type() == rope.pyobjects.PyObject.get_base_type('Type'):
            raise RefactoringException('Can not extract methods in class body')
        if self.end > self.scope_end:
            raise RefactoringException('Bad range selected for extract method')
        end_line = self.lines.get_line_number(self.end - 1)
        end_scope = self.scope.get_inner_scope_for_line(end_line)
        if end_scope != self.holding_scope and end_scope.get_end() != end_line:
            raise RefactoringException('Bad range selected for extract method')
        if _ReturnOrYieldFinder.does_it_return(self.source_code[self.start:self.end]):
            raise RefactoringException('Extracted piece should not contain return statements')

    def _create_info_collector(self):
        zero = self.holding_scope.get_start() - 1
        start_line = self.lines.get_line_number(self.start) - zero
        end_line = self.lines.get_line_number(self.end) - 1 - zero
        info_collector = _FunctionInformationCollector(start_line, end_line,
                                                       self._is_global())
        indented_body = self.source_code[self.scope_start:self.scope_end]
        body = sourcetools.indent_lines(indented_body,
                                        -sourcetools.find_minimum_indents(indented_body))
        ast = compiler.parse(body)
        compiler.walk(ast, info_collector)
        return info_collector

    def extract(self):
        args = self._find_function_arguments()
        returns = self._find_function_returns()
        
        result = []
        result.append(self.source_code[:self.start_line])
        if self._is_global():
            result.append('\n%s\n' % self._get_function_definition())
        result.append(self.source_code[self.start_line:self.start])
        call = self._get_call(returns, args)
        result.append(call)
        result.append(self.source_code[self.end:self.end_line])
        result.append(self.source_code[self.end_line:self.scope_end])
        if not self._is_global():
            result.append('\n%s' % self._get_function_definition())
        result.append(self.source_code[self.scope_end:])
        return ''.join(result)

    def _get_call(self, returns, args):
        if self.is_one_line:
            ending = ''
            if self.end == self.end_line:
                ending = '\n'
            return self._get_function_call(args) + ending
        else:
            call_prefix = ''
            if returns:
                call_prefix = self._get_comma_form(returns) + ' = '
            return ' ' * self.first_line_indents + call_prefix \
                   + self._get_function_call(args) + '\n'
    
    def _get_function_definition(self):
        args = self._find_function_arguments()
        returns = self._find_function_returns()
        if not self._is_global():
            function_indents = self.scope_indents
        else:
            function_indents = 4
        result = []
        result.append('%sdef %s:\n' %
                      (' ' * self._get_indents(self.holding_scope.get_start()),
                       self._get_function_signature(args)))
        extracted_body = self.source_code[self.start:self.end]
        if self.is_one_line:
            lines = []
            for line in extracted_body.splitlines():
                if line.endswith('\\'):
                    lines.append(line[:-1].strip())
                else:
                    lines.append(line.strip())
            unindented_body = 'return ' + ' '.join(lines) + '\n'
        else:
            unindented_body = sourcetools.indent_lines(
                extracted_body, -sourcetools.find_minimum_indents(extracted_body))
            if returns:
                unindented_body += 'return %s\n' % self._get_comma_form(returns)
        function_body = sourcetools.indent_lines(unindented_body, function_indents)
        result.append(function_body)
        return ''.join(result)
    
    def _get_function_signature(self, args):
        args = list(args)
        if self._is_method():
            if 'self' in args:
                args.remove('self')
            args.insert(0, 'self')
        return self.extracted_name + '(%s)' % self._get_comma_form(args)
    
    def _get_function_call(self, args):
        prefix = ''
        if self._is_method():
            if  'self' in args:
                args.remove('self')
            prefix = 'self.'
        return prefix + '%s(%s)' % (self.extracted_name, self._get_comma_form(args))

    def _get_comma_form(self, names):
        result = ''
        if names:
            result += names[0]
            for name in names[1:]:
                result += ', ' + name
        return result
    
    def _find_function_arguments(self):
        return list(self.info_collector.prewritten.intersection(self.info_collector.read))
    
    def _find_function_returns(self):
        return list(self.info_collector.written.intersection(self.info_collector.postread))
        
    def _choose_closest_line_end(self, source_code, offset):
        lineno = self.lines.get_line_number(offset)
        line_start = self.lines.get_line_start(lineno)
        line_end = self.lines.get_line_end(lineno)
        if source_code[line_start:offset].strip() == '':
            return line_start
        elif source_code[offset:line_end].strip() == '':
            return min(line_end + 1, len(source_code))
        return offset
    
    def _get_indents(self, lineno):
        return sourcetools.get_indents(self.lines, lineno)
    

class _SingleLineExtractMethodPerformer(_ExtractMethodPerformer):
    pass
    
    
class _FunctionInformationCollector(object):
    
    def __init__(self, start, end, is_global):
        self.start = start
        self.end = end
        self.is_global = is_global
        self.prewritten = set()
        self.written = set()
        self.read = set()
        self.postread = set()
        self.host_function = True
    
    def _read_variable(self, name, lineno):
        if self.start <= lineno <= self.end:
            self.read.add(name)
        if self.end < lineno:
            self.postread.add(name)
    
    def _written_variable(self, name, lineno):
        if self.start <= lineno <= self.end:
            self.written.add(name)
        if self.start > lineno:
            self.prewritten.add(name)
        
    def visitFunction(self, node):
        if not self.is_global and self.host_function:
            self.host_function = False
            for name in node.argnames:
                self._written_variable(name, node.lineno)
            compiler.walk(node.code, self)
        else:
            self._written_variable(node.name, node.lineno)
            visitor = _VariableReadsAndWritesFinder()
            compiler.walk(node.code, visitor)
            for name in visitor.read - visitor.written:
                self._read_variable(name, node.lineno)

    def visitAssName(self, node):
        self._written_variable(node.name, node.lineno)
    
    def visitName(self, node):
        self._read_variable(node.name, node.lineno)
    
    def visitClass(self, node):
        self._written_variable(node.name, node.lineno)
    

class _VariableReadsAndWritesFinder(object):
    
    def __init__(self):
        self.written = set()
        self.read = set()
    
    def visitAssName(self, node):
        self.written.add(node.name)
    
    def visitName(self, node):
        self.read.add(node.name)
    
    def visitFunction(self, node):
        self.written.add(node.name)
        visitor = _VariableReadsAndWritesFinder()
        compiler.walk(node.code, visitor)
        self.read.update(visitor.read - visitor.written)

    def visitClass(self, node):
        self.written.add(node.name)
    
    @staticmethod
    def find_reads_and_writes(code):
        if code.strip() == '':
            return set(), set()
        min_indents = sourcetools.find_minimum_indents(code)
        indented_code = sourcetools.indent_lines(code, -min_indents)
        ast = compiler.parse(indented_code)
        visitor = _VariableReadsAndWritesFinder()
        compiler.walk(ast, visitor)
        return visitor.read, visitor.written


class _ReturnOrYieldFinder(object):
    
    def __init__(self):
        self.returns = False

    def visitReturn(self, node):
        self.returns = True

    def visitYield(self, node):
        self.returns = True

    def visitFunction(self, node):
        pass
    
    def visitClass(self, node):
        pass
    
    @staticmethod
    def does_it_return(code):
        if code.strip() == '':
            return False
        min_indents = sourcetools.find_minimum_indents(code)
        indented_code = sourcetools.indent_lines(code, -min_indents)
        ast = compiler.parse(indented_code)
        visitor = _ReturnOrYieldFinder()
        compiler.walk(ast, visitor)
        return visitor.returns


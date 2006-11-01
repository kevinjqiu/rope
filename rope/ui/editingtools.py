import rope.ui.indenter
import rope.ui.highlighter
import rope.ide.codeassist
import rope.ide.outline
import rope.refactor
import rope.ui.editingcontexts


def get_editingtools_for_context(name, project):
    if name == 'python':
        return PythonEditingTools(project)
    if name == 'rest':
        return ReSTEditingTools()
    return NormalEditingTools()


class EditingTools(object):

    def create_indenter(self, editor):
        pass

    def create_highlighting(self):
        pass    


class PythonEditingTools(EditingTools):

    def __init__(self, project):
        self.project = project
        self._code_assist = None
        self._outline = None

    def create_indenter(self, editor):
        return rope.ui.indenter.PythonCodeIndenter(editor)

    def create_highlighting(self):
        return rope.ui.highlighter.PythonHighlighting()
    
    def _get_code_assist(self):
        if self._code_assist is None:
            self._code_assist = rope.ide.codeassist.PythonCodeAssist(self.project)
        return self._code_assist

    def _get_outline(self):
        if self._outline is None:
            self._outline = rope.ide.outline.PythonOutline(self.project)
        return self._outline
    
    codeassist = property(_get_code_assist)
    outline = property(_get_outline)


class ReSTEditingTools(EditingTools):

    def __init__(self):
        pass

    def create_indenter(self, editor):
        return rope.ui.indenter.NormalIndenter(editor)

    def create_highlighting(self):
        return rope.ui.highlighter.ReSTHighlighting()
    

class NormalEditingTools(EditingTools):

    def __init__(self):
        pass

    def create_indenter(self, editor):
        return rope.ui.indenter.NormalIndenter(editor)

    def create_highlighting(self):
        return rope.ui.highlighter.NoHighlighting()
    

import os.path
import shutil
import sys

import rope.base.project


def sample_project(root=None, **kwds):
    if root is None:
        root = 'sample_project'
        # HACK: Using ``/dev/shm/`` for faster tests
        if os.name == 'posix' and os.path.isdir('/dev/shm'):
            root = '/dev/shm/' + root
    remove_recursively(root)
    return rope.base.project.Project(root, **kwds)


def remove_project(project):
    project.close()
    remove_recursively(project.address)


def remove_recursively(path):
    import time
    if os.name == 'nt':
        for i in range(12):
            try:
                _remove_recursively(path)
            except WindowsError:
                time.sleep(0.3)
            else:
                break
    else:
        _remove_recursively(path)

def _remove_recursively(path):
    if not os.path.exists(path):
        return
    if os.path.isfile(path):
        os.remove(path)
    else:
        shutil.rmtree(path)

def run_only_for_25(func):
    """Should be used as a decorator for a unittest.TestCase test method"""
    if sys.version_info >= (2, 5, 0):
        return func
    else:
        def do_nothing(self):
            pass
        return do_nothing


def assert_raises(exception_class):
    """Should be used as a decorator for a unittest.TestCase test method"""
    def _assert_raises(func):
        def call_func(self, *args, **kws):
            self.assertRaises(exception_class, func, self, *args, **kws)
        return call_func
    return _assert_raises

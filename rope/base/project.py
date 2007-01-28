import os

import rope.base.change
import rope.base.fscommands
import rope.base.history
import rope.base.pycore
from rope.base.exceptions import RopeError


class _Project(object):

    def __init__(self, fscommands):
        self.observers = set()
        self.file_access = rope.base.fscommands.FileAccess()
        self._history = rope.base.history.History(maxundos=100)
        self.operations = rope.base.change._ResourceOperations(self, fscommands)

    def get_resource(self, resource_name):
        """Get a resource in a project.

        `resource_name` is the path of a resource in a project.  It
        is the path of a resource relative to project root.  Project
        root folder address is an empty string.

        """
        path = self._get_resource_path(resource_name)
        if not os.path.exists(path):
            raise RopeError('Resource %s does not exist' % resource_name)
        elif os.path.isfile(path):
            return File(self, resource_name)
        elif os.path.isdir(path):
            return Folder(self, resource_name)
        else:
            raise RopeError('Unknown resource ' + resource_name)

    def validate(self, folder):
        """Validate files and folders contained in this folder

        This method asks all registered to validate all of the files
        and folders contained in this folder that they are interested
        in.

        """
        for observer in list(self.observers):
            observer.validate(folder)

    def add_observer(self, observer):
        """Register a `ResourceObserver`

        See `FilteredResourceObserver`.
        """
        self.observers.add(observer)

    def remove_observer(self, observer):
        """Remove a registered `ResourceObserver`"""
        if observer in self.observers:
            self.observers.remove(observer)

    def _get_resource_path(self, name):
        pass

    history = property(lambda self: self._history)


class Project(_Project):
    """A Project containing files and folders"""

    def __init__(self, project_root, fscommands=None):
        """A rope project

        :parameters:
            - `project_root`: the address of the root folder of the project
            - `fscommands`: implements the file system operations rope uses
              have a look at `rope.base.fscommands`

        """
        self._address = os.path.expanduser(project_root)
        if not os.path.exists(self._address):
            os.mkdir(self._address)
        elif not os.path.isdir(self._address):
            raise RopeError('Project root exists and is not a directory')
        if fscommands is None:
            fscommands = rope.base.fscommands.create_fscommands(self._address)
        super(Project, self).__init__(fscommands)
        self.pycore = rope.base.pycore.PyCore(self)
        self.no_project = NoProject()

    root = property(lambda self: self.get_resource(''))

    address = property(lambda self: self._address)

    def get_files(self):
        return self._get_files_recursively(self.root)

    def _get_resource_path(self, name):
        return os.path.join(self._address, *name.split('/'))

    def _get_files_recursively(self, folder):
        result = []
        for file in folder.get_files():
            result.append(file)
        for folder in folder.get_folders():
            if not folder.name.startswith('.'):
                result.extend(self._get_files_recursively(folder))
        return result

    def get_pycore(self):
        return self.pycore

    def get_out_of_project_resource(self, path):
        return self.no_project.get_resource(path)

    def do(self, changes):
        """Apply the changes in a `ChangeSet`

        Most of the time you call this function for committing the
        changes for a refactoring.
        """
        self.history.do(changes)


class NoProject(_Project):
    """A null object for holding out of project files"""

    def __init__(self):
        fscommands = rope.base.fscommands.FileSystemCommands()
        super(NoProject, self).__init__(fscommands)

    def _get_resource_path(self, name):
        return os.path.abspath(name)

    def get_resource(self, name):
        return super(NoProject, self).get_resource(os.path.abspath(name))


class Resource(object):
    """Represents files and folders in a project"""

    def __init__(self, project, path):
        self.project = project
        self._path = path

    def move(self, new_location):
        """Move resource to `new_location`"""
        self._perform_change(rope.base.change.MoveResource(self, new_location),
                             'Moving <%s> to <%s>' % (self.path, new_location))

    def remove(self):
        """Remove resource from the project"""
        self._perform_change(rope.base.change.RemoveResource(self),
                             'Removing <%s>' % self.path)

    def is_folder(self):
        """Return true if the resource is a folder"""

    def exists(self):
        return os.path.exists(self.real_path)

    def _get_parent(self):
        parent = '/'.join(self.path.split('/')[0:-1])
        return self.project.get_resource(parent)

    def _get_path(self):
        """Return the path of this resource relative to the project root

        The path is the list of parent directories separated by '/' followed
        by the resource name.
        """
        return self._path

    def _get_name(self):
        """Return the name of this resource"""
        return self.path.split('/')[-1]

    def _get_real_path(self):
        """Return the file system path of this resource"""
        return self.project._get_resource_path(self.path)

    def _get_destination_for_move(self, destination):
        dest_path = self.project._get_resource_path(destination)
        if os.path.isdir(dest_path):
            if destination != '':
                return destination + '/' + self.name
            else:
                return self.name
        return destination

    parent = property(_get_parent)
    name = property(_get_name)
    path = property(_get_path)
    real_path = property(_get_real_path)

    def __eq__(self, obj):
        return self.__class__ == obj.__class__ and self.path == obj.path

    def __hash__(self):
        return hash(self.path)

    def _perform_change(self, change_, description):
        changes = rope.base.change.ChangeSet(description)
        changes.add_change(change_)
        self.project.do(changes)


class File(Resource):
    """Represents a file"""

    def __init__(self, project, name):
        super(File, self).__init__(project, name)

    def read(self):
        return self.project.file_access.read(self.real_path)

    def write(self, contents):
        try:
            if contents == self.read():
                return
        except IOError:
            pass
        self._perform_change(rope.base.change.ChangeContents(self, contents),
                             'Writing file <%s>' % self.path)

    def is_folder(self):
        return False


class Folder(Resource):
    """Represents a folder"""

    def __init__(self, project, name):
        super(Folder, self).__init__(project, name)

    def is_folder(self):
        return True

    def get_children(self):
        """Return the children of this folder"""
        path = self.real_path
        result = []
        content = os.listdir(path)
        for name in content:
            if name.endswith('.pyc') or name == '.svn' or name.endswith('~'):
                continue
            if self.path != '':
                resource_name = self.path + '/' + name
            else:
                resource_name = name
            result.append(self.project.get_resource(resource_name))
        return result

    def create_file(self, file_name):
        self._perform_change(
            rope.base.change.CreateFile(self, file_name),
            'Creating file <%s>' % (self.path + '/' + file_name))
        return self.get_child(file_name)

    def create_folder(self, folder_name):
        self._perform_change(
            rope.base.change.CreateFolder(self, folder_name),
            'Creating folder <%s>' % (self.path + '/' + folder_name))
        return self.get_child(folder_name)

    def get_child(self, name):
        if self.path:
            child_path = self.path + '/' + name
        else:
            child_path = name
        return self.project.get_resource(child_path)

    def has_child(self, name):
        try:
            self.get_child(name)
            return True
        except RopeError:
            return False

    def get_files(self):
        result = []
        for resource in self.get_children():
            if not resource.is_folder():
                result.append(resource)
        return result

    def get_folders(self):
        result = []
        for resource in self.get_children():
            if resource.is_folder():
                result.append(resource)
        return result

    def contains(self, resource):
        if self == resource:
            return False
        return self.path == '' or resource.path.startswith(self.path + '/')


class ResourceObserver(object):
    """Provides the interface for observing resources

    `ResourceObserver`\s can be registered using `Resource.add_observer`.
    But most of the time what is needed is `FilteredResourceObserver`
    since ResourceObserver report all changes passed to them and they
    don't report changes to all of the resources.  For example if a
    folder is removed, it only `removed` for that folder and not its
    contents.  You can use `FilteredResourceObserver` if you are
    interested in changes only to a list of resources.  And you want
    changes to be reported on individual resources.

    """

    def __init__(self, changed, removed):
        self.changed = changed
        self.removed = removed

    def resource_changed(self, resource):
        """It is called when the resource changes"""
        self.changed(resource)

    def resource_removed(self, resource, new_resource=None):
        """It is called when a resource no longer exists

        `new_resource` is the destination if we know it, otherwise it
        is None.

        """
        self.removed(resource, new_resource)

    def validate(self, resource):
        """Validate the existence of this resource and its children.

        This function is called when rope need to update its resource
        cache about the files that might have been changed or removed
        by other processes.

        """


class FilteredResourceObserver(object):
    """A useful decorator for `ResourceObserver`

    Most resource observers have a list of resources and are
    interested only in changes to those files.  This class satisfies
    this need.  It dispatches resource changed and removed messages.
    It performs these tasks:

    * Changes to files and folders are analyzed to check whether any
      of the interesting resources are changed or not.  If they are,
      it reports these changes to `resource_observer` passed to the
      constructor.
    * When a resource is removed it checks whether any of the
      interesting resources are contained in that folder and reports
      them to `resource_observer`.
    * When validating a folder it validates all of the interesting
      files in that folder.

    Since most resource observers have are interested in a list of
    resources that change over time, `add_resource` and
    `remove_resource` might be useful.

    """

    def __init__(self, resource_observer, initial_resources=None,
                 timekeeper=None):
        self.observer = resource_observer
        self.resources = {}
        if timekeeper is not None:
            self.timekeeper = timekeeper
        else:
            self.timekeeper = Timekeeper()
        if initial_resources is not None:
            for resource in initial_resources:
                self.add_resource(resource)

    def add_resource(self, resource):
        """Add a resource to the list of interesting resources"""
        self.resources[resource] = self.timekeeper.getmtime(resource)

    def remove_resource(self, resource):
        """Add a resource to the list of interesting resources"""
        if resource in self.resources:
            del self.resources[resource]

    def resource_changed(self, resource):
        changes = _Changes()
        self._update_changes_caused_by_changed(changes, resource)
        self._perform_changes(changes)

    def _update_changes_caused_by_changed(self, changes, changed):
        if changed in self.resources:
            changes.add_changed(changed)
        if self._is_parent_changed(changed):
            changes.add_changed(changed.parent)

    def _update_changes_caused_by_removed(self, changes, resource,
                                          new_resource=None):
        if resource in self.resources:
            changes.add_removed(resource, new_resource)
        if resource.is_folder():
            for file in list(self.resources):
                if resource.contains(file):
                    new_file = self._calculate_new_resource(resource,
                                                            new_resource, file)
                    changes.add_removed(file, new_file)
        if self._is_parent_changed(resource):
            changes.add_changed(resource.parent)
        if new_resource is not None:
            if self._is_parent_changed(new_resource):
                changes.add_changed(new_resource.parent)

    def _is_parent_changed(self, child):
        return child.parent in self.resources

    def resource_removed(self, resource, new_resource=None):
        changes = _Changes()
        self._update_changes_caused_by_removed(changes, resource, new_resource)
        self._perform_changes(changes)

    def validate(self, resource):
        moved = self._search_resource_moves(resource)
        changed = self._search_resource_changes(resource)
        changes = _Changes()
        for file in moved:
            if file in self.resources:
                self._update_changes_caused_by_removed(changes, file)
        for file in changed:
            if file in self.resources:
                self._update_changes_caused_by_changed(changes, file)
        self._perform_changes(changes)

    def _perform_changes(self, changes):
        for resource in changes.changes:
            self.observer.resource_changed(resource)
            self.resources[resource] = self.timekeeper.getmtime(resource)
        for resource, new_resource in changes.moves.iteritems():
            self.observer.resource_removed(resource, new_resource)

    def _search_resource_moves(self, resource):
        all_moved = set()
        if resource in self.resources and not resource.exists():
            all_moved.add(resource)
        if resource.is_folder():
            for file in self.resources:
                if resource.contains(file):
                    if not file.exists():
                        all_moved.add(file)
        moved = set(all_moved)
        for folder in [file for file in all_moved if file.is_folder()]:
            if folder in moved:
                for file in list(moved):
                    if folder.contains(file):
                        moved.remove(file)
        return moved

    def _search_resource_changes(self, resource):
        changed = set()
        if resource in self.resources and self._is_changed(resource):
            changed.add(resource)
        if resource.is_folder():
            for file in self.resources:
                if file.exists() and resource.contains(file):
                    if self._is_changed(file):
                        changed.add(file)
        return changed

    def _is_changed(self, resource):
        return self.resources[resource] != self.timekeeper.getmtime(resource)

    def _calculate_new_resource(self, main, new_main, resource):
        if new_main is None:
            return None
        diff = resource.path[len(main.path):]
        return resource.project.get_resource(new_main.path + diff)


class Timekeeper(object):

    def getmtime(self, resource):
        """Return the modification time of a `Resource`."""
        return os.path.getmtime(resource.real_path)


class _Changes(object):

    def __init__(self):
        self.changes = set()
        self.moves = {}

    def add_changed(self, resource):
        self.changes.add(resource)

    def add_removed(self, resource, new_resource=None):
        self.moves[resource] = new_resource


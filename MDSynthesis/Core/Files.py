"""
Classes for datafile syncronization. 

"""

import Aggregators
import Workers
import yaml
import pickle
from uuid import uuid4
import tables
import fcntl

class File(object):
    """File object base class. Implements file locking and reloading methods.
    
    """
    def __init__(self, filename, logger=None, **kwargs):
        """Create File instance for interacting with file on disk.

        All files in MDSynthesis should be accessible by high-level
        methods without having to worry about simultaneous reading and writing by
        other processes. The File object includes methods and infrastructure
        for ensuring shared and exclusive locks are consistently applied before
        reads and writes, respectively.

        :Arguments:
           *filename*
              name of file on disk object corresponds to 
           *logger*
              logger to send warnings and errors to

        """
        self.filename = os.path.abspath(filename)
        self.handle = None
        self.logger = logger

    def shlock(self):
        """Get shared lock on file.

        Using fcntl.lockf, a shared lock on the file is obtained. If an
        exclusive lock is already held on the file by another process,
        then the method waits until it can obtain the lock.

        :Returns:
           *success*
              True if shared lock successfully obtained
        """
        fcntl.lockf(self.handle, fcntl.LOCK_SH)

        return True

    def exlock(self):
        """Get exclusive lock on file.
    
        Using fcntl.lockf, an exclusive lock on the file is obtained. If a
        shared or exclusive lock is already held on the file by another
        process, then the method waits until it can obtain the lock.

        :Returns:
           *success*
              True if exclusive lock successfully obtained
        """
        # first obtain shared lock; may help to avoid race conditions between
        # exclusive locks (REQUIRES THOROUGH TESTING)
        if self.shlock():
            fcntl.lockf(self.handle, fcntl.LOCK_EX)
    
        return True

    def unlock(self):
        """Remove exclusive or shared lock on file.

        :Returns:
           *success*
              True if lock removed
        """
        fcntl.lockf(self.handle, fcntl.LOCK_UN)

        return True

    def check_existence(self):
        """Check for existence of file.
    
        """
        return os.path.exists(self.filename)

class ContainerFile(File):
    """Container file object; syncronized access to Container data.

    """
    class Meta(tables.IsDescription):
        """Table definition for metadata.

        All strings limited to hardcoded size for now.

        """
        # unique identifier for container
        uuid = tables.StringCol(36)

        # user-given name of container
        name = tables.StringCol(36)

        class = tables.StringCol(36)

        # eventually we would like this to be generated dynamically
        # meaning, size of location string is size needed, and meta table
        # is regenerated if any of its strings need to be (or smaller)
        # When Coordinator generates its database, it uses largest string size
        # needed
        location = tables.StringCol(256)

    class Coordinator(tables.IsDescription):
        """Table definition for coordinator info.

        This information is kept separate from other metadata to allow the
        Coordinator to simply stack tables to populate its database. It doesn't
        need entries that store its own path.

        Path length fixed size for now.
        """
        # absolute path of coordinator
        abspath = tables.StringCol(256)
        
    class Tags(tables.IsDescription):
        """Table definition for tags.

        """
        tag = tables.StringCol(36)

    class Categories(tables.IsDescription):
        """Table definition for categories.

        """
        category = tables.StringCol(36)
        value = tables.StringCol(36)

    def __init__(self, filename, logger, classname, **kwargs): 
        """Initialize Container state file.

        This is the base class for all Container state files. It generates 
        data structure elements common to all Containers. It also implements
        low-level I/O functionality.

        :Arguments:
           *filename*
              path to file
           *logger*
              Container's logger instance
           *classname*
              Container's class name

        :Keywords:
           *name*
              user-given name of Container object
           *coordinator*
              directory in which coordinator state file can be found [None]
           *categories*
              user-given dictionary with custom keys and values; used to
              give distinguishing characteristics to object for search
           *tags*
              user-given list with custom elements; used to give distinguishing
              characteristics to object for search
           *details*
              user-given string for object notes

        .. Note:: kwargs passed to :meth:`create`

        """
        super(ContainerFile, self).__init__(filename, logger=logger)
        
        # if file does not exist, it is created
        if not self.check_existence():
            self.create(classname, **kwargs)

    def create(self, classname, **kwargs):
        """Build state file and common data structure elements.

        :Arguments:
           *classname*
              Container's class name

        :Keywords:
           *name*
              user-given name of Container object
           *coordinator*
              directory in which coordinator state file can be found [None]
           *categories*
              user-given dictionary with custom keys and values; used to
              give distinguishing characteristics to object for search
           *tags*
              user-given list with custom elements; used to give distinguishing
              characteristics to object for search
        """
        self.handle = tables.open_file(self.filename, 'w')
        self.exlock()

        # metadata table
        meta_table = self.handle.create_table('/', 'meta', self.Meta, 'metadata')
        container = meta.row

        container['uuid'] = str(uuid4())
        container['name'] = kwargs.pop('name', classname)
        container['class'] = classname
        container['location'] = os.path.dirname(self.filename)
        container.append()

        # coordinator table
        coordinator_table = self.handle.create_table('/', 'coordinator', self.Coordinator, 'coordinator information')
        container = coordinator.row
        
        container['abspath'] = kwargs.pop('coordinator', None)
        container.append()

        # tags table
        tags_table = self.handle.create_table('/', 'tags', self.Tags, 'tags')
        container = tags.row
        
        tags = kwargs.pop('tags', list())
        for tag in tags:
            container['tag'] = str(tag)
            container.append()

        # categories table
        categories_table = self.handle.create_table('/', 'categories', self.Tags, 'categories')
        container = categories.row
        
        categories = kwargs.pop('categories', dict())
        for key in categories.keys():
            container['category'] = str(key)
            container['value'] = str(categories[key])
            container.append()

        # remove lock and close
        self.unlock()
        self.handle.close()
    
    def read(self, func):
        """Decorator for opening file for reading and applying shared lock.
        
        Applying this decorator to a method will ensure that the file is opened
        for reading and that a shared lock is obtained before that method is
        executed. It also ensures that the lock is removed and the file closed
        after the method returns.

        """
        def inner(*args, **kwargs):
            self.handle = tables.open_file(self.filename, 'r')
            self.shlock()
            func(*args, **kwargs)
            self.unlock()

        return inner
    
    def write(self, func):
        """Decorator for opening file for writing and applying exclusive lock.
        
        Applying this decorator to a method will ensure that the file is opened
        for appending and that an exclusive lock is obtained before that method is
        executed. It also ensures that the lock is removed and the file closed
        after the method returns.

        """
        def inner(*args, **kwargs):
            self.handle = tables.open_file(self.filename, 'a')
            self.exlock()
            func(*args, **kwargs)
            self.unlock()

        return inner

    def _open_r(self):
        """Open file with intention to write.

        Not to be used except for debugging files.

        """
        self.handle = tables.open_file(self.filename, 'r')
        self.shlock()

    def _open_w(self):
        """Open file with intention to write.

        Not to be used except for debugging files.

        """
        self.handle = tables.open_file(self.filename, 'a')
        self.exlock()

    def _close(self):
        """Close file.

        Not to be used except for debugging files.

        """
        self.handle.close()

class SimFile(ContainerFile):
    """Main Sim state file.

    This file contains all the information needed to store the state of a
    Sim object. It includes accessors, setters, and modifiers for all
    elements of the data structure, as well the data structure definition.
    It also defines the format of the file, i.e. the writer and reader
    used to manage it.
    
    """

    class UniverseTopology(tables.IsDescription):
        """Table definition for storing universe topology paths.

        Three versions of the path to a topology are stored: the absolute path
        (abspath), the relative path from user's home directory (relhome), and the
        relative path from the Sim object's directory (relSim). This allows the
        Sim object to use some heuristically good starting points trying to find
        missing files using Finder.
        
        """
        abspath = tables.StringCol(255)
        relhome = tables.StringCol(255)
        relSim = tables.StringCol(255)

    class UniverseTrajectory(tables.IsDescription):
        """Table definition for storing universe trajectory paths.

        The paths to trajectories used for generating the Universe
        are stored in this table.

        See UniverseTopology for path storage descriptions.

        """
        abspath = tables.StringCol(255)
        relhome = tables.StringCol(255)
        relSim = tables.StringCol(255)

    class Selection(tables.IsDescription):
        """Table definition for storing selections.

        A single table corresponds to a single selection. Each row in the
        column contains a selection string. This allows one to store a list
        of selections so as to preserve selection order, which is often
        required for structural alignments.

        """
        selection = tables.StringCol(255)

    def __init__(self, location, logger, **kwargs):
        """Initialize Sim state file.

        :Arguments:
           *location*
              directory that represents the Container
           *logger*
              logger to send warnings and errors to

        """
        super(SimFile, self).__init__(location, logger=logger, classname='Sim', **kwargs)
    
    def create(self, **kwargs):
        """Build Sim data structure.

        :Keywords:
           *name*
              user-given name of Sim object
           *coordinator*
              directory in which Coordinator state file can be found [``None``]
           *categories*
              user-given dictionary with custom keys and values; used to
              give distinguishing characteristics to object for search
           *tags*
              user-given list with custom elements; used to give distinguishing
              characteristics to object for search
           *details*
              user-given string for object notes

        .. Note:: kwargs passed to :meth:`create`

        """
        super(SimFile, self).create(**kwargs)

        self.data['universes'] = dict()
        self.data['selections'] = dict()

class DatabaseFile(File):
    """Database file object; syncronized access to Database data.

    """

class DataFile(object):
    """Universal datafile interface.

    Allows for safe reading and writing of datafiles, which can be of a wide
    array of formats. Handles the details of conversion from pythonic data
    structure to persistent file form.

    """
    file.flush(fsync=True)


"""
Classes for datafile syncronization. 

"""

import Aggregators
import Workers

class File(object):
    """File object base class. Implements file locking and syncronization.
    
    """
    def __init__(self, filename, reader, writer, datastruct=None, logger=None):
        """Create File instance for interacting with file on disk.

        The File object keeps its own cached version of a data structure
        written to file in sync with the file itself. It does this by
        consistently applying locks to files before reading and writing. 
        
        At all times, reading and modifying the data structure is the same as
        reading and writing to the file. Accessing an element of the data
        structure results in locking, reading, and unlocking the file each
        time. Modifying an element results in locking, reading, writing, and
        unlocking. All operations are performed atomically to ensure unintended
        overwrites are avoided.

        :Arguments:
           *filename*
              name of file on disk object synchronizes with
           *reader*
              function used to translate file into data structure
           *writer*
              function used to tranlate data structure into file
           *datastruct*
              data structure to store; overrides definition in :meth:`create`
              this allows for custom data structures without a pre-defined
              definition 
           *logger*
              logger to send warnings and errors to

        """
        self.filename = filename
        self.lockname = "{}.lock".format(self.file.name) 

        self.reader = reader
        self.writer = writer

        # if given, use data structure and write to file
        # if none given, check existence of file and read it in if present
        # else create a new data structure and file from definition
        if datastruct:
            self.data = datastruct
            self.write()
        elif self.check_existence():
            self.read()
        else:
            self.create()

    def create(self):
        """Build data structure and create file.

        This is a placeholder function, since each specific File use-case
        will have a different data structure definition.

        """
        self.data = None
        self.write()

    def read(self):
        """Read contents of file into data structure.

        :Returns:
           *success*
              True if write successful
        """
        # keep attempting lock until successful (failsafe)
        while not self.lock():
            continue

        # keep reading until unlock gives success (only if synchronized)
        while not self.unlock()
            with open(self.filename, 'r') as f:
                self.data = self.reader(f)
        
        return True

    def write(self):
        """Write data structure to file.
    
        :Returns:
           *success*
              True if write successful
        """
        # keep attempting lock until successful (failsafe)
        while not self.lock():
            continue

        # keep writing until unlock gives success (only if synchronized)
        while not self.unlock()
            with open(self.filename, 'w') as f:
                self.data = self.writer(self.data)

        return True

    def lock(self):
        """Get exclusive lock on file.

        The lock is just a symlink of the target file, since making a symlink
        appears to be an atomic operation on most platforms. This is important,
        since creating a symlink also serves to check if one is already present
        all in one operation.

        :Returns:
           *success*
              True if lockfile successfully created
        """
        # if lockfile already present, wait until it disappears; make lock
        while True:
            try:
                os.symlink(self.filename, self.lockname):
                break
            except OSError:
                time.sleep(1)

        # return lockfile existence
        return os.path.exists(self.lockname)

    def unlock(self):
        """Remove exclusive lock on file.

        Before removing the lock, checks that the data structure is
        the same as what is on file.

        :Returns:
           *success*
              True if comparison successful 
        """
        # check that python representation matches file
        success = self.compare()

        if success:
            os.remove(self.lockname)

        return success

    def compare(self):
        """Compare data structure with file contents.

        :Returns:
           *same*
              True if file synchronized with data structure
        """
        with open(self.filename, 'r') as f:
            datatemp = self.reader(f)
        
        return self.data == datatemp
    
    def check_existence(self):
        """Check for existence of file.
    
        """
        return os.path.exists(self.filename)

class ContainerFile(File):
    """Container file object; syncronized access to Container data.

    """

class SimFile(ContainerFile):
    """Main Sim state file.
    
    """



class OperatorFile(File):
    """Operator file object; syncronized access to Operator data.

    """

class DatabaseFile(File):
    """Database file object; syncronized access to Database data.

    """

class DataFile(object):
    """Universal datafile interface.

    Allows for safe reading and writing of datafiles, which can be of a wide
    array of formats. Handles the details of conversion from pythonic data
    structure to persistent file form.

    """


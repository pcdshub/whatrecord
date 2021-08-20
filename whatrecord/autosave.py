from __future__ import annotations

import datetime
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Union

import lark

from . import settings, transformer
from .common import AnyPath, FullLoadContext, ShellStateHandler
from .db import RecordInstance
from .macro import MacroContext, macros_from_string
from .transformer import context_from_token


@dataclass
class RestoreError:
    context: FullLoadContext
    number: int
    description: str


@dataclass
class RestoreValue:
    context: FullLoadContext
    pvname: str
    record: str
    field: str
    value: Union[str, List[str]]


@dataclass
class AutosaveRestoreFile:
    """Representation of an autosave restore (.sav) file."""
    filename: str
    values: Dict[str, Dict[str, RestoreValue]] = field(default_factory=dict)
    disconnected: List[str] = field(default_factory=list)
    errors: List[RestoreError] = field(default_factory=list)
    comments: List[str] = field(default_factory=list)

    @classmethod
    def from_string(
        cls,
        contents: str,
        filename: AnyPath = "",
        macros: Optional[Dict[str, str]] = None
    ) -> AutosaveRestoreFile:
        """Load an autosave file given its string contents."""
        grammar = lark.Lark.open_from_package(
            "whatrecord",
            "autosave_save.lark",
            search_paths=("grammar", ),
            parser="earley",
            propagate_positions=True,
        )

        if macros:
            contents = MacroContext(macros=macros).expand_by_line(contents)

        return _AutosaveRestoreTransformer(cls, filename).transform(
            grammar.parse(contents)
        )

    @classmethod
    def from_file_obj(
        cls, fp, filename: AnyPath, macros: Optional[Dict[str, str]] = None
    ) -> AutosaveRestoreFile:
        """Load an autosave file given a file object."""
        return cls.from_string(
            fp.read(),
            filename=getattr(fp, "name", filename),
            macros=macros,
        )

    @classmethod
    def from_file(
        cls, filename: AnyPath, macros: Optional[Dict[str, str]] = None
    ) -> AutosaveRestoreFile:
        """
        Load an autosave restore (.sav) file.

        Parameters
        ----------
        filename : pathlib.Path or str
            The filename.

        Returns
        -------
        file : AutosaveRestoreFile
            The resulting parsed file.
        """
        with open(filename, "rt") as fp:
            return cls.from_string(fp.read(), filename=filename, macros=macros)


@lark.visitors.v_args(inline=True)
class _AutosaveRestoreTransformer(lark.visitors.Transformer):
    def __init__(self, cls, fn, visit_tokens=False):
        super().__init__(visit_tokens=visit_tokens)
        self.fn = str(fn)
        self.cls = cls
        self.errors = []
        self.restores = {}
        self.comments = []
        self.disconnected = []

    @lark.visitors.v_args(tree=True)
    def restore(self, body):
        return self.cls(
            filename=self.fn,
            values=self.restores,
            errors=self.errors,
            comments=self.comments,
            disconnected=self.disconnected,
        )

    restore_item = transformer.pass_through

    def error(self, exclamation, error_number, error_description=None):
        self.errors.append(
            RestoreError(
                context=transformer.context_from_token(self.fn, exclamation),
                number=error_number,
                description=str(error_description or ""),
            )
        )

    def value_restore(self, pvname, value=None):
        context = context_from_token(self.fn, pvname)
        if "." in pvname:
            record, field = pvname.split(".", 1)
        else:
            record, field = pvname, "VAL"

        record = str(record)
        if record not in self.restores:
            self.restores[record] = {}

        self.restores[record][field.lstrip(".")] = RestoreValue(
            context=context,
            record=record,
            pvname=f"{record}.{field}" if field else record,
            field=str(field),
            value=value if isinstance(value, list) else _fix_value(value),
        )

    value = transformer.pass_through
    record_name = transformer.pass_through
    scalar_value = transformer.pass_through
    pvname = transformer.pass_through

    def array_elements(self, *elements):
        return [_fix_value(elem) for elem in elements]

    def array_value(self, array_marker, array_begin, elements, array_end):
        return list(elements)

    def error_number(self, number):
        return int(number)

    error_description = transformer.stringify

    def comment(self, comment):
        comment = comment.lstrip("# ")
        if not comment:
            return

        parts = comment.split(" ")
        if len(parts) == 3 and parts[-2:] == ["Search", "Issued"]:
            self.disconnected.append(parts[0])
        else:
            self.comments.append(comment)


def _strip_double_quote(value: str) -> str:
    """Strip one leading/single trailing double-quote."""
    if value[0] == '"':
        value = value[1:]
    if value[-1] == '"':
        value = value[:-1]
    return value


RE_REMOVE_ESCAPE = re.compile(r"\\(.)")


def _fix_value(value: Optional[str]) -> str:
    """Remove quotes, and fix up escaping."""
    if value is None:
        # Value can be empty in autosave files
        return ""
    value = _strip_double_quote(value)
    return RE_REMOVE_ESCAPE.sub(r"\1", value)


@dataclass
class AutosaveSet:
    context: FullLoadContext
    request_filename: str
    save_filename: str
    period: Optional[int] = None
    trigger_channel: Optional[str] = None
    macros: Dict[str, str] = field(default_factory=dict)
    method: str = "manual"


@dataclass
class AutosaveRestorePassFile:
    context: FullLoadContext
    save_filename: str
    macros: Dict[str, str] = field(default_factory=dict)
    pass_number: int = 0

    load_timestamp: Optional[datetime.datetime] = None
    file_timestamp: Optional[datetime.datetime] = None
    data: Optional[AutosaveRestoreFile] = None

    def update(self, save_path: pathlib.Path) -> AutosaveRestoreFile:
        """Update the autosave .sav file from disk."""
        fn = save_path / self.save_filename
        file_timestamp = datetime.datetime.fromtimestamp(fn.stat().st_mtime)
        if self.file_timestamp is not None and file_timestamp == self.file_timestamp:
            if self.data is not None:
                return self.data

        if self.load_timestamp is not None and self.data is not None:
            dt = datetime.datetime.now() - self.load_timestamp
            if dt.total_seconds() < settings.AUTOSAVE_RELOAD_PERIOD:
                return self.data

        self.file_timestamp = file_timestamp
        self.load_timestamp = datetime.datetime.now()
        self.data = AutosaveRestoreFile.from_file(
            fn,
            macros=self.macros,
        )
        return self.data


_handler = ShellStateHandler.generic_handler_decorator


@dataclass
class AutosaveState(ShellStateHandler):
    """The state of autosave in an IOC."""

    metadata_key: ClassVar[str] = "autosave"

    configured: bool = False
    request_paths: List[pathlib.Path] = field(default_factory=list)
    save_path: pathlib.Path = field(default_factory=pathlib.Path)
    sets: Dict[str, AutosaveSet] = field(default_factory=dict)
    restore_files: Dict[str, AutosaveRestorePassFile] = field(default_factory=dict)
    incomplete_sets_ok: Optional[bool] = None  # default: True
    dated_backups: Optional[bool] = None  # default: True
    date_period_minutes: Optional[int] = None  # default: 0
    num_seq_files: Optional[int] = None  # default: 3
    seq_period: Optional[int] = None  # default: 0
    retry_seconds: Optional[int] = None  # default: 0
    ca_reconnect: Optional[bool] = None  # default: False
    callback_timeout: Optional[int] = None  # default: 0
    task_priority: Optional[int] = None  # default: 0
    nfs_host: Optional[str] = None
    use_status_pvs: Optional[bool] = None  # default: False
    status_prefix: Optional[str] = None
    file_permissions: Optional[int] = None  # default: 0o664
    debug: Optional[int] = None  # default: 0

    @property
    def save_name_pv(self) -> Optional[str]:
        """The save name PV, derived from the macro context."""
        if self.primary_handler is not None:
            return self.primary_handler.macro_context.get("SAVENAMEPV")

    @property
    def save_path_pv(self) -> Optional[str]:
        """The save path PV, derived from the macro context."""
        if self.primary_handler is not None:
            return self.primary_handler.macro_context.get("SAVEPATHPV")

    # save_restore.c

    @_handler
    def handle_fdbrestore(self, filename: str = ""):
        """
        If save_file refers to a save set that exists in memory, then PV's in
        the save set will be restored from values in memory. Otherwise, this
        functions restores the PV's in <saveRestorePath>/<save_file> and
        creates a new backup file "<saveRestorePath>/<save_file>.bu". The
        effect probably will not be the same as a boot-time restore, because
        caput() calls are used instead of static database access dbPutX()
        calls. Record processing will result from caput()'s to inherently
        process- passive fields.
        """

    @_handler
    def handle_fdbrestoreX(self, filename="", macrostring=""):
        """
        This function restores from the file <saveRestorePath>/<save_file>,
        which can look just like a save file, but which needn't end with <END>.
        No backup file will be written. The effect probably will not be the
        same as a boot-time restore, because caput() calls are used instead of
        static database access dbPut*() calls. Record processing will result
        from caput()'s to inherently process-passive fields.
        """

    @_handler
    def handle_manual_save(self, request_file: str = ""):
        """
        Cause current PV values for the request file to be saved. Any request
        file named in a create_xxx_set() command can be saved manually.
        """

    @_handler
    def handle_set_savefile_name(self, request_file: str = "", save_filename: str = ""):
        """
        If a save set has already been created for the request file, this
        function will change the save file name.
        """
        try:
            set_ = self.sets[request_file]
        except KeyError:
            raise ValueError("Request file not configured")

        set_.save_filename = save_filename

    @_handler
    def handle_create_periodic_set(
        self, filename: str = "", period: int = 0, macro_string: str = "", *_
    ):
        """
        Create a save set for the request file. The save file will be written
        every period seconds.
        """
        self.sets[filename] = AutosaveSet(
            context=self.get_load_context(),
            request_filename=filename,
            save_filename="{}.sav".format(pathlib.Path(filename).stem),
            period=period,
            trigger_channel=None,
            macros=macros_from_string(macro_string),
            method="periodic",
        )

    @_handler
    def handle_create_triggered_set(
        self, filename: str = "", trigger_channel: str = "", macro_string: str = "", *_
    ):
        """
        Create a save set for the request file. The save file will be written
        whenever the PV specified by trigger_channel is posted. Normally this
        occurs when the PV's value changes.
        """
        self.sets[filename] = AutosaveSet(
            context=self.get_load_context(),
            request_filename=filename,
            save_filename="{}.sav".format(pathlib.Path(filename).stem),
            period=None,
            trigger_channel=trigger_channel,
            macros=macros_from_string(macro_string),
            method="triggered",
        )

    @_handler
    def handle_create_monitor_set(
        self, filename: Optional[str] = None, period: int = 0, macro_string: str = "", *_
    ):
        """
        Create a save set for the request file. The save file will be written
        every period seconds, if any PV in the save set was posted
        (changed value) since the last write.
        """
        if filename is None:
            # An indicator to "start the save task"
            return

        self.sets[filename] = AutosaveSet(
            context=self.get_load_context(),
            request_filename=filename,
            save_filename="{}.sav".format(pathlib.Path(filename).stem),
            period=int(period),
            trigger_channel=None,
            macros=macros_from_string(macro_string),
            method="monitor",
        )

    @_handler
    def handle_create_manual_set(self, filename: str = "", macro_string: str = ""):
        """
        Create a save set for the request file. The save file will be written
        when the function manual_save() is called with the same request-file
        name.
        """
        self.sets[filename] = AutosaveSet(
            context=self.get_load_context(),
            request_filename=filename,
            save_filename="{}.sav".format(pathlib.Path(filename).stem),
            period=None,
            trigger_channel=None,
            macros=macros_from_string(macro_string),
            method="manual",
        )

    @_handler
    def handle_save_restoreShow(self, verbose: int = 0):
        """Show the save restore status."""
        return self.sets

    @_handler
    def handle_set_requestfile_path(self, path: str = "", subpath: str = ""):
        full_path = (pathlib.Path(path) / subpath).resolve()
        if full_path not in self.request_paths:
            self.request_paths.append(full_path)

    @_handler
    def handle_set_savefile_path(self, path: str = "", subpath: str = ""):
        """
        Called before iocInit(), this function specifies the path to be
        prepended to save-file and restore-file names. pathsub, if present,
        will be appended to path, if present, with a separating '/', whether or
        not path ends or pathsub begins with '/'. If the result does not end in
        '/', one will be appended to it.

        If save_restore is managing its own NFS mount, this function specifies
        the mount point, and calling it will result in an NFS mount if all
        other requirements have already been met. If a valid NFS mount already
        exists, the file system will be dismounted and then mounted with the
        new path name. This function can be called at any time.
        """
        path = pathlib.Path(path) / subpath
        if self.primary_handler is not None:
            path = self.primary_handler._fix_path(path)
        self.save_path = path.resolve()

    @_handler
    def handle_set_saveTask_priority(self, priority: int = 0):
        """Set the priority of the save_restore task."""
        self.task_priority = int(priority)

    @_handler
    def handle_save_restoreSet_NFSHost(
        self, hostname: str = "", address: str = "", mntpoint: str = "", *_
    ):
        """
        Specifies the name and IP address of the NFS host. If both have been
        specified, and set_savefile_path() has been called to specify the file
        path, save_restore will manage its own NFS mount. This allows
        save_restore to recover from a reboot of the NFS host
        (that is, a stale file handle) and from some kinds of tampering with
        the save_restore directory.
        """
        self.nfs_host = f"nfs://{hostname}/{mntpoint} ({address})"

    @_handler
    def handle_remove_data_set(self, filename: str = ""):
        """If a save set has been created for request_file, this function will delete it."""
        ...

    @_handler
    def handle_reload_periodic_set(
        self, filename: str = "", period: int = 0, macro_string: str = "", *_
    ):
        """
        This function allows you to change the PV's and the period associated
        with a save set created by create_periodic_set().
        """

    @_handler
    def handle_reload_triggered_set(
        self, filename: str = "", trigger_channel: str = "", macro_string: str = "", *_
    ):
        """
        This function allows you to change the PV's and the trigger channel
        associated with a save set created by create_triggered_set().
        """

    @_handler
    def handle_reload_monitor_set(
        self, filename: str = "", period: int = 0, macro_string: str = "", *_
    ):
        """
        This function allows you to change the PV's and the period associated
        with a save set created by create_monitor_set().
        """

    @_handler
    def handle_reload_manual_set(self, filename: str = "", macrostring: str = ""):
        """
        This function allows you to change the PV's associated with a save set
        created by create_manual_set().
        """

    @_handler
    def handle_save_restoreSet_Debug(self, level: int = 0):
        """
        Sets the value (int) save_restoreDebug (initially 0). Increase to get
        more informational messages printed to the console.
        """
        self.debug = int(level)

    @_handler
    def handle_save_restoreSet_NumSeqFiles(self, numSeqFiles: int = 0):
        """
        Sets the value of (int) save_restoreNumSeqFiles (initially 3). This is
        the number of sequenced backup files to be maintained.
        """
        self.num_seq_files = int(numSeqFiles)
        if not (0 <= self.num_seq_files <= 10):
            raise ValueError("numSeqFiles must be between 0 and 10 inclusive.")

    @_handler
    def handle_save_restoreSet_SeqPeriodInSeconds(self, period: int = 0):
        """
        Sets the value of (int) save_restoreSeqPeriodInSeconds (initially 60).
        Sequenced backup files will be written with this period.
        """
        self.seq_period = int(period)
        if self.seq_period < 10:
            raise ValueError("period must be 10 or greater.")

    @_handler
    def handle_save_restoreSet_IncompleteSetsOk(self, ok: int = 0):
        """
        Sets the value of (int) save_restoreIncompleteSetsOk (initially 1). If
        set to zero, save files will not be restored at boot time unless they
        are perfect, and they will not be overwritten at save time unless a
        valid CA connection and value exists for every PV in the list.
        """
        self.incomplete_sets_ok = bool(ok)

    @_handler
    def handle_save_restoreSet_DatedBackupFiles(self, ok: int = 0):
        """
        Sets the value of (int) save_restoreDatedBackupFiles (initially 1). If
        zero, the backup file written at reboot time
        (a copy of the file from which PV values are restored) will have the
        suffix '.bu', and will be overwritten every reboot. If nonzero, each
        reboot will leave behind its own backup file.
        """
        self.dated_backups = bool(ok)

    @_handler
    def handle_save_restoreSet_status_prefix(self, prefix: str = ""):
        """
        Specifies the prefix to be used to construct the names of PV's with
        which save_restore reports its status. If you want autosave to update
        status PVs as it operates, you must call this function and load the
        database save_restoreStatus.db, specifying the same prefix in both
        commands.
        """
        self.status_prefix = prefix

    @_handler
    def handle_save_restoreSet_FilePermissions(self, permissions: int = 0):
        """
        Specify the file permissions used to create new .sav files. This
        integer value will be supplied, exactly as given, to the system call,
        open(), and to the call fchmod(). Typically, file permissions are set
        with an octal number, such as 0640, and
        save_restoreSet_FilePermissions() will confirm any number given to it
        by echoing it to the console as an octal number.
        """
        self.file_permissions = int(permissions)

    @_handler
    def handle_save_restoreSet_RetrySeconds(self, seconds: int = 0):
        """
        Specify the time delay between a failed .sav-file write and the retry
        of that write. The default delay is 60 seconds. If list-PV's change
        during the delay, the new values will be written.
        """
        self.retry_seconds = int(seconds)

    @_handler
    def handle_save_restoreSet_UseStatusPVs(self, ok: int = 0):
        """
        Specifies whether save_restore should report its status to a preloaded
        set of EPICS PV's (contained in the database save_restoreStatus.db). If
        the argument is '0', then status PV's will not be used.
        """
        self.use_status_pvs = bool(ok)

    @_handler
    def handle_save_restoreSet_CAReconnect(self, ok: int = 0):
        """
        Specify whether autosave should periodically retry connecting to PVs
        whose initial connection attempt failed. Currently, the
        connection-retry interval is hard-wired at 60 seconds.
        """
        self.ca_reconnect = bool(ok)

    @_handler
    def handle_save_restoreSet_CallbackTimeout(self, timeout: int = 0):
        """
        Specify the time interval in seconds between forced save-file writes.
        (-1 means forever). This is intended to get save files written even if
        the normal trigger mechanism is broken.
        """
        self.callback_timeout = int(timeout)

    @_handler
    def handle_asVerify(
        self, filename: str = "", verbose: int = 0, restoreFileName: str = "", *_
    ):
        """
        Compare PV values in the IOC with values written in filename
        (which should be an autosave restore file, or at least look like one).
        If restoreFileName is not empty, write a new restore file.
        """
        ...

    @_handler
    def handle_save_restoreSet_periodicDatedBackups(self, periodMinutes: int = 0):
        """
        Sets the value of (int) save_restoreDatedBackupFiles (initially 1). If
        zero, the backup file written at reboot time
        (a copy of the file from which PV values are restored) will have the
        suffix '.bu', and will be overwritten every reboot. If nonzero, each
        reboot will leave behind its own backup file.
        """
        self.dated_backups = True
        self.date_period_minutes = int(periodMinutes)

    # dbrestore.c

    @_handler
    def handle_set_pass0_restoreFile(self, file: str = "", macro_string: str = ""):
        """
        This function specifies a save file to be restored during iocInit,
        before record initialization. An unlimited number of files can be
        specified using calls to this function. If the file name begins with
        "/", autosave will use it as specified; otherwise, autosave will
        prepend the file path specified to set_savefile_path(). The second
        argument is optional.
        """
        self.restore_files[file] = AutosaveRestorePassFile(
            context=self.get_load_context(),
            save_filename=file,
            macros=macros_from_string(macro_string),
            pass_number=0,
        )
        return {
            "autosave": f"Added pass 0 restore file {self.save_path}/{file}"
        }

    @_handler
    def handle_set_pass1_restoreFile(self, file: str = "", macro_string: str = ""):
        """
        This function specifies a save file to be restored during iocInit,
        after record initialization. An unlimited number of files can be
        specified using calls to this function. If the file name begins with
        "/", autosave will use it as specified; otherwise, autosave will
        prepend the file path specified to set_savefile_path(). The second
        argument is optional.
        """
        self.restore_files[file] = AutosaveRestorePassFile(
            context=self.get_load_context(),
            save_filename=file,
            macros=macros_from_string(macro_string),
            pass_number=1,
        )
        return {
            "autosave": f"Added pass 1 restore file {self.save_path}/{file}"
        }

    @_handler
    def handle_dbrestoreShow(self):
        """
        List all the save sets currently being managed by the save_restore
        task. If (verbose != 0), lists the PV's as well.
        """
        ...

    @_handler
    def handle_makeAutosaveFileFromDbInfo(
        self, filename: str = "", info_name: str = "", *_
    ):
        """
        Search through the EPICS database
        (that is, all EPICS records loaded into an IOC) for 'info' nodes named
        info_name; construct a list of PV names from the associated info_values
        found, and write the PV names to the file fileBaseName. If fileBaseName
        does not contain the string '.req', this string will be appended to it.
        See makeAutosaveFiles() for more information.
        """

    @_handler
    def handle_makeAutosaveFiles(self):
        """
        Search through the EPICS database
        (that is, all EPICS records loaded into an IOC) for info nodes named
        'autosaveFields' and 'autosaveFields_pass0'; construct lists of PV
        names from the associated info values, and write the PV names to the
        files 'info_settings.req' and 'info_positions.req', respectively.
        """

    @_handler
    def handle_eraseFile(self, filename: str = ""):
        """Erase (empty) an autosave file."""
        ...

    @_handler
    def handle_appendToFile(self, filename: str = "", line: str = ""):
        """
        Append line to a file.

        For example, to add a line to built_settings.req yourself:

        appendToFile("built_settings.req", '$(P)userStringSeqEnable')
        """
        ...

    @_handler
    def handle_autosaveBuild(
        self, filename: str = "", reqFileSuffix: str = "", on: int = 0, *_
    ):
        """
        It's tedious and error prone to have these entries separately
        maintained, so autosave can do the request-file part for you. To do
        this, you tell autosave to arrange to be called whenever
        dbLoadRecords() is called
        (note that dbLoadTemplate() calls dbLoadRecords()), you tell it how to
        make a request-file name from a database-file name, and you give it the
        name of the request file you want it to build. You can do this with the
        following command:

            autosaveBuild("built_settings.req", "_settings.req", 1)

        This tells autosave to do the following:

            1. Begin building the file built_settings.req. If this is the first
               call that mentions built_settings.req, erase the file.
            2. Generate request-file names by stripping ".db", or ".vdb", or
               ".template" from database-file names, and adding the suffix
               "_settings.req".
            3. Enable (disable) automated building if the third argument is 1
               (0).

        While automated building is enabled, autosave will generate
        request-file names and search for those files in its request-file path.
        If it finds a request file, it will add the appropriate line to
        built_settings.req.

        All this does is get the file built_settings.req built. If you want it
        to be used, you must add the following line to auto_settings.req:

            file built_settings.req P=$(P)
        """

    def annotate_record(self, record: RecordInstance) -> Optional[Dict[str, Any]]:
        metadata = {}
        for restore_file in self.restore_files.values():
            try:
                data = restore_file.update(self.save_path)
            except FileNotFoundError:
                fn = self.save_path / restore_file.save_filename
                metadata.setdefault("error", []).append(
                    f"Restore file not found: {fn}"
                )
                continue

            record_data = data.values.get(record.name, None)
            if record_data is not None:
                metadata.setdefault("restore", []).append(record_data)
            for pvname in data.disconnected:
                if pvname.split(".")[0] == record.name:
                    if "." in pvname:
                        field = pvname.split(".", 1)[1]
                    else:
                        field = "VAL"
                    metadata.setdefault("disconnected", []).append(
                        field
                    )

        return metadata if metadata else None

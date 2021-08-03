"""
This module is not intended to be imported and used in Python.  It's a helper
script to be paired with the GNU debugger (gdb).

Usage:
    $ gdb --batch-silent --command gdb_binary_info.py --args /path/to/bin/linux-x86_64/ioc_binary
"""
from __future__ import print_function

if __name__ != "__main__":
    raise RuntimeError(__doc__)

import json  # noqa
import os  # noqa
import sys  # noqa
import tempfile  # noqa

import gdb  # noqa

try:
    gdb.execute("set startup-with-shell off")
except gdb.error:
    # Comes in a later version
    pass


def get_all_symbol_names():
    try:
        msymbols = gdb.execute("maint print msymbols", to_string=True)
    except gdb.error:
        with tempfile.NamedTemporaryFile(mode="wt") as temp:
            gdb.execute("maint print msymbols " + temp.name, to_string=True)
            with open(temp.name, "rt") as f:
                msymbols = f.read()

    for line in msymbols.splitlines():
        line = line.strip()
        if not line.count(" ") > 3:
            continue

        symbol_name = line.split()[3]
        yield line, symbol_name


def parse_version_string(ver):
    return ver.split(" ")[2].rstrip(",")


def get_version_info():
    try:
        version = gdb.parse_and_eval("pVersionCAC")
        return parse_version_string(str(version))
    except gdb.error:
        return None


OLD_GDB = not hasattr(gdb, "lookup_static_symbol")

if not OLD_GDB:
    # TODO: unify or just remove old gdb support?
    def get_variables():
        defs = gdb.lookup_static_symbol("vardefs")
        if not defs:
            return {}

        variables = {}
        idx = 0
        while True:
            var = defs.value()[idx]
            name = var["name"]
            if int(name.dereference().address) == 0:
                break
            variables[name.string()] = {
                "name": name.string(),
                "type": str(var["type"]),
                "value": None,
            }
            idx += 1
        return variables

    def find_funcdefs(symbols=None):
        variables = gdb.execute("info variables -q -t iocshFuncDef", to_string=True)
        funcdef_names = [
            line.split()[-1].rstrip(";")
            for line in variables.splitlines()
            if 'iocshFuncDef' in line
        ]

        for funcdef_name in funcdef_names:
            sym = gdb.lookup_static_symbol(funcdef_name)
            try:
                val = sym.value()
            except Exception:
                continue

            try:
                name = val["name"].string()
            except gdb.error:
                # optimized out; skip this one entirely
                continue

            yield name, sym, val

else:
    def get_variables():
        # TODO
        return {}

    def find_funcdefs(symbols=None):
        for line, symbol_name in (symbols or ALL_SYMBOLS):
            sym, is_method_field = gdb.lookup_symbol(symbol_name)
            if is_method_field:
                continue

            if sym is None or str(sym.type) not in ("const iocshFuncDef", "iocshFuncDef"):
                continue

            try:
                val = sym.value()
            except Exception:
                continue

            try:
                val["name"].string()
            except gdb.error:
                # optimized out; skip this one entirely
                continue

            yield symbol_name, sym, val


def get_symbol_context(sym):
    """Get the whatrecord-format context for the given gdb symbol."""
    return (os.path.abspath(sym.symtab.fullname()), sym.line)


def get_commands():
    def by_name(item):
        name, _, _, = item
        return name

    for name, funcdef_sym, funcdef in sorted(find_funcdefs(), key=by_name):
        try:
            context = get_symbol_context(funcdef_sym)
        except gdb.error:
            context = None

        command = {
            "name": name,
            "usage": None,
            "context": (context, ) if context else None,
            "args": [],
        }
        try:
            command["usage"] = funcdef["usage"]
        except Exception:
            pass

        for idx in range(int(funcdef["nargs"])):
            arg = funcdef["arg"][idx].dereference()
            command["args"].append({
                "name": arg["name"].string(),
                "type": str(arg["type"]),
            })
        yield name, command


if OLD_GDB:
    # gdb.execute("set logging off")
    # Do this before "start" - static symbols only for now
    ALL_SYMBOLS = tuple(sorted(get_all_symbol_names()))
    gdb.execute("start")

try:
    info = {
        "commands": dict(get_commands()),
        "base_version": get_version_info(),
        "variables": get_variables(),
        "error": None,
    }
except Exception as ex:
    info = {
        "commands": {},
        "base_version": None,
        "variables": {},
        "error": f"{type(ex).__name__}: {ex}",
    }
finally:
    if OLD_GDB:
        gdb.execute("kill")


# Note: --batch-silent will eat up all output of this script, too; so
# use the original sys.__stdout__
print(json.dumps(info, indent=4), file=sys.__stdout__)

# gdb.execute("quit")

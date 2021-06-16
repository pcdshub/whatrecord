"""
`whatrec` is the top-level command for accessing various subcommands.

Try::

"""

import argparse
import asyncio
import importlib
import inspect
import logging

import whatrecord  # noqa

DESCRIPTION = __doc__
RETURN_VALUE = None

MODULES = ("server", "iocmanager_loader", "info", "parse")


def _try_import(module):
    relative_module = f".{module}"
    return importlib.import_module(relative_module, "whatrecord.bin")


def _build_commands():
    global DESCRIPTION
    result = {}
    unavailable = []

    for module in sorted(MODULES):
        try:
            mod = _try_import(module)
        except Exception as ex:
            unavailable.append((module, ex))
        else:
            result[module] = (mod.build_arg_parser, mod.main)
            DESCRIPTION += f"\n    $ whatrecord {module} --help"

    if unavailable:
        DESCRIPTION += "\n\n"

        for module, ex in unavailable:
            DESCRIPTION += (
                f"\nWARNING: whatrecord {module!r} is unavailable due to:"
                f"\n\t{ex.__class__.__name__}: {ex}"
            )

    return result


COMMANDS = _build_commands()


def main():
    top_parser = argparse.ArgumentParser(
        prog="whatrec",
        description=DESCRIPTION,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    top_parser.add_argument(
        "--version",
        "-V",
        action="version",
        version='0.0.0',  # TODO # whatrecord.__version__,
        help="Show the whatrec version number and exit.",
    )

    top_parser.add_argument(
        "--log",
        "-l",
        dest="log_level",
        default="INFO",
        type=str,
        help="Python logging level (e.g. DEBUG, INFO, WARNING)",
    )

    subparsers = top_parser.add_subparsers(help="Possible subcommands")
    for command_name, (build_func, main) in COMMANDS.items():
        sub = subparsers.add_parser(command_name.replace("_", "-"))
        build_func(sub)
        sub.set_defaults(func=main)

    args = top_parser.parse_args()
    kwargs = vars(args)
    log_level = kwargs.pop("log_level")

    logger = logging.getLogger("whatrecord")
    logger.setLevel(log_level)
    logging.basicConfig()

    if hasattr(args, "func"):
        func = kwargs.pop("func")
        logger.debug("%s(**%r)", func.__name__, kwargs)

        global RETURN_VALUE
        if inspect.iscoroutinefunction(func):
            loop = asyncio.get_event_loop()
            RETURN_VALUE = loop.run_until_complete(func(**kwargs))
        else:
            RETURN_VALUE = func(**kwargs)
            logger.debug(
                "%s Return value available as RETURN_VALUE: %s",
                func.__name__, RETURN_VALUE
            )
    else:
        top_parser.print_help()


if __name__ == "__main__":
    result = main()

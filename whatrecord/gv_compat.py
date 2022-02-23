"""
The following is borrowed from pygraphviz, reimplemented to allow for asyncio
compatibility.

Some form of it may move upstream at some point.  Requires graphviz<0.18 due
to API changes.
"""

import asyncio
import logging
import os

import graphviz as gv

logger = logging.getLogger(__name__)


async def async_render(
    engine, format, filepath, renderer=None, formatter=None, quiet=False
):
    """
    Async Render file with Graphviz ``engine`` into ``format``,  return result
    filename.

    Parameters
    ----------
    engine :
        The layout commmand used for rendering (``'dot'``, ``'neato'``, ...).
    format :
        The output format used for rendering (``'pdf'``, ``'png'``, ...).
    filepath :
        Path to the DOT source file to render.
    renderer :
        The output renderer used for rendering (``'cairo'``, ``'gd'``, ...).
    formatter :
        The output formatter used for rendering (``'cairo'``, ``'gd'``, ...).
    quiet : bool
        Suppress ``stderr`` output from the layout subprocess.

    Returns
    -------
    The (possibly relative) path of the rendered file.

    Raises
    ------
    ValueError
        If ``engine``, ``format``, ``renderer``, or ``formatter`` are not
        known.

    graphviz.RequiredArgumentError
        If ``formatter`` is given but ``renderer`` is None.

    graphviz.ExecutableNotFound
        If the Graphviz executable is not found.

    subprocess.CalledProcessError
        If the exit status is non-zero.

    Notes
    -----
    The layout command is started from the directory of ``filepath``, so that
    references to external files (e.g. ``[image=...]``) can be given as paths
    relative to the DOT source file.
    """
    # Adapted from graphviz under the MIT License (MIT) Copyright (c) 2013-2020
    # Sebastian Bank
    dirname, filename = os.path.split(filepath)
    cmd, rendered = gv.backend.command(engine, format, filename, renderer, formatter)

    if dirname:
        cwd = dirname
        rendered = os.path.join(dirname, rendered)
    else:
        cwd = None

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )

    (stdout, stderr) = await proc.communicate()
    if proc.returncode:
        raise gv.backend.CalledProcessError(
            proc.returncode, cmd, output=stdout, stderr=stderr
        )
    return rendered


class AsyncDigraph(gv.Digraph):
    async def async_render(
        self,
        filename=None,
        directory=None,
        view=False,
        cleanup=False,
        format=None,
        renderer=None,
        formatter=None,
        quiet=False,
        quiet_view=False,
    ):
        """
        Save the source to file and render with the Graphviz engine.

        Parameters
        ----------
        filename :
            Filename for saving the source (defaults to ``name`` + ``'.gv'``)
        directory :
            (Sub)directory for source saving and rendering.
        view (bool) :
            Open the rendered result with the default application.
        cleanup (bool) :
            Delete the source file after rendering.
        format :
            The output format used for rendering (``'pdf'``, ``'png'``, etc.).
        renderer :
            The output renderer used for rendering (``'cairo'``, ``'gd'``, ...).
        formatter :
            The output formatter used for rendering (``'cairo'``, ``'gd'``, ...).
        quiet (bool) :
            Suppress ``stderr`` output from the layout subprocess.
        quiet_view (bool) :
            Suppress ``stderr`` output from the viewer process;
           implies ``view=True``, ineffective on Windows.
        Returns:
            The (possibly relative) path of the rendered file.

        Raises
        ------
        ValueError
            If ``format``, ``renderer``, or ``formatter`` are not known.

        graphviz.RequiredArgumentError
            If ``formatter`` is given but ``renderer`` is None.

        graphviz.ExecutableNotFound
            If the Graphviz executable is not found.

        subprocess.CalledProcessError
            If the exit status is non-zero.

        RuntimeError
            If viewer opening is requested but not supported.

        Notes
        -----
        The layout command is started from the directory of ``filepath``, so that
        references to external files (e.g. ``[image=...]``) can be given as paths
        relative to the DOT source file.
        """
        # Adapted from graphviz under the MIT License (MIT) Copyright (c) 2013-2020
        # Sebastian Bank
        filepath = self.save(filename, directory)

        if format is None:
            format = self._format

        rendered = await async_render(
            self._engine,
            format,
            filepath,
            renderer=renderer,
            formatter=formatter,
            quiet=quiet,
        )

        if cleanup:
            logger.debug("delete %r", filepath)
            os.remove(filepath)

        if quiet_view or view:
            self._view(rendered, self._format, quiet_view)

        return rendered

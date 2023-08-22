import pathlib

import blark.dependency_store
import pytest

from ..common import IocMetadata
from ..plugins import twincat_pytmc
from . import conftest

BLARK_ROOT = conftest.MODULE_PATH / "blark_root"

if not (BLARK_ROOT / "README.md").exists():
    pytest.fail(
        f"{BLARK_ROOT} is missing: whatrecord was likely not cloned with "
        "--recursive for this test suite submodule"
    )

twincat_projects = list(BLARK_ROOT.glob("**/*.tsproj"))
twincat_ioc_path = conftest.MODULE_PATH / "iocs" / "ioc_twincat"
project_a_path = BLARK_ROOT / "project_a" / "project_a" / "project_a.tsproj"
project_c_path = BLARK_ROOT / "project_c" / "project_c" / "project_c.tsproj"


@pytest.fixture
def project_c_md() -> IocMetadata:
    return IocMetadata(name="ioc_twincat", script=twincat_ioc_path / "st.cmd")


@pytest.fixture
def depstore(
    monkeypatch: pytest.MonkeyPatch,
) -> blark.dependency_store.DependencyStore:
    depstore = blark.dependency_store.DependencyStore(root=BLARK_ROOT)

    def _get_dep_store():
        return depstore

    monkeypatch.setattr(blark.dependency_store, "get_dependency_store", _get_dep_store)
    return depstore


def test_get_project_from_ioc(project_c_md: IocMetadata):
    _, makefile_contents, _ = twincat_pytmc.get_ioc_makefile(project_c_md)
    info = twincat_pytmc.get_project_from_ioc(project_c_md, makefile_contents)
    assert info is not None

    path, plc_name = info
    assert plc_name == "ProjectC"
    assert path == project_c_path


def test_plc_metadata_with_tmc(
    project_c_md: IocMetadata,
    depstore: blark.dependency_store.DependencyStore,
):
    # logging.getLogger("blark").setLevel("DEBUG")
    plc_md, = list(twincat_pytmc.PlcMetadata.from_ioc(project_c_md))

    assert plc_md.context[0].name == str(plc_md.filename)
    assert plc_md.name == "ProjectC"
    assert plc_md.include_dependencies
    expected_files = {
        'MAIN.TcPOU',
        'ProjectC.plcproj',
        'project_c.tsproj',
    }
    loaded_names = {pathlib.Path(file).name for file in plc_md.loaded_files}
    for fn in expected_files:
        assert fn in loaded_names

    assert plc_md.record_to_symbol == {
        # Simple pragma'd LREAL
        "PREFIX:fOutput": "ProjectC:MAIN.fOutput",
        "PREFIX:fOutput_RBV": "ProjectC:MAIN.fOutput",
        # Function block instance which refers back to SampleLibraryA
        "PREFIX:fbTest:fInput": "ProjectC:MAIN.fbTest.fInput",
        "PREFIX:fbTest:fInput_RBV": "ProjectC:MAIN.fbTest.fInput",
        "PREFIX:fbTest:fOutput_RBV": "ProjectC:MAIN.fbTest.fOutput",
    }

    assert plc_md.nc is not None
    assert len(plc_md.nc.axes) == 1
    axis = plc_md.nc.axes[0]
    assert axis.name == "Axis 1"
    assert pathlib.Path(axis.context[0].name).name == "Axis 1.xti"
    assert axis.units == "mm"

    assert set(plc_md.dependencies) == {"SampleLibraryA"}
    assert plc_md.dependencies["SampleLibraryA"] == blark.solution.DependencyVersion(
        name="SampleLibraryA",
        version="*",
        vendor="blark-testing",
        namespace="SampleLibraryA",
    )

    def check_context(md: twincat_pytmc.PlcSymbolMetadata, expected_files: list[str]):
        files = [pathlib.Path(ctx.name).name for ctx in md.context]
        assert set(files) == set(expected_files)

    # Simple symbol, with I/O records:
    sym = plc_md.symbols["ProjectC:MAIN.fOutput"]
    check_context(sym, ["MAIN.TcPOU"])
    assert sym.name == "ProjectC:MAIN.fOutput"
    assert sym.type == "LREAL"
    assert sym.records == ["PREFIX:fOutput_RBV", "PREFIX:fOutput"]

    # Symbol generated from a library FB input, with setpoint/rbv records:
    sym = plc_md.symbols['ProjectC:MAIN.fbTest.fInput']
    check_context(sym, ["MAIN.TcPOU", "FB_SampleA_Test.TcPOU"])
    assert sym.name == "ProjectC:MAIN.fbTest.fInput"
    assert sym.type == "LREAL (SampleLibraryA.FB_SampleA_Test)"
    assert sym.records == ["PREFIX:fbTest:fInput_RBV", "PREFIX:fbTest:fInput"]

    # Symbol generated from a library FB output, with only readback record:
    sym = plc_md.symbols['ProjectC:MAIN.fbTest.fOutput']
    check_context(sym, ["MAIN.TcPOU", "FB_SampleA_Test.TcPOU"])
    assert sym.name == "ProjectC:MAIN.fbTest.fOutput"
    assert sym.type == "LREAL (SampleLibraryA.FB_SampleA_Test)"
    assert sym.records == ["PREFIX:fbTest:fOutput_RBV"]

    assert depstore.get_dependency("project_c") is not None
    assert depstore.get_dependency("SampleLibraryA") is not None


def test_plc_metadata_without_tmc():
    (project_a,) = list(
        twincat_pytmc.PlcMetadata.from_project_filename(
            project_a_path,
            include_dependencies=False,
        )
    )
    assert not project_a.record_to_symbol
    assert not project_a.symbols
    assert "ProjectA.plcproj" in project_a.context[0].name


def test_empty_plugin_results():
    results = twincat_pytmc.TwincatPluginResults.from_metadata_items([])
    assert not results.nested


def test_plugin_results(project_c_md: IocMetadata):
    plc_md, = list(twincat_pytmc.PlcMetadata.from_ioc(project_c_md))
    results = twincat_pytmc.TwincatPluginResults.from_metadata_items(
        # Loading it twice to smoke test the 'merge' function
        [plc_md, plc_md]
    )
    assert results is not None

    # The TwinCAT Plugin uses "nested" metadata, allowing the server to
    # only give you per-project information if you want.  So not everything is
    # in the top-level dictionary.
    assert "PREFIX:fOutput_RBV" in results.nested["ProjectC"].record_to_metadata_keys
    assert "ProjectC:MAIN.fOutput" in results.nested["ProjectC"].metadata_by_key

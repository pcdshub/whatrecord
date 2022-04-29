import textwrap

import pytest

from .. import iocmanager


def test_parse_empty():
    assert iocmanager.parse_config([]) == []


@pytest.mark.parametrize(
    "source, expected",
    [
        pytest.param(
            textwrap.dedent(
                """\
        COMMITHOST = "psbuild-rhel7-01"

        hosts = [
           'amo-console',
           'ioc-amo-gige01',
           'ioc-amo-gige02',
           'ioc-amo-gige03',
           'ioc-amo-hv1',
           'ioc-amo-hv2',
           'ioc-amo-kbo-lvdt',
           'ioc-amo-lampenc01',
           'ioc-amo-las1',
           'ioc-amo-misc01',
           'ioc-amo-mot01',
           'ioc-amo-sdl',
           'ioc-amo-slits',
           'ioc-amo-uniq',
           'ioc-amo-vacuum',
           'ioc-det-pnccd01',
        ]

        procmgr_config = [
         {id:'ioc-amo-gige-01', host: 'ioc-amo-gige01', port: 30011, dir: 'ioc/amo/gigECam/R2.3.3',
          history: ['ioc/amo/gigECam/R2.3.3', '/reg/neh/home/sstubbs/work/amo/gigECam/current']},
         {id:'ioc-amo-gige-05', host: 'ioc-amo-gige01', port: 30015, dir: 'ioc/amo/gigECam/R2.3.3',
          history: ['ioc/amo/gigECam/R2.3.3']},
         {id:'ioc-amo-gige-06', host: 'ioc-amo-gige01', port: 30016, dir: 'ioc/amo/gigECam/R2.3.3',
          history: ['ioc/amo/gigECam/R2.3.3']},
         {id:'ioc-amo-gige-08', host: 'ioc-amo-gige01', port: 30029, dir: 'ioc/amo/gigECam/R2.3.3',
          history: ['ioc/amo/gigECam/R2.3.3']},
         {id:'ioc-amo-gige-09', host: 'ioc-amo-gige01', port: 30017, dir: 'ioc/amo/gigECam/R2.3.3',
          history: ['ioc/amo/gigECam/R2.3.3']},
         {id:'ioc-amo-usr-acromag', host: 'ioc-amo-gige01', port: 30001,
          dir: 'ioc/amo/pciAcromag/R1.0.4',
          history: ['ioc/amo/pciAcromag/R1.0.4']},
         {id:'ioc-amo-gige-02', host: 'ioc-amo-gige02', port: 30012, dir: 'ioc/amo/gigECam/R2.3.3',
          history: ['ioc/amo/gigECam/R2.3.3']},
         {id:'ioc-amo-gige-03', host: 'ioc-amo-gige02', port: 30013, dir: 'ioc/amo/gigECam/R2.3.3',
          history: ['ioc/amo/gigECam/R2.3.3']},
        ]
            """,
            ),
            [
                {
                    "id": "ioc-amo-gige-01",
                    "host": "ioc-amo-gige01",
                    "port": 30011,
                    "dir": "ioc/amo/gigECam/R2.3.3",
                    "history": [
                        "ioc/amo/gigECam/R2.3.3",
                        "/reg/neh/home/sstubbs/work/amo/gigECam/current",
                    ],
                },
                {
                    "id": "ioc-amo-gige-05",
                    "host": "ioc-amo-gige01",
                    "port": 30015,
                    "dir": "ioc/amo/gigECam/R2.3.3",
                    "history": ["ioc/amo/gigECam/R2.3.3"],
                },
                {
                    "id": "ioc-amo-gige-06",
                    "host": "ioc-amo-gige01",
                    "port": 30016,
                    "dir": "ioc/amo/gigECam/R2.3.3",
                    "history": ["ioc/amo/gigECam/R2.3.3"],
                },
                {
                    "id": "ioc-amo-gige-08",
                    "host": "ioc-amo-gige01",
                    "port": 30029,
                    "dir": "ioc/amo/gigECam/R2.3.3",
                    "history": ["ioc/amo/gigECam/R2.3.3"],
                },
                {
                    "id": "ioc-amo-gige-09",
                    "host": "ioc-amo-gige01",
                    "port": 30017,
                    "dir": "ioc/amo/gigECam/R2.3.3",
                    "history": ["ioc/amo/gigECam/R2.3.3"],
                },
                {
                    "id": "ioc-amo-usr-acromag",
                    "host": "ioc-amo-gige01",
                    "port": 30001,
                    "dir": "ioc/amo/pciAcromag/R1.0.4",
                    "history": ["ioc/amo/pciAcromag/R1.0.4"],
                },
                {
                    "id": "ioc-amo-gige-02",
                    "host": "ioc-amo-gige02",
                    "port": 30012,
                    "dir": "ioc/amo/gigECam/R2.3.3",
                    "history": ["ioc/amo/gigECam/R2.3.3"],
                },
                {
                    "id": "ioc-amo-gige-03",
                    "host": "ioc-amo-gige02",
                    "port": 30013,
                    "dir": "ioc/amo/gigECam/R2.3.3",
                    "history": ["ioc/amo/gigECam/R2.3.3"],
                },
            ],
            id="basic",
        ),
        pytest.param(
            textwrap.dedent(
                """\
                COMMITHOST = "psbuild-rhel7-01"

                hosts = [
                   'amo-console',
                   'ioc-amo-gige01',
                   'ioc-amo-gige02',
                   'ioc-amo-gige03',
                   'ioc-amo-hv1',
                   'ioc-amo-hv2',
                   'ioc-amo-kbo-lvdt',
                   'ioc-amo-lampenc01',
                   'ioc-amo-las1',
                   'ioc-amo-misc01',
                   'ioc-amo-mot01',
                   'ioc-amo-sdl',
                   'ioc-amo-slits',
                   'ioc-amo-uniq',
                   'ioc-amo-vacuum',
                   'ioc-det-pnccd01',
                ]

                procmgr_config = [
                     {id:'ioc-mec-gige11', host: 'ioc-mec-las-gige02',
                      port: 32511, dir: 'ioc/mec/gigECam/R1.1.1',
                      disable: True, alias: 'Gige Long Pulse 1',
                      history: ['ioc/mec/gigECam/R0.1.9']},
                    # {id:'ioc-mec-gige12', host: 'ioc-mec-las-gige02', port: 32512,
                    #  dir: 'ioc/mec/gigECam/R1.1.1', alias: 'Gige Long Pulse 2',
                    #  history: ['ioc/mec/gigECam/R0.1.9']},
                     {id:'ioc-mec-gige12', host: 'ioc-mec-las-gige02', port: 32512,
                      dir: '/cds/userpath', alias: 'Gige Long Pulse 2',
                      history: ['ioc/mec/gigECam/R0.1.9']},
                ]
            """,
            ),
            [
                {
                    "id": "ioc-mec-gige11",
                    "host": "ioc-mec-las-gige02",
                    "port": 32511,
                    "dir": "ioc/mec/gigECam/R1.1.1",
                    "disable": True,
                    "alias": "Gige Long Pulse 1",
                    "history": ["ioc/mec/gigECam/R0.1.9"],
                },
                {
                    "id": "ioc-mec-gige12",
                    "host": "ioc-mec-las-gige02",
                    "port": 32512,
                    "dir": "/cds/userpath",
                    "alias": "Gige Long Pulse 2",
                    "history": ["ioc/mec/gigECam/R0.1.9"],
                },
            ],
            id="commented",
        ),
    ]
)
def test_parse(source: str, expected: list, caplog: pytest.LogCaptureFixture):
    print(source)
    # print(source.splitlines())
    caplog.set_level("WARNING", logger=iocmanager.logger.name)
    assert iocmanager.parse_config(source.splitlines()) == expected
    assert not caplog.records, "No failure to parse messages"


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            textwrap.dedent(
                """\
                procmgr_config=[
                 syntax error id:'ioc-amo-gige-01', host: 'ioc-amo-gige01',
                    port: 30011, dir: 'ioc/amo/gigECam/R2.3.3',
                  history: ['ioc/amo/gigECam/R2.3.3',
                            '/reg/neh/home/sstubbs/work/amo/gigECam/current']},
                ]
            """,
            ),
            id="syntax-error-1"
        ),
        pytest.param(
            textwrap.dedent(
                """\
                procmgr_config=[
                 {id:ioc-amo-gige-01', host: 'ioc-amo-gige01', port: 30011,
                  dir: 'ioc/amo/gigECam/R2.3.3',
                  history: ['ioc/amo/gigECam/R2.3.3',
                            '/reg/neh/home/sstubbs/work/amo/gigECam/current']},
                ]
            """,
            ),
            id="syntax-error-2"
        ),
        pytest.param(
            textwrap.dedent(
                """\
                procmgr_config=[
                 {id:ioc-amo-gige-01', host: 'ioc-amo-gige01', port: 30011,
                  dir: 'ioc/amo/gigECam/R2.3.3',
                  history; ['ioc/amo/gigECam/R2.3.3',
                            '/reg/neh/home/sstubbs/work/amo/gigECam/current']},
                ]
            """,
            ),
            id="syntax-error-3"
        ),
    ]
)
def test_parse_failure(source: str, caplog: pytest.LogCaptureFixture):
    print(source)
    # print(source.splitlines())
    caplog.set_level("WARNING", logger=iocmanager.logger.name)
    assert iocmanager.parse_config(source.splitlines()) == []
    assert len(caplog.records) == 1, "Failure to parse id line"

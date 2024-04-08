import sys
from pathlib import Path
from types import ModuleType

import nbclient.exceptions
import pytest

import mitosis
from mitosis import _disk
from mitosis import unpack
from mitosis.__main__ import _split_param_str
from mitosis.__main__ import normalize_modinput
from mitosis._typing import ExpStep
from mitosis._typing import Parameter
from mitosis.tests import bad_return_experiment
from mitosis.tests import mock_legacy
from mitosis.tests import mock_paper
from mitosis.tests import mock_part1
from mitosis.tests import mock_part2


def test_reproduceable_dict():
    mydict = mitosis.StrictlyReproduceableDict(**{"1": print})
    assert str(mydict) == r"{'1': <builtin_function_or_method builtins.print>}"


def test_reproduceable_list():
    mylist = mitosis.StrictlyReproduceableList([1, print])
    assert str(mylist) == r"[1, <builtin_function_or_method builtins.print>]"


def test_unreproduceable_list():
    # test function in a local closure
    with pytest.raises(ValueError):
        str(mitosis.StrictlyReproduceableList([1, lambda x: 1]))


def test_reproduceable_list_of_strs():
    mylist = mitosis.StrictlyReproduceableList(["a"])
    assert str(mylist) == r"['a']"


def test_reproduceable_dict_of_strs():
    mylist = mitosis.StrictlyReproduceableDict({"a": "b"})
    assert str(mylist) == r"{'a': 'b'}"


def test_nested_reproduceable_classes():
    mylist = mitosis.StrictlyReproduceableList([print])
    mylist = mitosis.StrictlyReproduceableList([mylist])
    mydict = mitosis.StrictlyReproduceableDict(a=mylist)
    mydict = mitosis.StrictlyReproduceableDict(b=mydict)
    result = str(mydict)
    assert result == r"{'b': {'a': [[<builtin_function_or_method builtins.print>]]}}"


def mock_global_f():
    pass


mock_global_f.__module__ = "__main__"


def test_unreproduceable_dict():
    # test function in a local closure
    def mock_local_f():
        pass

    with pytest.raises(ImportError):
        str(mitosis.StrictlyReproduceableDict(**{"1": mock_local_f}))

    # test function defined in __main__
    mock_global_f.__module__ = "__main__"
    with pytest.raises(ImportError):
        str(mitosis.StrictlyReproduceableDict(**{"1": mock_global_f}))
    mock_global_f.__module__ = __name__

    # test unimportable module
    newmod = ModuleType("_mockmod")
    setattr(newmod, "mock_global_f", mock_global_f)
    mock_global_f.__module__ = newmod.__name__
    with pytest.raises(ImportError):
        str(mitosis.StrictlyReproduceableDict(**{"1": mock_global_f}))
    mock_global_f.__module__ = __name__

    # test module missing name
    newmod = ModuleType("_mockmod")
    mock_global_f.__module__ = newmod.__name__
    sys.modules["_mockmod"] = newmod
    with pytest.raises(ImportError):
        str(mitosis.StrictlyReproduceableDict(**{"1": mock_global_f}))
    mock_global_f.__module__ = __name__
    sys.modules.pop("_mockmod")

    # test lambda function
    with pytest.raises(ValueError):
        str(mitosis.StrictlyReproduceableDict(**{"1": lambda x: 1}))


def test_kernel_name():
    mitosis._create_kernel()


@pytest.fixture
def fake_eval_param():
    return mitosis.Parameter("1", "seed", 1, evaluate=True)


@pytest.fixture
def fake_lookup_param():
    return mitosis.Parameter("test", "foo", 2, evaluate=False)


@pytest.fixture()
def mock_steps():
    return [
        # fmt: off
        ExpStep(
            "foo",
            mock_part1.Klass.gen_data, "mitosis.tests.mock_part1:Klass.gen_data",
            mock_paper.data_config, "mitosis.tests.mock_paper:data_config",
            None,
            [
                Parameter("test", "length", 5, evaluate=False),
                Parameter("True", "extra", True, evaluate=True),
            ],
            []
        ),
        ExpStep(
            "bar",
            mock_part2.fit_and_score, "mitosis.tests.mock_part2:fit_and_score",
            mock_paper.meth_config, "mitosis.tests.mock_paper:meth_config",
            None,
            [
                Parameter("test", "metric", "len", evaluate=False),
            ],
            []
        )
        # fmt: on
    ]


def test_mock_experiment(mock_steps, tmp_path):
    exp_key = mitosis.run(
        mock_steps,
        debug=True,
        trials_folder=tmp_path,
    )
    data = mitosis.load_trial_data(exp_key, trials_folder=tmp_path)
    assert len(data[1]["data"]) == 5


def test_empty_mod_logging_debug(tmp_path):
    hexstr = mitosis.run(
        mock_legacy,
        debug=True,
        trials_folder=tmp_path,
        params=[],
    )
    trial_folder = _disk._locate_trial_folder(hexstr, trials_folder=tmp_path)
    with open(trial_folder / f"{mock_legacy.__name__}.log") as f:
        log_str = "".join(f.readlines())
    assert "This is run every time" in log_str
    assert "This is run in debug mode only" in log_str


@pytest.mark.clean
def test_empty_mod_logging(tmp_path):
    hexstr = mitosis.run(
        mock_legacy,
        debug=False,
        trials_folder=tmp_path,
        params=[],
    )
    trial_folder = _disk._locate_trial_folder(hexstr, trials_folder=tmp_path)
    with open(trial_folder / f"{mock_legacy.__name__}.log") as f:
        log_str = "".join(f.readlines())
    assert "This is run every time" in log_str
    assert "This is run in debug mode only" not in log_str


def test_split_param_str():
    result = _split_param_str("+a=b")
    assert result == ("", False, "a", "b")
    result = _split_param_str("a.b=c")
    assert result == ("a", True, "b", "c")


def test_malfored_return_experiment(tmp_path):
    with pytest.raises(nbclient.exceptions.CellExecutionError):
        mitosis.run(
            bad_return_experiment,
            debug=True,
            trials_folder=tmp_path,
            params=[],
        )


def test_load_toml():
    parent = Path(__file__).resolve().parent
    tomlfile = parent / "test_pyproject.toml"
    result = _disk.load_mitosis_steps(tomlfile)
    expected = {
        "data": (
            "mitosis.tests.mock_part1:Klass.gen_data",
            "mitosis.tests.mock_paper:data_config",
        ),
        "fit_eval": (
            "mitosis.tests.mock_part2:fit_and_score",
            "mitosis.tests.mock_paper:meth_config",
        ),
    }
    assert result == expected


def test_load_bad_toml():
    parent = Path(__file__).resolve().parent
    tomlfile = parent / "pyproject_missing.toml"
    with pytest.raises(RuntimeError, match="does not have a tools"):
        _disk.load_mitosis_steps(tomlfile)
    tomlfile = parent / "pyproject_malformed.toml"
    with pytest.raises(RuntimeError, match="table is malformed"):
        _disk.load_mitosis_steps(tomlfile)


def test_unpack():
    from importlib.metadata import version

    obj_ref = "importlib.metadata:version"
    result = unpack(obj_ref)
    assert result is version


def test_normalize_modinput():
    modinput = "mitosis.tests.mock_experiment"
    result = normalize_modinput(modinput)
    assert result == {
        "mitosis.tests.mock_experiment": (
            "mitosis.tests.mock_experiment:run",
            "mitosis.tests.mock_experiment:lookup_dict",
        )
    }
    # if modinput is an object, connect to run and lookup_dict with . not :
    modinput = "mitosis.tests.mock_experiment:MockExp.MockExpInner"
    result = normalize_modinput(modinput)
    assert result == {
        "mitosis.tests.mock_experiment:MockExp.MockExpInner": (
            "mitosis.tests.mock_experiment:MockExp.MockExpInner.run",
            "mitosis.tests.mock_experiment:MockExp.MockExpInner.lookup_dict",
        )
    }

"""Principle 1: the test suite runs with sockets disabled, so any accidental network call fails."""

import importlib
import pkgutil
import socket

import pytest
from pytest_socket import SocketBlockedError

import descargo


@pytest.mark.filterwarnings("ignore:A test tried to use socket:UserWarning")
def test_sockets_are_blocked() -> None:
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def test_importing_every_module_opens_no_socket() -> None:
    for module in pkgutil.walk_packages(descargo.__path__, prefix="descargo."):
        if module.name == "descargo.__main__":
            continue
        importlib.import_module(module.name)

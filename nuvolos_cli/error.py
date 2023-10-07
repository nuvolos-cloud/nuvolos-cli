import sys
from .logging import clog


def nuvolos_info(msg, exit=False):
    clog.info(msg)
    if exit:
        sys.exit()
    return


def nuvolos_debug(msg, exit=False):
    clog.debug(msg)
    if exit:
        sys.exit()
    return


def nuvolos_error(msg, exit=True):
    clog.error(msg)
    if exit:
        sys.exit()
    return


def nuvolos_critical(msg, exit=True):
    clog.critical(msg)
    if exit:
        sys.exit()
    return


def nuvolos_warning(msg, exit=True):
    clog.warning(msg)
    if exit:
        sys.exit()
    return

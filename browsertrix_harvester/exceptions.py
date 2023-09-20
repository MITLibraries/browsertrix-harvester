"""browsertrix_harvest.exceptions."""
# ruff: noqa: N818


class RequiresContainerContextError(Exception):
    pass


class WaczFileDoesNotExist(Exception):
    pass


class ConfigYamlError(Exception):
    pass

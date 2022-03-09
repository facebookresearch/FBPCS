#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict
from yaml import YAMLError


class ConfigYamlBaseException(Exception):
    pass


class ConfigYamlFieldNotFoundError(KeyError, ConfigYamlBaseException):
    """Raised when a ConfigYamlDict key access fails"""

    def __init__(self, key: str) -> None:
        msg = f"{key} is expected in your config.yml file but was not found. Please make sure your config is up to date."
        super().__init__(msg)


class ConfigYamlModuleImportError(ImportError, ConfigYamlBaseException):
    """Raised when a module path cannot be imported"""

    def __init__(self, class_path: str) -> None:
        msg = f"{class_path} (specified in your config.yml) could not be imported (module not found). Please make sure that your config is up to date."
        super().__init__(msg)


class ConfigYamlClassNotFoundError(AttributeError, ConfigYamlBaseException):
    """Raised when a class is not found at a given module path"""

    def __init__(self, class_path: str) -> None:
        msg = f"{class_path} (specified in your config.yml) could not be imported (class not found). Please make sure that your config is up to date."
        super().__init__(msg)


class ConfigYamlWrongClassConfiguredError(AssertionError, ConfigYamlBaseException):
    """Raised when the type of a class loaded through reflection is different than expected"""

    def __init__(self, class_path: str, target_class_name: str) -> None:
        msg = f"{class_path} (specified in your config.yml) is the wrong type - it should be a {target_class_name}. Please make sure that your config is up to date."
        super().__init__(msg)


class ConfigYamlWrongConstructorError(TypeError, ConfigYamlBaseException):
    """Raised when the arguments passed to a constructor are incorrect"""

    def __init__(self, class_name: str, cause: str) -> None:
        msg = f"{class_name} (specified in your config.yml) does not have the correct arguments. {cause}. Please make sure that your config is up to date."
        super().__init__(msg)


class ConfigYamlValidationError(ValueError, ConfigYamlBaseException):
    """Raise when a config.yml fails validation"""

    def __init__(self, class_name: str, cause: str, remediation: str) -> None:
        msg = f"{class_name} (specified in your config.yml) failed validation. Cause: {cause}. Suggested remediation: {remediation}"
        super().__init__(msg)


class ConfigYamlFileParsingError(YAMLError, ConfigYamlBaseException):
    """Raised when the content of file is not in a valid YAML format"""

    def __init__(self, file_name: str, cause: str) -> None:
        msg = f"{file_name} is not a valid YAML file. Please make sure that your config file is valid YAML file.\nCause: {cause}."
        super().__init__(msg)

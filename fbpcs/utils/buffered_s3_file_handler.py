#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import contextlib
import pathlib
import tempfile
from typing import Optional

from fbpcp.service.storage_s3 import S3StorageService


class BufferedS3Reader(contextlib.AbstractContextManager):
    def __init__(self, s3_path: pathlib.Path, storage_service: S3StorageService):
        self.s3_path = s3_path
        self.storage_service = storage_service
        self.data: Optional[str] = None
        self.cursor = 0

    def __enter__(self):
        self.data = self.storage_service.read(str(self.s3_path))
        return self

    def __exit__(self, *exc):
        pass

    def seek(self, idx: int) -> None:
        data = self.data
        if data is None:
            raise ValueError("BufferedS3Reader: data is None")
        self.cursor = min(idx, len(data))

    def read(self, chars: int = 0) -> str:
        data = self.data
        if data is None:
            raise ValueError("BufferedS3Reader: data is None")
        if chars > 0:
            res = data[self.cursor : self.cursor + chars]
            self.cursor += chars
        else:
            res = data[self.cursor :]
            self.cursor = len(data)
        return res

    def copy_to_local(self) -> pathlib.Path:
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(str(self.data))
            return pathlib.Path(f.name)


class BufferedS3Writer(contextlib.AbstractContextManager):
    def __init__(self, s3_path: pathlib.Path, storage_service: S3StorageService):
        self.s3_path = s3_path
        self.storage_service = storage_service
        self.written = False
        self.buffer = ""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if not self.written:
            self.storage_service.write(str(self.s3_path), self.buffer)
            self.written = True

    def __del__(self):
        self.__exit__()

    def write(self, data: str) -> None:
        self.buffer += data

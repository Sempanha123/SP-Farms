import base64
import json
import os
from dataclasses import dataclass
from typing import Protocol

import keyring
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

_SERVICE_NAME = "SP-Farms"
_ARCHIVE_VERSION = 1


class KeyringBackend(Protocol):
    def set_password(self, service: str, username: str, password: str) -> None: ...

    def get_password(self, service: str, username: str) -> str | None: ...

    def delete_password(self, service: str, username: str) -> None: ...


class KeyringVault:
    def __init__(self, backend: KeyringBackend | None = None) -> None:
        self._backend = backend or keyring

    def store(self, reference: str, value: str) -> None:
        self._backend.set_password(_SERVICE_NAME, reference, value)

    def retrieve(self, reference: str) -> str | None:
        return self._backend.get_password(_SERVICE_NAME, reference)

    def delete(self, reference: str) -> None:
        self._backend.delete_password(_SERVICE_NAME, reference)


@dataclass(frozen=True, slots=True)
class EncryptedSecretArchive:
    version: int
    salt: str
    nonce: str
    ciphertext: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "version": self.version,
                "salt": self.salt,
                "nonce": self.nonce,
                "ciphertext": self.ciphertext,
            },
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, value: str) -> "EncryptedSecretArchive":
        data = json.loads(value)
        return cls(
            version=int(data["version"]),
            salt=str(data["salt"]),
            nonce=str(data["nonce"]),
            ciphertext=str(data["ciphertext"]),
        )


def encrypt_secret(value: str, passphrase: str) -> EncryptedSecretArchive:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(passphrase, salt)
    ciphertext = AESGCM(key).encrypt(nonce, value.encode("utf-8"), None)
    return EncryptedSecretArchive(
        version=_ARCHIVE_VERSION,
        salt=_encode(salt),
        nonce=_encode(nonce),
        ciphertext=_encode(ciphertext),
    )


def decrypt_secret(archive: EncryptedSecretArchive, passphrase: str) -> str:
    if archive.version != _ARCHIVE_VERSION:
        raise ValueError(f"Unsupported secret archive version: {archive.version}")
    salt = _decode(archive.salt)
    nonce = _decode(archive.nonce)
    ciphertext = _decode(archive.ciphertext)
    key = _derive_key(passphrase, salt)
    return AESGCM(key).decrypt(nonce, ciphertext, None).decode("utf-8")


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode("utf-8"))


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))

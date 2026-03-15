"""Encryption interfaces (Ports).

Abstract contract for encryption/decryption operations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class EncryptionInfo:
    """Information about encryption status."""
    algorithm: str
    key_size_bits: int
    status: str  # "loaded", "no_key", "error"
    key_fingerprint: Optional[str] = None
    message: Optional[str] = None


class Encryptor(ABC):
    """Abstract base class for encryption operations."""

    @abstractmethod
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext and return ciphertext."""
        pass

    @abstractmethod
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext and return plaintext."""
        pass

    @abstractmethod
    def get_info(self) -> EncryptionInfo:
        """Get information about encryption status."""
        pass

from __future__ import annotations

import math
import secrets
import string
from dataclasses import dataclass
from typing import Iterable

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerifyMismatchError,
)

from hmac import compare_digest


# ==========================================================
# Password Policy
# ==========================================================

@dataclass(slots=True)
class PasswordPolicy:

    minimum_length: int = 12

    maximum_length: int = 128

    require_uppercase: bool = True

    require_lowercase: bool = True

    require_number: bool = True

    require_symbol: bool = True

    prevent_username: bool = True

    prevent_email: bool = True

    minimum_entropy: float = 60.0

    history: int = 5


DEFAULT_POLICY = PasswordPolicy()


# ==========================================================
# Argon2 Configuration
# ==========================================================

PASSWORD_HASHER = PasswordHasher(

    time_cost=3,

    memory_cost=65536,

    parallelism=4,

    hash_len=32,

    salt_len=16,

)


# ==========================================================
# Password Service
# ==========================================================

class PasswordService:

    def __init__(
        self,
        policy: PasswordPolicy | None = None,
    ):

        self.policy = policy or DEFAULT_POLICY

        self.hasher = PASSWORD_HASHER


# ==========================================================
# Hash Password
# ==========================================================

    def hash_password(
        self,
        password: str,
    ) -> str:

        return self.hasher.hash(password)


# ==========================================================
# Verify Password
# ==========================================================

    def verify_password(
        self,
        password: str,
        password_hash: str,
    ) -> bool:

        try:

            return self.hasher.verify(
                password_hash,
                password,
            )

        except (

            VerifyMismatchError,

            InvalidHashError,

        ):

            return False


# ==========================================================
# Needs Rehash
# ==========================================================

    def needs_rehash(
        self,
        password_hash: str,
    ) -> bool:

        return self.hasher.check_needs_rehash(
            password_hash
        )


# ==========================================================
# Upgrade Hash
# ==========================================================

    def upgrade_hash(
        self,
        password: str,
        password_hash: str,
    ) -> str | None:

        if not self.verify_password(
            password,
            password_hash,
        ):

            return None

        if not self.needs_rehash(
            password_hash,
        ):

            return None

        return self.hash_password(password)


# ==========================================================
# Constant Time Comparison
# ==========================================================

    @staticmethod
    def secure_compare(
        value1: str,
        value2: str,
    ) -> bool:

        return compare_digest(
            value1.encode(),
            value2.encode(),
        )
        
        # ==========================================================
# Password Character Sets
# ==========================================================

UPPERCASE = set(string.ascii_uppercase)

LOWERCASE = set(string.ascii_lowercase)

DIGITS = set(string.digits)

SYMBOLS = set(string.punctuation)


# ==========================================================
# Character Diversity
# ==========================================================

    def character_diversity(
        self,
        password: str,
    ) -> dict:

        return {

            "uppercase": any(
                c in UPPERCASE for c in password
            ),

            "lowercase": any(
                c in LOWERCASE for c in password
            ),

            "digits": any(
                c in DIGITS for c in password
            ),

            "symbols": any(
                c in SYMBOLS for c in password
            ),

        }


# ==========================================================
# Password Entropy
# ==========================================================

    def entropy(
        self,
        password: str,
    ) -> float:

        charset = 0

        diversity = self.character_diversity(
            password
        )

        if diversity["lowercase"]:
            charset += 26

        if diversity["uppercase"]:
            charset += 26

        if diversity["digits"]:
            charset += 10

        if diversity["symbols"]:
            charset += len(string.punctuation)

        if charset == 0:

            return 0.0

        return round(

            len(password)

            * math.log2(charset),

            2,

        )


# ==========================================================
# Password Score
# ==========================================================

    def strength_score(
        self,
        password: str,
    ) -> int:

        score = 0

        length = len(password)

        entropy = self.entropy(password)

        if length >= 12:
            score += 20

        if length >= 16:
            score += 20

        if entropy >= 60:
            score += 20

        if entropy >= 80:
            score += 20

        diversity = self.character_diversity(
            password
        )

        score += sum(

            5

            for value in diversity.values()

            if value

        )

        score = min(score, 100)

        return score


# ==========================================================
# Strength Label
# ==========================================================

    def strength_label(
        self,
        password: str,
    ) -> str:

        score = self.strength_score(
            password
        )

        if score >= 90:
            return "excellent"

        if score >= 75:
            return "strong"

        if score >= 60:
            return "good"

        if score >= 40:
            return "fair"

        return "weak"


# ==========================================================
# Common Password Detection
# ==========================================================

    def is_common_password(
        self,
        password: str,
        common_passwords: Iterable[str],
    ) -> bool:

        candidate = password.casefold()

        for common in common_passwords:

            if compare_digest(

                candidate,

                common.casefold(),

            ):

                return True

        return False


# ==========================================================
# Password Validation
# ==========================================================

    def validate_password(
        self,
        password: str,
        username: str | None = None,
        email: str | None = None,
        common_passwords: Iterable[str] | None = None,
    ) -> list[str]:

        errors: list[str] = []

        policy = self.policy

        if len(password) < policy.minimum_length:

            errors.append(

                f"Password must contain at least {policy.minimum_length} characters."

            )

        if len(password) > policy.maximum_length:

            errors.append(

                f"Password cannot exceed {policy.maximum_length} characters."

            )

        diversity = self.character_diversity(
            password
        )

        if policy.require_uppercase and not diversity["uppercase"]:

            errors.append(
                "Password must contain an uppercase letter."
            )

        if policy.require_lowercase and not diversity["lowercase"]:

            errors.append(
                "Password must contain a lowercase letter."
            )

        if policy.require_number and not diversity["digits"]:

            errors.append(
                "Password must contain a number."
            )

        if policy.require_symbol and not diversity["symbols"]:

            errors.append(
                "Password must contain a special character."
            )
            
            # ==========================================================
# Username / Email Validation
# ==========================================================

    def contains_username(
        self,
        password: str,
        username: str | None,
    ) -> bool:

        if not username:
            return False

        username = username.strip().casefold()

        if len(username) < 3:
            return False

        return username in password.casefold()


    def contains_email(
        self,
        password: str,
        email: str | None,
    ) -> bool:

        if not email:
            return False

        local = email.split("@")[0].strip().casefold()

        if len(local) < 3:
            return False

        return local in password.casefold()


# ==========================================================
# Sequential Character Detection
# ==========================================================

    def has_sequential_characters(
        self,
        password: str,
        sequence_length: int = 4,
    ) -> bool:

        password = password.lower()

        alphabet = string.ascii_lowercase

        numbers = string.digits

        for i in range(len(alphabet) - sequence_length + 1):

            if alphabet[i:i + sequence_length] in password:

                return True

        for i in range(len(numbers) - sequence_length + 1):

            if numbers[i:i + sequence_length] in password:

                return True

        return False


# ==========================================================
# Repeated Character Detection
# ==========================================================

    def has_repeated_characters(
        self,
        password: str,
        repeat_limit: int = 4,
    ) -> bool:

        count = 1

        previous = ""

        for character in password:

            if character == previous:

                count += 1

                if count >= repeat_limit:

                    return True

            else:

                count = 1

            previous = character

        return False


# ==========================================================
# Keyboard Pattern Detection
# ==========================================================

    def has_keyboard_pattern(
        self,
        password: str,
    ) -> bool:

        patterns = [

            "qwerty",

            "asdf",

            "zxcv",

            "12345",

            "password",

            "admin",

            "letmein",

            "welcome",

        ]

        candidate = password.casefold()

        return any(

            pattern in candidate

            for pattern in patterns

        )


# ==========================================================
# Password History
# ==========================================================

    def is_reused_password(
        self,
        password: str,
        previous_hashes: Iterable[str],
    ) -> bool:

        for password_hash in previous_hashes:

            if self.verify_password(

                password,

                password_hash,

            ):

                return True

        return False


# ==========================================================
# Continue Validation
# ==========================================================

        if (
            policy.prevent_username
            and
            self.contains_username(
                password,
                username,
            )
        ):

            errors.append(

                "Password cannot contain your username."

            )

        if (
            policy.prevent_email
            and
            self.contains_email(
                password,
                email,
            )
        ):

            errors.append(

                "Password cannot contain your email."

            )

        if self.entropy(password) < policy.minimum_entropy:

            errors.append(

                f"Password entropy must be at least {policy.minimum_entropy:.0f} bits."

            )

        if self.has_sequential_characters(
            password
        ):

            errors.append(

                "Password contains sequential characters."

            )

        if self.has_repeated_characters(
            password
        ):

            errors.append(

                "Password contains repeated characters."

            )

        if self.has_keyboard_pattern(
            password
        ):

            errors.append(

                "Password contains common keyboard patterns."

            )

        if (
            common_passwords
            and
            self.is_common_password(
                password,
                common_passwords,
            )
        ):

            errors.append(

                "Password is too common."

            )

        return errors
        
        # ==========================================================
# Secure Password Generator
# ==========================================================

    def generate_password(
        self,
        length: int = 20,
    ) -> str:

        if length < self.policy.minimum_length:

            length = self.policy.minimum_length

        alphabet = (
            string.ascii_letters
            + string.digits
            + string.punctuation
        )

        while True:

            password = "".join(

                secrets.choice(alphabet)

                for _ in range(length)

            )

            if not self.validate_password(password):

                return password


# ==========================================================
# Passphrase Generator
# ==========================================================

    def generate_passphrase(
        self,
        words: list[str],
        count: int = 5,
        separator: str = "-",
    ) -> str:

        if len(words) < count:

            raise ValueError(
                "Word list too small."
            )

        selected = [

            secrets.choice(words)

            for _ in range(count)

        ]

        return separator.join(selected)


# ==========================================================
# Pronounceable Password
# ==========================================================

    def generate_pronounceable(
        self,
        syllables: int = 5,
    ) -> str:

        consonants = (
            "bcdfghjklmnpqrstvwxyz"
        )

        vowels = "aeiou"

        result = []

        for _ in range(syllables):

            result.append(

                secrets.choice(consonants)

            )

            result.append(

                secrets.choice(vowels)

            )

        result.append(

            secrets.choice(string.digits)

        )

        result.append(

            secrets.choice("!@#$%^&*")

        )

        password = "".join(result)

        return password.capitalize()


# ==========================================================
# Password Mask
# ==========================================================

    @staticmethod
    def mask(
        password: str,
        visible: int = 2,
    ) -> str:

        if len(password) <= visible:

            return "*" * len(password)

        return (

            password[:visible]

            + "*" * (len(password) - visible)

        )


# ==========================================================
# Password Statistics
# ==========================================================

    def statistics(
        self,
        password: str,
    ) -> dict:

        return {

            "length": len(password),

            "entropy": self.entropy(password),

            "strength":

                self.strength_score(password),

            "label":

                self.strength_label(password),

            "diversity":

                self.character_diversity(password),

            "contains_sequence":

                self.has_sequential_characters(
                    password
                ),

            "contains_repetition":

                self.has_repeated_characters(
                    password
                ),

            "contains_keyboard_pattern":

                self.has_keyboard_pattern(
                    password
                ),

        }


# ==========================================================
# Compliance Report
# ==========================================================

    def compliance_report(
        self,
        password: str,
        username: str | None = None,
        email: str | None = None,
    ) -> dict:

        errors = self.validate_password(

            password,

            username=username,

            email=email,

        )

        return {

            "compliant":

                len(errors) == 0,

            "errors":

                errors,

            "statistics":

                self.statistics(password),

            "policy":

                self.policy,

        }
        
        # ==========================================================
# Password History
# ==========================================================

    def validate_password_history(
        self,
        password: str,
        previous_hashes: Iterable[str],
    ) -> bool:
        """
        Returns True when the password has never been used.
        """

        return not self.is_reused_password(
            password=password,
            previous_hashes=previous_hashes,
        )


# ==========================================================
# Automatic Hash Migration
# ==========================================================

    def verify_and_upgrade(
        self,
        password: str,
        password_hash: str,
    ) -> tuple[bool, str | None]:
        """
        Returns:
            (
                verified,
                upgraded_hash
            )
        """

        verified = self.verify_password(
            password=password,
            password_hash=password_hash,
        )

        if not verified:

            return False, None

        if self.needs_rehash(password_hash):

            return True, self.hash_password(password)

        return True, None


# ==========================================================
# Bulk Password Audit
# ==========================================================

    def audit_passwords(
        self,
        passwords: Iterable[str],
    ) -> list[dict]:

        results = []

        for password in passwords:

            results.append(

                {

                    "password": self.mask(password),

                    "score": self.strength_score(password),

                    "label": self.strength_label(password),

                    "entropy": self.entropy(password),

                    "compliant": len(
                        self.validate_password(password)
                    ) == 0,

                }

            )

        return results


# ==========================================================
# Overall Security Score
# ==========================================================

    def security_score(
        self,
        password: str,
    ) -> float:

        report = self.compliance_report(password)

        score = float(
            report["statistics"]["strength"]
        )

        if not report["compliant"]:

            deductions = min(
                len(report["errors"]) * 5,
                40,
            )

            score -= deductions

        return round(max(score, 0.0), 2)


# ==========================================================
# Service Diagnostics
# ==========================================================

    def health(self) -> dict:

        return {

            "service": "PasswordService",

            "algorithm": "Argon2id",

            "policy": {

                "minimum_length": self.policy.minimum_length,

                "maximum_length": self.policy.maximum_length,

                "minimum_entropy": self.policy.minimum_entropy,

                "history": self.policy.history,

            },

            "status": "healthy",

        }


# ==========================================================
# Singleton Instance
# ==========================================================

password_service = PasswordService()


# ==========================================================
# Convenience Functions
# ==========================================================

hash_password = password_service.hash_password

verify_password = password_service.verify_password

validate_password = password_service.validate_password

generate_password = password_service.generate_password

generate_passphrase = password_service.generate_passphrase

generate_pronounceable = (
    password_service.generate_pronounceable
)

strength_score = password_service.strength_score

strength_label = password_service.strength_label

security_score = password_service.security_score


# ==========================================================
# Public Exports
# ==========================================================

__all__ = [

    "PasswordPolicy",

    "PasswordService",

    "password_service",

    "hash_password",

    "verify_password",

    "validate_password",

    "generate_password",

    "generate_passphrase",

    "generate_pronounceable",

    "strength_score",

    "strength_label",

    "security_score",

]
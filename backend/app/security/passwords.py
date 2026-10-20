import re

_COMMON = {
    "password", "123456789", "1234567890", "qwertyuiop", "iloveyou12", "senha12345",
    "password123", "letmein123", "admin12345", "welcome123", "gamefy1234", "abc1234567",
}


def validate_password(password: str, email: str = "") -> list[str]:
    """Return a list of problems (empty = acceptable). Length over complexity (NIST 800-63B),
    plus a few cheap sanity checks. Hard cap protects the hasher from huge inputs."""
    problems: list[str] = []
    if len(password) < 10:
        problems.append("Use at least 10 characters.")
    if len(password) > 128:
        problems.append("Use at most 128 characters.")
    low = password.lower()
    if low in _COMMON or re.fullmatch(r"(.)\1+", password or ""):
        problems.append("This password is too common.")
    local = email.split("@")[0].lower()
    if len(local) >= 4 and local in low:
        problems.append("Do not include your email name in the password.")
    if len(set(password)) < 5:
        problems.append("Use a more varied password.")
    return problems

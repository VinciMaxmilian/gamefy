"""TLS verification setting for outbound HTTP clients.

On Windows/macOS, use the OS certificate store (via `truststore`) so corporate TLS-inspection proxies —
trusted by the OS but unknown to Python's bundled certifi list — do not cause CERTIFICATE_VERIFY_FAILED.
Everywhere else (Linux, Vercel, CI) keep httpx's default verification."""
import ssl
import sys


def client_verify() -> "ssl.SSLContext | bool":
    if sys.platform in ("win32", "darwin"):
        try:
            import truststore
            return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except ImportError:
            pass
    return True

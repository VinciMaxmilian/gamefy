"""Use the operating system's certificate store on Windows/macOS.

Corporate networks often re-sign HTTPS with a company root CA that the OS trusts but Python's bundled
certifi list does not, causing "CERTIFICATE_VERIFY_FAILED". `truststore` makes Python use the OS store.
Skipped elsewhere (Linux/CI already work and may rely on custom bundles)."""
import sys


def use_system_trust_store() -> bool:
    if sys.platform not in ("win32", "darwin"):
        return False
    try:
        import truststore
        truststore.inject_into_ssl()
        return True
    except ImportError:
        print("TIP: if you see CERTIFICATE_VERIFY_FAILED on a corporate network, run: pip install truststore")
        return False

# Shared pytest configuration.
#
# The older test_iter*/test_sanctuary/test_library_* files are live-server tests: set REACT_APP_BACKEND_URL
# (e.g. http://<nuc-ip>:8091) and they call that running stack over HTTP. test_security_hardening.py is
# self-contained and needs no server.

"""Developer tooling. Not the application.

`src/` is the application, and a guard in `tests/test_interop.py` refuses any
HTTP client there — this build plans outbound calls and never sends them, and
the way to keep that true is for the code that could send one not to exist.

`carlos stop` has to ask a running server which process it is, which means an
HTTP client. That is a developer asking a local server a question, not the
application reaching the network, and the two live in different directories so
the guard can tell them apart without being weakened.
"""

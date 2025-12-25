from importlib import import_module


def test_import_page_does_not_raise_session_state_error():
    # Importing the module should not raise errors about widget default vs session_state set
    mod = import_module("mie_lib.pages.m_chain")
    assert hasattr(mod, "main")


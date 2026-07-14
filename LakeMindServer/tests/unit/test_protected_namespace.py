from __future__ import annotations
from lakemind_server.security.protected_namespace import is_protected, assert_writable


class TestProtectedNamespace:
    def test_protected_path_detected(self):
        assert is_protected("ten_abc/ast_xyz/file.txt")

    def test_non_protected_path(self):
        assert not is_protected("mybucket/myfile.txt")

    def test_writable_by_owner(self):
        assert_writable("ten_a/ast_x/file.txt", "ten_a")

    def test_not_writable_by_other(self):
        try:
            assert_writable("ten_b/ast_x/file.txt", "ten_a")
            assert False, "Should have raised"
        except PermissionError:
            pass

    def test_platform_admin_can_write_any(self):
        assert_writable("ten_b/ast_x/file.txt", "ten_a", is_platform_admin=True)

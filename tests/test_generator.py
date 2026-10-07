"""Tests of the binding generator (tools/gen). They do not need CEF to run, only its headers.

The headers are read from build/native/cef (see `python tools/prepare.py`); the tests that
need them are skipped when they are missing.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CEF_ROOT = os.path.join(ROOT, "build", "native", "cef")
sys.path.insert(0, os.path.join(ROOT, "tools", "gen"))

import model  # noqa: E402
from typesys import Enum, LibRef, Prim, Str, Void  # noqa: E402

HAS_HEADERS = os.path.isfile(os.path.join(CEF_ROOT, "include", "cef_version.h"))


class Naming(unittest.TestCase):
    def test_snake_case(self):
        cases = {
            "GetURL": "get_url",
            "OnLoadEnd": "on_load_end",
            "IsReadOnly": "is_read_only",
            "SetHeaderByName": "set_header_by_name",
            "GetResourceType": "get_resource_type",
            "HTTPStatus": "http_status",
            "Open": "open",
        }
        for cef_name, expected in cases.items():
            self.assertEqual(model.snake_case(cef_name), expected, cef_name)

    def test_python_keywords_get_an_underscore(self):
        self.assertEqual(model.py_method_name("Continue"), "continue_")
        self.assertEqual(model.py_param_name("from"), "from_")

    def test_class_names_lose_the_cef_prefix(self):
        self.assertEqual(model.py_class_name("CefResourceHandler"), "ResourceHandler")
        self.assertEqual(model.py_class_name("Other"), "Other")


@unittest.skipUnless(HAS_HEADERS, "needs the CEF headers (python tools/prepare.py)")
class WithHeaders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scope import Scope
        from typesys import plan_method
        cls.plan_method = staticmethod(plan_method)
        cls.model = model.Model(CEF_ROOT)
        cls.scope = Scope.current(cls.model)

    def plan(self, cls_name, method_name):
        cls = self.model.classes[cls_name]
        for method in list(cls.get_virtual_funcs()) + list(cls.get_static_funcs()):
            if method.get_name() == method_name:
                return self.plan_method(self.model, self.scope, cls_name, method,
                                        client_side=cls.is_client_side())
        raise KeyError(method_name)

    def test_the_class_name_comes_from_the_declaration(self):
        # The parser's own "pointer type root" is the C API name (cef_request_t).
        plan = self.plan("CefResourceHandler", "Open")
        self.assertTrue(plan.supported, plan.reason)
        self.assertIsInstance(plan.params[0].kind, LibRef)
        self.assertEqual(plan.params[0].kind.cls, "CefRequest")

    def test_output_parameters_are_returned(self):
        plan = self.plan("CefResourceHandler", "GetResponseHeaders")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([p.name for p in plan.outs], ["response_length", "redirect_url"])
        self.assertIsInstance(plan.ret, Void)
        self.assertEqual([name for name, _ in plan.results], ["response_length", "redirect_url"])

    def test_return_value_comes_before_the_output_parameters(self):
        plan = self.plan("CefResourceHandler", "Open")
        self.assertEqual([name for name, _ in plan.results], ["return", "handle_request"])

    def test_buffer_pair_becomes_one_parameter(self):
        plan = self.plan("CefResourceHandler", "Read")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual([p.name for p in plan.ins], ["data_out", "callback"])
        self.assertEqual(plan.params[0].size_name, "bytes_to_read")

    def test_enumerations_are_told_apart_from_structs(self):
        plan = self.plan("CefRequest", "GetResourceType")
        self.assertTrue(plan.supported, plan.reason)
        self.assertEqual(plan.ret, Enum("ResourceType", "cef_resource_type_t"))

    def test_unsupported_types_are_reported_with_a_reason(self):
        plan = self.plan("CefRequest", "GetHeaderMap")
        self.assertFalse(plan.supported)
        self.assertIn("multimap", plan.reason)
        plan = self.plan("CefRequest", "GetPostData")
        self.assertFalse(plan.supported)
        self.assertIn("CefPostData is not generated yet", plan.reason)

    def test_pure_virtual_methods_are_detected(self):
        cls = self.model.classes["CefResourceHandler"]
        pure = {m.get_name(): self.model.is_pure_virtual(cls, m) for m in cls.get_virtual_funcs()}
        self.assertTrue(pure["Cancel"])
        self.assertTrue(pure["GetResponseHeaders"])
        self.assertFalse(pure["Open"])
        factory = self.model.classes["CefSchemeHandlerFactory"]
        self.assertTrue(self.model.is_pure_virtual(factory, factory.get_virtual_funcs()[0]))

    def test_primitives_and_strings(self):
        plan = self.plan("CefRequest", "SetURL")
        self.assertIsInstance(plan.params[0].kind, Str)
        plan = self.plan("CefResponse", "SetStatus")
        self.assertEqual(plan.params[0].kind, Prim("int", "int"))

    def test_generated_files_are_up_to_date(self):
        import generate
        files = generate.build_all(CEF_ROOT)
        for key, text in files.items():
            path = generate.OUTPUTS[key]
            with open(path, encoding="utf-8", newline="") as f:
                self.assertEqual(f.read(), text,
                                 "%s is out of date: run python tools/gen/generate.py" % path)

    def test_generation_is_deterministic(self):
        import generate
        self.assertEqual(generate.build_all(CEF_ROOT), generate.build_all(CEF_ROOT))


if __name__ == "__main__":
    unittest.main()

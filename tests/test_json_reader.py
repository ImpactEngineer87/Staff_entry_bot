import json
import tempfile
import unittest
from pathlib import Path

from staffbot.readers import InputError, ParseOptions, load_file


class JsonReaderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def read(self, value, options=ParseOptions()):
        path = self.root / "staff.json"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return load_file(path, options)

    def raw(self, text):
        path = self.root / "staff.json"
        path.write_text(text, encoding="utf-8")
        return load_file(path)

    def test_objects_follow_first_record_order_even_when_later_keys_move(self):
        data = self.read([{"id": "001", "name": "Mary Jane", "email": None},
                          {"email": "jose@example.com", "name": "José García", "id": "002"}])
        data.validate()
        self.assertEqual(data.records[0].values, ("001", "Mary Jane", ""))
        self.assertEqual(data.records[1].values, ("002", "José García", "jose@example.com"))
        self.assertEqual(data.records[1].source, "JSON record 2")
        self.assertIn('1="id", 2="name", 3="email"', " ".join(data.warnings))

    def test_single_flat_object_is_one_record(self):
        data = self.read({"id": "001", "name": "Mary Jane"})
        data.validate()
        self.assertEqual([record.values for record in data.records], [("001", "Mary Jane")])

    def test_records_wrapper_keeps_metadata_out_of_the_form(self):
        data = self.read({"records": [{"id": "001", "name": "Mary Jane"}],
                          "metadata": {"exported": "today"}})
        data.validate()
        self.assertEqual(data.records[0].values, ("001", "Mary Jane"))
        self.assertIn("wrapper metadata is ignored", " ".join(data.warnings))

    def test_rows_keep_empty_fields_and_allow_header_skip_and_column_order(self):
        data = self.read([["ID", "Name", "Department"], ["001", "José García", None]],
                         ParseOptions(skip_header=True, columns=(2, 1, 3)))
        data.validate()
        self.assertEqual(data.records[0].values, ("José García", "001", ""))

    def test_numeric_precision_booleans_null_and_text_are_preserved(self):
        data = self.raw('[["001", 123456789012345678901234567890, '
                        '0.123456789012345678901234567890, 12.00, true, false, null]]')
        data.validate()
        self.assertEqual(data.records[0].values,
                         ("001", "123456789012345678901234567890",
                          "0.123456789012345678901234567890", "12.00", "TRUE", "FALSE", ""))

    def test_bom_unicode_explicit_encoding_and_uppercase_extension(self):
        text = json.dumps([["001", "José García"]], ensure_ascii=False)
        for encoding in ("utf-8-sig", "utf-16", "cp1252"):
            with self.subTest(encoding=encoding):
                path = self.root / "staff.JSON"
                path.write_bytes(text.encode(encoding))
                options = ParseOptions(encoding=encoding if encoding == "cp1252" else "auto")
                self.assertEqual(load_file(path, options).records[0].values, ("001", "José García"))

    def test_empty_records_block_entry(self):
        for value in ([], {}, [[]], {"records": []}):
            with self.subTest(value=value), self.assertRaises(InputError):
                self.read(value).validate()

    def test_duplicate_object_keys_are_reported(self):
        with self.assertRaisesRegex(InputError, "Duplicate JSON key 'id'"):
            self.raw('[{"id":"001","id":"002"}]')

    def test_missing_or_extra_keys_block_import_even_with_column_selection(self):
        for second in ({"id": "002"}, {"id": "002", "name": "John", "extra": "value"}):
            with self.subTest(second=second), self.assertRaisesRegex(InputError, "field names must match"):
                self.read([{"id": "001", "name": "Mary"}, second], ParseOptions(columns=(1,)))

    def test_nested_values_require_flat_fields(self):
        for value in ([{"id": "001", "name": {"first": "Mary"}}], [["001", ["Mary", "Jane"]]]):
            with self.subTest(value=value), self.assertRaisesRegex(InputError, "nested objects and arrays"):
                self.read(value)

    def test_mixed_or_scalar_records_are_rejected(self):
        for value in ([{"id": "001"}, ["002"]], [["001"], {"id": "002"}],
                      ["001", "Mary"], "staff", 123, None):
            with self.subTest(value=value), self.assertRaises(InputError):
                self.read(value)

    def test_malformed_json_reports_line_and_column(self):
        with self.assertRaisesRegex(InputError, r"Invalid JSON at line 2, column"):
            self.raw('[\n{"id":"001",}\n]')

    def test_nonfinite_numbers_are_rejected(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant), self.assertRaisesRegex(InputError, "finite number"):
                self.raw("[[" + constant + "]]")

    def test_text_separator_does_not_split_json_strings(self):
        data = self.read([["001", "Mary Jane | HR"]],
                         ParseOptions(separator="custom", custom_separator="invalid separator"))
        self.assertEqual(data.records[0].values, ("001", "Mary Jane | HR"))

    def test_controls_and_inconsistent_rows_block_entry(self):
        for value in ([["001", "Mary\nJane"]], [["001", "Mary\tJane"]],
                      [["001", "Mary\x00Jane"]], [["001", "Mary"], ["002"]]):
            with self.subTest(value=value), self.assertRaises(InputError):
                self.read(value).validate()

    def test_sample_json_matches_the_existing_text_sample(self):
        root = Path(__file__).resolve().parents[1] / "examples"
        data = load_file(root / "staff.json")
        data.validate()
        self.assertEqual([record.values for record in data.records],
                         [record.values for record in load_file(root / "staff_spaces.txt").records])


if __name__ == "__main__":
    unittest.main()

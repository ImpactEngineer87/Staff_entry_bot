"""Exercise the practice form's real widgets without showing a desktop window."""
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

import demo_form


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class PracticeGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display is unavailable: {error}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        with patch.object(demo_form, "enable_dpi_awareness"), \
                patch.object(demo_form.tk, "Tk", return_value=self.root), \
                patch.object(self.root, "mainloop"):
            demo_form.main()
        self.root.update_idletasks()
        widgets = list(descendants(self.root))
        self.entries = [widget for widget in widgets if isinstance(widget, ttk.Entry)]
        self.assertEqual(len(self.entries), 4)
        self.table = next(widget for widget in widgets if isinstance(widget, ttk.Treeview))
        self.save = next(widget for widget in widgets
                         if isinstance(widget, ttk.Button) and widget.cget("text") == "Save record")

    def test_save_preserves_exact_text_and_unicode_then_clears_fields(self):
        values = (" 000123 ", 'Renée "R&D" Иванова', "People\tOperations", "élise+HR@example.test")
        for entry, value in zip(self.entries, values):
            entry.insert(0, value)

        self.save.invoke()

        records = self.table.get_children()
        self.assertEqual(len(records), 1)
        self.assertEqual(tuple(self.table.item(records[0], "values")), values)
        self.assertEqual([entry.get() for entry in self.entries], ["", "", "", ""])

        self.entries[0].insert(0, "000124")
        self.save.invoke()
        self.assertEqual(len(self.table.get_children()), 2)
        self.assertEqual(tuple(self.table.item(records[0], "values")), values)

    def test_missing_employee_id_does_not_save_or_clear_other_fields(self):
        self.entries[1].insert(0, "Ada Lovelace")
        self.entries[2].insert(0, "Engineering")
        self.entries[3].insert(0, "ada@example.test")

        self.save.invoke()

        self.assertEqual(self.table.get_children(), ())
        self.assertEqual([entry.get() for entry in self.entries],
                         ["", "Ada Lovelace", "Engineering", "ada@example.test"])

    def test_tab_order_reaches_save_and_enter_has_a_save_binding(self):
        # Native Tk traversal excludes withdrawn windows. Map a transparent,
        # undecorated window offscreen only while querying the real Tab sequence.
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0.0)
        self.root.geometry("940x820-30000-30000")
        self.root.deiconify()
        self.root.update()
        self.addCleanup(self.root.withdraw)

        focus_order = self.entries + [self.save]
        for current, following in zip(focus_order, focus_order[1:]):
            self.assertEqual(str(current.tk_focusNext()), str(following))
        self.assertTrue(self.save.bind("<Return>"))


if __name__ == "__main__":
    unittest.main()

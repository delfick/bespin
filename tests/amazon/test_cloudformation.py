# coding: spec

from bespin.amazon.cloudformation import NONEXISTANT, UPDATE_COMPLETE

from tests.helpers import BespinCase

describe BespinCase, "Status classes":
    it "have name equal to the class name":
        self.assertEqual(NONEXISTANT.name, "NONEXISTANT")
        self.assertEqual(UPDATE_COMPLETE.name, "UPDATE_COMPLETE")

    it "have helpful properties":
        self.assertEqual(NONEXISTANT.exists, False)
        self.assertEqual(UPDATE_COMPLETE.exists, True)

        self.assertEqual(NONEXISTANT.failed, False)
        self.assertEqual(UPDATE_COMPLETE.failed, False)

        self.assertEqual(NONEXISTANT.complete, False)
        self.assertEqual(UPDATE_COMPLETE.complete, True)


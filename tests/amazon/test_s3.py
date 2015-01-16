# coding: spec

from bespin.amazon.s3 import S3

from tests.helpers import BespinCase

describe BespinCase, "determine_chunks":
    it "successfully finds the chunks":
        chunks = list(S3().determine_chunks(10, min_chunk=3))
        self.assertEqual(chunks, [(0, 0, 3), (1, 3, 3), (2, 6, 4)])

    it "works if there is only one chunk":
        chunks = list(S3().determine_chunks(10, min_chunk=6))
        self.assertEqual(chunks, [(0, 0, 10)])

        chunks = list(S3().determine_chunks(10, min_chunk=10))
        self.assertEqual(chunks, [(0, 0, 10)])


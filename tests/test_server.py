import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import server
from bson import ObjectId


class FakeCursor(list):
    def limit(self, size):
        return FakeCursor(self[:size])


class FakeCollection:
    def __init__(self):
        self.documents = []

    def count_documents(self, _query):
        return len(self.documents)

    def find(self):
        return FakeCursor(self.documents)

    def insert_one(self, document):
        document["_id"] = ObjectId()
        self.documents.append(document.copy())
        return type("InsertResult", (), {"inserted_id": document["_id"]})()

    def replace_one(self, query, replacement):
        for index, document in enumerate(self.documents):
            if document["_id"] == query["_id"]:
                self.documents[index] = replacement.copy()
                return type("UpdateResult", (), {"matched_count": 1})()
        return type("UpdateResult", (), {"matched_count": 0})()

    def delete_one(self, query):
        for index, document in enumerate(self.documents):
            if document["_id"] == query["_id"]:
                del self.documents[index]
                return type("DeleteResult", (), {"deleted_count": 1})()
        return type("DeleteResult", (), {"deleted_count": 0})()


class FakeDatabase:
    def __init__(self):
        self.collections = {name: FakeCollection() for name in server.COLLECTIONS}

    def __getitem__(self, name):
        return self.collections[name]


class FakeMongoClient:
    class Admin:
        @staticmethod
        def command(_command):
            return {"ok": 1}

    admin = Admin()


class LibraryApiTests(unittest.TestCase):
    def setUp(self):
        self.original_database = server.database
        self.original_client = server.mongo_client
        server.database = FakeDatabase()
        server.mongo_client = FakeMongoClient()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.LibraryHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.httpd.server_port}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()
        server.database = self.original_database
        server.mongo_client = self.original_client

    def request(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def test_document_crud_lifecycle(self):
        status, body = self.request(
            "POST",
            "/api/collections/books/documents",
            {"bookID": "book-1", "title": "Example"},
        )
        self.assertEqual(status, 201)
        document = json.loads(body)["document"]
        document_id = document["_id"]["$oid"]

        status, body = self.request("GET", "/api/collections/books/documents")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["documents"]), 1)

        status, body = self.request(
            "PUT",
            f"/api/collections/books/documents/{document_id}",
            {"bookID": "book-1", "title": "Updated"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["document"]["title"], "Updated")

        status, _ = self.request(
            "DELETE",
            f"/api/collections/books/documents/{document_id}",
        )
        self.assertEqual(status, 204)

        status, body = self.request("GET", "/api/collections")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["counts"]["books"], 0)

    def test_invalid_collection_and_document_are_rejected(self):
        status, _ = self.request("POST", "/api/collections/unknown/documents", {})
        self.assertEqual(status, 404)

        status, body = self.request(
            "POST",
            "/api/collections/books/documents",
            ["not", "an", "object"],
        )
        self.assertEqual(status, 400)
        self.assertIn("JSON object", json.loads(body)["error"])

        status, _ = self.request(
            "DELETE",
            "/api/collections/books/documents/not-an-object-id",
        )
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()

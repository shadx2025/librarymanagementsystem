import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from bson import ObjectId, json_util
from pymongo import MongoClient
from pymongo.errors import PyMongoError


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
DATABASE_NAME = os.getenv("MONGODB_DATABASE", "LibraryDB")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
COLLECTIONS = ("books", "borrowings", "librarian", "students")
MAX_BODY_SIZE = 1_000_000

mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
database = mongo_client[DATABASE_NAME]


class LibraryHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path == "/api/health":
            self.handle_health()
        elif path == "/api/collections":
            self.handle_collections()
        elif path.startswith("/api/collections/"):
            collection_name = path.removeprefix("/api/collections/").removesuffix("/documents")
            self.handle_documents(collection_name)
        else:
            super().do_GET()

    def do_POST(self):
        collection_name = self.collection_from_path()
        if collection_name is None:
            self.send_error(404, "Unknown collection")
            return
        try:
            document = self.read_document()
            result = database[collection_name].insert_one(document)
            document["_id"] = result.inserted_id
            self.send_json(201, {"document": document})
        except ValueError as error:
            self.send_json(400, {"error": str(error)})
        except PyMongoError as error:
            self.send_database_error(error)

    def do_PUT(self):
        collection_name, document_id = self.collection_and_id()
        if collection_name is None or document_id is None:
            self.send_error(404, "Unknown document")
            return
        try:
            document = self.read_document()
            document.pop("_id", None)
            result = database[collection_name].replace_one(
                {"_id": ObjectId(document_id)},
                {**document, "_id": ObjectId(document_id)},
            )
            if result.matched_count == 0:
                self.send_json(404, {"error": "Document not found"})
                return
            self.send_json(200, {"document": {**document, "_id": ObjectId(document_id)}})
        except ValueError as error:
            self.send_json(400, {"error": str(error)})
        except PyMongoError as error:
            self.send_database_error(error)

    def do_DELETE(self):
        collection_name, document_id = self.collection_and_id()
        if collection_name is None or document_id is None:
            self.send_error(404, "Unknown document")
            return
        try:
            result = database[collection_name].delete_one({"_id": ObjectId(document_id)})
            if result.deleted_count == 0:
                self.send_json(404, {"error": "Document not found"})
                return
            self.send_response(204)
            self.end_headers()
        except PyMongoError as error:
            self.send_database_error(error)

    def handle_health(self):
        try:
            mongo_client.admin.command("ping")
            self.send_json(200, {"ok": True, "database": DATABASE_NAME})
        except PyMongoError as error:
            self.send_database_error(error)

    def handle_collections(self):
        try:
            mongo_client.admin.command("ping")
            counts = {
                name: database[name].count_documents({})
                for name in COLLECTIONS
            }
            self.send_json(200, {"database": DATABASE_NAME, "counts": counts})
        except PyMongoError as error:
            self.send_database_error(error)

    def handle_documents(self, collection_name):
        request_path = urlsplit(self.path).path
        if collection_name not in COLLECTIONS or not request_path.endswith("/documents"):
            self.send_error(404, "Unknown collection")
            return
        try:
            documents = list(database[collection_name].find().limit(101))
            has_more = len(documents) > 100
            self.send_json(200, {"documents": documents[:100], "hasMore": has_more})
        except PyMongoError as error:
            self.send_database_error(error)

    def collection_from_path(self):
        path = unquote(urlsplit(self.path).path)
        prefix = "/api/collections/"
        if not path.startswith(prefix) or not path.endswith("/documents"):
            return None
        name = path[len(prefix):-len("/documents")]
        return name if name in COLLECTIONS else None

    def collection_and_id(self):
        path = unquote(urlsplit(self.path).path)
        parts = path.split("/")
        if len(parts) != 6 or parts[1:3] != ["api", "collections"] or parts[4] != "documents":
            return None, None
        name, document_id = parts[3], parts[5]
        if name not in COLLECTIONS or not ObjectId.is_valid(document_id):
            return None, None
        return name, document_id

    def read_document(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid request body size") from error
        if length < 1 or length > MAX_BODY_SIZE:
            raise ValueError("Request body must be between 1 byte and 1 MB")
        try:
            document = json_util.loads(self.rfile.read(length))
        except (ValueError, TypeError) as error:
            raise ValueError("Request body must contain valid JSON") from error
        if not isinstance(document, dict):
            raise ValueError("A document must be a JSON object")
        return document

    def send_json(self, status, payload):
        body = json_util.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_database_error(self, error):
        print(f"MongoDB request failed ({type(error).__name__})")
        self.send_json(
            503,
            {
                "error": (
                    "Cannot connect to MongoDB. Start the server and verify "
                    "the MONGODB_URI setting."
                )
            },
        )


if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), LibraryHandler)
    print(f"LibraryDB frontend: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping LibraryDB frontend.")
    finally:
        server.server_close()
        mongo_client.close()

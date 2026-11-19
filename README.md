# LibraryDB frontend

A small web interface for the existing MongoDB `LibraryDB` database. It works with the `books`, `borrowings`, `students`, and `librarian` collections and displays fields from the documents already stored in each collection.

## Run locally

1. Start MongoDB on `localhost:27017` and confirm the `LibraryDB` database is available in MongoDB Compass.
2. From this folder, install the Python dependency:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Start the app:

   ```powershell
   python server.py
   ```

4. Open <http://127.0.0.1:8000>.

Run the backend tests with `python -m unittest discover -s tests -v`.

The app reads and writes to the database directly. It supports creating, editing, searching, and deleting documents. Records are edited as JSON so the UI does not assume field names that are not defined by the database. The collection view displays the first 100 records.

To use a different MongoDB address or database, set `MONGODB_URI` or `MONGODB_DATABASE` before starting the server. The server is intentionally available only on this computer at `127.0.0.1`. Set `PORT` if port 8000 is already in use.

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import OperationFailure
from bson import ObjectId
from pydantic import BaseModel
from datetime import datetime
import json

from config import mongodb_url, database_name, collection_name

app = FastAPI()

# MongoDB connection
client = MongoClient(mongodb_url)
db = client[database_name]
user_collection: Collection = db['Users']
stream_collection: Collection = db['Stream']

class User(BaseModel):
    _id: str
    uuid: str

# CORS Configuration
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:5173",
    "https://mx-webapps.psi.ch",
    "https://heidi-test.psi.ch",
    "https://heidi.psi.ch"
    # Add more allowed origins as needed
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

async def authenticate_user(userAccount, uuid):
    """
    Check if the user of client has the necessary permissions
    to access the endpoing
    """
    user = user_collection.find_one({'_id': userAccount})
    print(user)

    if not user:
        raise HTTPException(status_code=403, detail="Access forbidden")

    if uuid != user['uuid']:
        raise HTTPException(status_code=401, detail="Invalid access credentials")

    print("user authenticated")

    return True

@app.get("/event-stream")
async def event_stream(
    userAccount: str = Query(...), uuid: str = Query(...)
    ):
    try:
        await authenticate_user(userAccount, uuid)
    except Exception as e:
        raise HTTPException(status_code=401, detail='Invalid credentials')

    # Generator function to stream SSEs
    def generate_events():
        try:
            # Watch changes in the collection for the specified userAccount
            pipeline = [
                {"$match": {"fullDocument.userAccount": userAccount}}
            ]
            with stream_collection.watch(pipeline=pipeline) as stream:
                print(f"Watching for changes in the {collection_name} collection for userAccount: {userAccount}")
                for change in stream:
                    full_document = change.get("fullDocument")
                    if full_document and "method" in full_document:
                        # Get the event type from the "method" key in fullDocument
                        event_type = full_document["method"]
                        # Serialize the fullDocument with custom JSON encoder
                        serialized_data = json.dumps(full_document, cls=CustomJSONEncoder)
                        # Yield the serialized fullDocument as an SSE with the event type
                        event_data = f"event: {event_type}\ndata: {serialized_data}\n\n"
                        yield event_data

        except OperationFailure as e:
            print("Error watching collection:", e)

        finally:
            # Close the MongoDB connection
            client.close()
            print("MongoDB connection closed")

    # Return SSEs as a streaming response
    return StreamingResponse(generate_events(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import OperationFailure
from bson import ObjectId
from pydantic import BaseModel, Field
from datetime import datetime
import json
import uuid 

# Implemented Pydantic Settings for the ENV variables
from config import Settings

app = FastAPI()


async def get_client() -> MongoClient:
    """
    Connect to MongoDB and return the client
    """
    client = MongoClient(Settings.mongodb_url)
    try:
        yield client
        print("Connected successfully to MongoDB server")   
    finally:
        client.close()
        print("MongoDB connection closed")

class User(BaseModel):
    _id: str = Field(..., title='User Account')
    uuid: uuid.uuid4 = Field(..., title='User UUID')

app.add_middleware(
    CORSMiddleware,
    allow_origins=Settings.origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (ObjectId, datetime)):
            return str(obj) if isinstance(obj, ObjectId) else obj.isoformat()
        return super().default(obj)

async def authenticate_user(user_account: User, client: MongoClient) -> bool:
    """
    Check if the user of client has the necessary permissions
    to access the endpoint
    """
    db = client[Settings.database_name]
    user_collection: Collection = db[Settings.user_collection_name]
    user = user_collection.find_one({'_id': user_account._id})

    if not user:
        raise HTTPException(status_code=403, detail="Access forbidden")

    if uuid != user_account.uuid:
        raise HTTPException(status_code=401, detail="Invalid access credentials")

    return True

@app.get("/event-stream")
async def event_stream(
    user_account: User,
    client = Depends(get_client)
    ):

    try:
        await authenticate_user(user_account=user_account)
    except Exception as e:
        raise HTTPException(status_code=401, detail='Invalid credentials')

    db = client[Settings.database_name]
    stream_collection: Collection = db[Settings.stream_collection_name]

    # Generator function to stream SSEs
    def generate_events():
        try:
            # Watch changes in the collection for the specified userAccount
            pipeline = [
                {"$match": {"fullDocument.userAccount": user_account._id}}
            ]
            with stream_collection.watch(pipeline=pipeline) as stream:
                print(f"Watching for changes in the {stream_collection} collection for userAccount: {userAccount}")
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


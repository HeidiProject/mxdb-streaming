from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import OperationFailure
from bson import ObjectId
from pydantic import BaseModel, Field
from datetime import datetime
import json

# Implemented Pydantic Settings for the ENV variables
from config import Settings
settings = Settings(_env_file='.env', _env_file_encoding='utf-8')

app = FastAPI()

# FastAPI dependency to connect to MongoDB
# https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
async def get_client() -> MongoClient:
    """
    Connect to MongoDB and return the client
    """
    client = MongoClient(settings.mongodb_url)
    try:
        yield client
        print("Connected successfully to MongoDB server")   
    finally:
        client.close()
        print("MongoDB connection closed")


class User(BaseModel):
    id: str = Field(..., title='User Account')
    uuid: str = Field(..., title='User UUID')

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:8000",
        "http://localhost:5173",
        "https://mx-webapps.psi.ch",
        "https://heidi-test.psi.ch",
        "https://heidi.psi.ch"
    ],
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

async def authenticate_user(user_account: User, client: MongoClient) -> bool:
    """
    Check if the user of client has the necessary permissions
    to access the endpoing
    """
    db = client[settings.database_name]
    user_collection: Collection = db[settings.user_collection_name]
    user = user_collection.find_one({'_id': user_account.id})

    if not user:
        raise HTTPException(status_code=403, detail="Access forbidden")

    if user['uuid'] != user_account.uuid:
        raise HTTPException(status_code=401, detail="Invalid access credentials")

    print(f"user authenticated: {user_account.id}")

    return True

@app.get("/event-stream")
async def event_stream(
    userAccount, uuid,
    client = Depends(get_client)
    ):

    user_account = User(id=userAccount, uuid=uuid)

    try:
        await authenticate_user(user_account=user_account, client=client)
    except Exception:
        raise HTTPException(status_code=401, detail='Invalid credentials')
    
    db = client[settings.database_name]
    stream_collection: Collection = db[settings.stream_collection_name]

    # Generator function to stream SSEs
    def generate_events():
        try:
            # Watch changes in the collection for the specified userAccount
            pipeline = [
                {"$match": {"fullDocument.userAccount": user_account.id}}
            ]
            with stream_collection.watch(pipeline=pipeline) as stream:
                print(f"Watching for changes in the {settings.stream_collection_name} collection for userAccount: {user_account.id}")
                for change in stream:
                    full_document = change.get("fullDocument")
                    if full_document and "method" in full_document:
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


@app.get("/vespa-stream")
async def vespa_stream(
    userAccount, uuid,
    client = Depends(get_client)
    ):

    user_account = User(id=userAccount, uuid=uuid)

    try:
        await authenticate_user(user_account=user_account, client=client)
    except Exception as e:
        raise HTTPException(status_code=401, detail='Invalid credentials')

    db = client[settings.database_name]
    vespa_collection: Collection = db[settings.vespa_collection_name]
    if userAccount[0] == "e":
        userAccount = userAccount[1:]
    pgroup = f"p{userAccount}"
    # Generator function to stream SSEs
    def generate_events():
        try:
            # Watch changes in the collection for the specified userAccount
            pipeline = [
                {"$match": {"fullDocument.user_data.pgroup": pgroup}},
                {"$project": {
                    "fullDocument._id": 1,
                    "fullDocument.user_data.crystfelMinPixCount": 1,
                    "fullDocument.user_data.crystfelMinSNR": 1,
                    "fullDocument.user_data.crystfelThreshold": 1,
                    "fullDocument.numberOfImages": 1,
                    "fullDocument.numberOfImagesIndexed": 1,
                    "fullDocument.user_data.mergeId": 1,
                    "fullDocument.filename": 1,
                    "fullDocument.createdOn": 1,
                }}
            ]
            with vespa_collection.watch(pipeline=pipeline) as stream:
                print(f"Watching for changes in the {settings.vespa_collection_name} collection for pgroup: {pgroup}")
                for change in stream:
                    full_document = change.get("fullDocument")
                    if full_document:
                        # Get the event type from the "method" key in fullDocument
                        event_type = "vespa"
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

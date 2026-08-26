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
import logging

from ffcs_queries import CAMPAIGN_SOURCE_COLLECTION, campaign_discovery_pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

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
        print("In a finally and not try anymore")


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
    
def serialize_documents(doc):
    """Convert ObjectId to string in a MongoDB document."""
    if isinstance(doc, list):
        return [serialize_documents(item) for item in doc]
    if isinstance(doc, dict):
        return {key: serialize_documents(value) for key, value in doc.items()}
    if isinstance(doc, ObjectId):
        return str(doc)
    return doc

async def authenticate_user(user_account: User, client: MongoClient) -> bool:
    """
    Check if the user of client has the necessary permissions
    to access the endpoint
    """
    print(user_account.id)
    print(user_account.uuid)
    if user_account.id[0] == "p":
        user_account.id = f"e{user_account[1:]}"
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
                {
                    "$match": {
                        "fullDocument.experiment_group": pgroup
                    }
                },
                {
                    "$project": {
                        "run_number": "$fullDocument.run_number",
                        "triggered_flag": "$fullDocument.user_data.triggered_flag",
                        "trigger_status": { "$ifNull": ["$fullDocument.trigger_status", "off"] },
                        "resolutionLimitMean": { "$ifNull": ["$fullDocument.resolutionLimitMean", None] },
                        "numberOfImages": { "$ifNull": ["$fullDocument.numberOfImages", 0] },
                        "numberOfImagesIndexed": { "$ifNull": ["$fullDocument.numberOfImagesIndexed", 0] },
                        "numberReflectionsMean": { "$ifNull": ["$fullDocument.numberReflectionsMean", None] },
                        "sample_name": "$fullDocument.sample_name",
                        "user_tag": "$fullDocument.user_tag"
                    }
                }
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

    # Return SSEs as a streaming response
    return StreamingResponse(generate_events(), media_type="text/event-stream")

@app.get("/experiment-data/")
def get_experiment_data(experiment_group: str = "", client = Depends(get_client)
):
    logger.debug(f"inside experiment-data endpoint for experiment_group: {experiment_group}")
    pipeline = [
        {
            '$match': {
                'experiment_group': experiment_group
            }
        }, {
            '$project': {
                'numberOfSpotsPerImage': 0, 
                'numberOfLatticesPerImage': 0, 
                'slurmJobId_off': 0, 
                'beam_y_pxl': 0,
            }
        }, {
            '$project': {
                'run_number': 1,
                'file_number': 1,
                'trigger_status': {
                    '$ifNull': ['$trigger_status', 'off']
                },
                'resolutionLimitMean': {
                    '$ifNull': ['$resolutionLimitMean', None]
                },
                'numberOfImages': {
                    '$ifNull': ['$numberOfImages', 0]
                },
                'numberOfImagesIndexed': {
                    '$ifNull': ['$numberOfImagesIndexed', 0]
                },
                'numberReflectionsMean': {
                    '$ifNull': ['$numberReflectionsMean', None]
                },
                'trigger_flag':{
                    '$ifNull': ['$user_data.trigger_flag', False]
                },
                'sample_name': 1,
                'user_tag': 1
            }
        }, {
        '$sort': {
            'run_number': -1, 
            'file_number': -1
        }
    }

    ]

    logger.debug("after pipeline")

    try:
        # Execute the aggregation pipeline
        db = client[settings.database_name]
        collection: Collection = db[settings.vespa_collection_name]
        results = collection.aggregate(pipeline)        
        serialized_results = [serialize_documents(doc) for doc in results]  # Serialize the result
        return serialized_results
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

#  Commented out at the moment for testing - runID aggregation logic below
# @app.get("/experiment-data/")
# def get_experiment_data(experiment_group: str = "", client = Depends(get_client)
# ):
#     logger.debug(f"inside experiment-data endpoint for experiment_group: {experiment_group}")
#     pipeline = [
#         {
#             '$match': {
#                 'experiment_group': experiment_group
#             }
#         },
#         {
#             '$project': {
#                 'run_number': 1,
#                 'trigger_status': {
#                     '$ifNull': ['$trigger_status', 'off']
#                 },
#                 'resolutionLimitMean': {
#                     '$ifNull': ['$resolutionLimitMean', None]
#                 },
#                 'numberOfImages': {
#                     '$ifNull': ['$numberOfImages', 0]
#                 },
#                 'numberOfImagesIndexed': {
#                     '$ifNull': ['$numberOfImagesIndexed', 0]
#                 },
#                 'numberReflectionsMean': {
#                     '$ifNull': ['$numberReflectionsMean', None]
#                 },
#                 'trigger_flag':{
#                     '$ifNull': ['$user_data.trigger_flag', False]
#                 },
#                 'sample_name': 1,
#                 'user_tag': 1
#             }
#         },
#         {
#             '$group': {
#                 '_id': {
#                     'run_number': '$run_number',
#                     'trigger_status': '$trigger_status',
#                     'user_tag': '$user_tag',
#                     'sample_name': '$sample_name',
#                     'trigger_flag': '$trigger_flag'
#                 },
#                 'acquisitions': {
#                     '$push': {
#                         'resolutionLimitMean': '$resolutionLimitMean',
#                         'numberOfImages': '$numberOfImages',
#                         'numberOfImagesIndexed': '$numberOfImagesIndexed',
#                         'numberReflectionsMean': '$numberReflectionsMean'
#                     }
#                 },
#                 'diffraction_resolution': {
#                     '$avg': '$resolutionLimitMean'
#                 },
#                 'total_images': {
#                     '$sum': '$numberOfImages'
#                 },
#                 'indexed_images': {
#                     '$sum': '$numberOfImagesIndexed'
#                 },
#                 'total_reflections': {
#                     '$avg': '$numberReflectionsMean'
#                 }
#             }
#         },
#         {
#             '$sort': {
#                 '_id.run_number': -1  # Sort by run_number in descending order
#             }
#         }
#     ]

#     logger.debug("after pipeline")

#     try:
#         # Execute the aggregation pipeline
#         db = client[settings.database_name]
#         collection: Collection = db[settings.vespa_collection_name]
#         results = collection.aggregate(pipeline)        
#         serialized_results = [serialize_documents(doc) for doc in results]  # Serialize the result
#         return serialized_results
#         return results
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

@app.get("/experiment-data-summary/")
def get_experiment_data(experiment_group: str = "", client = Depends(get_client)
):
    logger.debug(f"inside experiment-data endpoint for experiment_group: {experiment_group}")
    pipeline = [
        {
            '$match': {
                'experiment_group': experiment_group
            }
        }, {
            '$project': {
                'user_data': '$user_data', 
                'trigger_status': {
                    '$ifNull': [
                        '$trigger_status', 'off'
                    ]
                }, 
                'resolutionLimitMean': {
                    '$ifNull': [
                        '$resolutionLimitMean', None
                    ]
                }, 
                'numberOfImages': {
                    '$ifNull': [
                        '$numberOfImages', 0
                    ]
                }, 
                'numberOfImagesIndexed': {
                    '$ifNull': [
                        '$numberOfImagesIndexed', 0
                    ]
                }, 
                'numberReflectionsMean': {
                    '$ifNull': [
                        '$numberReflectionsMean', None
                    ]
                }, 
                'sample_name': 1, 
                'user_tag': {
                    '$ifNull': [
                        '$user_tag', None
                    ]
                }, 
            }
        }, {
            '$group': {
                '_id': {
                    'user_tag': '$user_tag', 
                    'trigger_flag': '$user_data.trigger_flag', 
                    'trigger_status': '$trigger_status', 
                    'sample_name': '$sample_name'
                }, 
                'acquisitions': {
                    '$push': {
                        'resolutionLimitMean': '$resolutionLimitMean', 
                        'numberOfImages': '$numberOfImages', 
                        'numberOfImagesIndexed': '$numberOfImagesIndexed', 
                        'numberReflectionsMean': '$numberReflectionsMean'
                    }
                }, 
                'diffraction_resolution': {
                    '$avg': '$resolutionLimitMean'
                }, 
                'total_images': {
                    '$sum': '$numberOfImages'
                }, 
                'indexed_images': {
                    '$sum': '$numberOfImagesIndexed'
                }, 
                'total_reflections': {
                    '$avg': '$numberReflectionsMean'
                }
            }
        }
    ]

    logger.debug("after pipeline")

    try:
        # Execute the aggregation pipeline
        db = client[settings.database_name]
        collection: Collection = db[settings.vespa_collection_name]
        results = collection.aggregate(pipeline).to_list(length=None)
        serialized_results = [serialize_documents(doc) for doc in results]  # Serialize the result
        return serialized_results
    except Exception as e:
        logger.error(f"Error details: {repr(e)}")
        raise HTTPException(status_code=500, detail=f"Server Error: {repr(e)}")
    
@app.get("/ffcs-summary/")
def get_ffcs_experiment_data(user_account: str = "", client = Depends(get_client)
):
    logger.debug(f"inside experiment-data endpoint for experiment_group: {user_account}")
    pipeline = campaign_discovery_pipeline(user_account)

    logger.info("after pipeline")

    try:
        # Execute the aggregation pipeline
        db = client['ffcs']
        collection: Collection = db[CAMPAIGN_SOURCE_COLLECTION]
        results = collection.aggregate(pipeline).to_list(length=None)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/ffcs-campaign-summary/")
def get_ffcs_campaign_data(user_account: str = "", campaign_id: str = "", client = Depends(get_client)
):
    logger.debug(f"inside experiment-data endpoint for experiment_group: {user_account}")
    pipeline = [
        {
            '$match': {
                'userAccount': user_account, 
                'campaignId': campaign_id
            }
        }, {
            '$addFields': {
                '_id': {
                    '$toString': '$_id'
                }, 
                'libraryId': {
                    '$toString': '$libraryId'
                }
            }
        }, {
            '$group': {
                '_id': {
                    'campaignId': '$campaignId',
                    'plateId': '$plateId',
                    'well': '$well',
                }, 
                'document': {
                    '$push': '$$ROOT'
                }
            }
        }, {
        '$sort': {
            '_id.plateId': -1, 
            '_id.well': 1,
            }
        }
    ]

    logger.info("after pipeline")

    try:
        # Execute the aggregation pipeline
        db = client['ffcs']
        collection: Collection = db['Wells']
        results = collection.aggregate(pipeline).to_list(length=None)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

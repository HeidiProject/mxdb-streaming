# mxdb-streaming

mxdb-streaming is a FASTAPI microservice that utilizes mongoDB changestreams to live stream information from our mxdb with SSEs. The Heidi webpage will connect to this service from the frontend to update our data processing tracker. Further endpoints can be added to in future to stream additional information - e.g. in live experiment tracking - start of dataset collection can also be displayed. 

## To deploy in production:

Build the docker image:
```
VERSION={version} docker-compose build
```

Run the docker image to start the service:
```
VERSION={version} docker compose up -d
```

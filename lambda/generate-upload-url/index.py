import json
import os
import uuid
import boto3
import logging

# Initialize S3 client and logger
s3_client = boto3.client('s3')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get bucket name from environment variable
ATTACHMENTS_S3_BUCKET_NAME = os.environ.get('ATTACHMENTS_S3_BUCKET_NAME')

def handler(event, context):
    if not ATTACHMENTS_S3_BUCKET_NAME:
        logger.error("Error: S3 bucket name not set in environment variables.")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Configuration error: S3 bucket name not set."}),
            "headers": {"Content-Type": "application/json"}
        }

    logger.info(f"Received event: {json.dumps(event)}")

    try:
        query_params = event.get('queryStringParameters', {})
        file_name = query_params.get('fileName')
        content_type = query_params.get('contentType', 'application/octet-stream') # Default content type

        if not file_name:
            logger.error("Error: 'fileName' is a required query string parameter.")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "'fileName' is a required query string parameter."}),
                "headers": {"Content-Type": "application/json"}
            }

        # Extract userId from Cognito authorizer claims
        user_id = None
        try:
            user_id = event['requestContext']['authorizer']['claims']['sub']
        except (KeyError, TypeError):
            logger.warning("Cognito user ID ('sub') not found in event claims.")
            try:
                user_id = event['requestContext']['authorizer']['principalId']
                logger.info(f"Using principalId as userId: {user_id}")
            except(KeyError, TypeError):
                logger.warning("principalId not found. Defaulting userId to 'anonymous'.")
                user_id = 'anonymous'

        # Generate a unique object key
        # Using a path structure: private/{userId}/{uuid}-{fileName}
        # This helps in organizing files per user and avoids name collisions.
        unique_id = str(uuid.uuid4())
        object_key = f"private/{user_id}/{unique_id}-{file_name}"

        # Parameters for the presigned URL
        presigned_url_params = {
            'Bucket': ATTACHMENTS_S3_BUCKET_NAME,
            'Key': object_key,
            'ExpiresIn': 3600,  # URL expiration time in seconds (e.g., 1 hour)
            'ContentType': content_type # Important to set ContentType for the actual upload
        }

        # For PUT operations, ContentType must be specified in generate_presigned_url
        # or the client must send it with the PUT request and it must match.
        # If conditions are used, they must be met by the client's upload.
        # Example of Conditions (more advanced, for specific client requirements):
        # conditions = [
        #     {"Content-Type": content_type},
        #     ["content-length-range", 0, 10485760] # Max 10MB
        # ]
        # presigned_url_params['Conditions'] = conditions

        logger.info(f"Generating presigned URL with params: {json.dumps(presigned_url_params)}")

        upload_url = s3_client.generate_presigned_url(
            'put_object',
            Params=presigned_url_params
        )

        logger.info(f"Successfully generated presigned URL for key: {object_key}")

        response_body = {
            "uploadUrl": upload_url,
            "objectKey": object_key,
            "bucket": ATTACHMENTS_S3_BUCKET_NAME,
            "expiresIn": presigned_url_params['ExpiresIn']
        }

        return {
            "statusCode": 200,
            "body": json.dumps(response_body),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*" # Adjust for production
            }
        }

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error.", "details": str(e)}),
            "headers": {"Content-Type": "application/json"}
        }

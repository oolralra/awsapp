import json
import os
import uuid
from datetime import datetime
import boto3

# Initialize DynamoDB client outside the handler for better performance
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TODO_TABLE_NAME')
table = dynamodb.Table(table_name) if table_name else None

def handler(event, context):
    if not table:
        print("Error: DynamoDB table name not set in environment variables.")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Configuration error: DynamoDB table name not set."}),
            "headers": {"Content-Type": "application/json"}
        }

    print(f"Received event: {json.dumps(event)}")

    try:
        # Parse request body
        try:
            body = json.loads(event.get('body', '{}'))
        except json.JSONDecodeError:
            print("Error: Invalid JSON in request body.")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid JSON in request body."}),
                "headers": {"Content-Type": "application/json"}
            }

        task_description = body.get('task')
        if not task_description:
            print("Error: 'task' is a required field.")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "'task' is a required field."}),
                "headers": {"Content-Type": "application/json"}
            }

        # Extract userId from Cognito authorizer claims
        try:
            # When using Lambda proxy integration with Cognito User Pool authorizer
            user_id = event['requestContext']['authorizer']['claims']['sub']
        except (KeyError, TypeError):
            # Fallback if claims are not available (e.g. testing without authorizer)
            print("Warning: Cognito user ID not found in event. Defaulting to 'anonymous'.")
            user_id = 'anonymous'
            # For local testing, you might want to get it from a test event
            if 'requestContext' in event and 'authorizer' in event['requestContext'] and 'principalId' in event['requestContext']['authorizer']:
                 user_id = event['requestContext']['authorizer']['principalId']


        # Generate unique ID and timestamp
        todo_id = str(uuid.uuid4())
        created_at_timestamp = datetime.utcnow().isoformat()

        # Construct the item
        todo_item = {
            'id': todo_id,
            'userId': user_id,
            'task': task_description,
            'status': 'pending',  # Default status
            'createdAt': created_at_timestamp
        }

        # Add optional attachment fields if present in the request body
        attachment_key = body.get('attachmentKey')
        if attachment_key and isinstance(attachment_key, str) and attachment_key.strip():
            todo_item['attachmentKey'] = attachment_key.strip()

        attachment_filename = body.get('attachmentFilename')
        if attachment_filename and isinstance(attachment_filename, str) and attachment_filename.strip():
            todo_item['attachmentFilename'] = attachment_filename.strip()

        # Save item to DynamoDB
        table.put_item(Item=todo_item)
        print(f"Successfully saved item to DynamoDB: {json.dumps(todo_item)}")

        response = {
            "statusCode": 201, # Created
            "body": json.dumps(todo_item),
            "headers": {
                "Content-Type": "application/json"
            }
        }

    except Exception as e:
        print(f"Error processing request: {str(e)}")
        response = {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error.", "details": str(e)}),
            "headers": {
                "Content-Type": "application/json"
            }
        }

    return response

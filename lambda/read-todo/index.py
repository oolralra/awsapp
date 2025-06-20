import json
import os
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
        # Extract todo_id from path parameters
        try:
            todo_id = event['pathParameters']['id']
        except (KeyError, TypeError):
            print("Error: 'id' not found in pathParameters.")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Bad Request: Missing 'id' in path parameters."}),
                "headers": {"Content-Type": "application/json"}
            }

        # Extract authenticated_userId from Cognito authorizer claims
        authenticated_user_id = None
        try:
            authenticated_user_id = event['requestContext']['authorizer']['claims']['sub']
        except (KeyError, TypeError):
            print("Warning: Cognito user ID ('sub') not found in event claims.")
            try:
                authenticated_user_id = event['requestContext']['authorizer']['principalId']
                print(f"Using principalId as authenticated_userId: {authenticated_user_id}")
            except(KeyError, TypeError):
                print("Warning: principalId not found. Defaulting authenticated_userId to 'anonymous'.")
                authenticated_user_id = 'anonymous'


        # Fetch item from DynamoDB
        response = table.get_item(Key={'id': todo_id})
        item = response.get('Item')

        if not item:
            print(f"Item with id '{todo_id}' not found.")
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Not Found: To-do item not found."}),
                "headers": {"Content-Type": "application/json"}
            }

        # Authorization check: Ensure the item belongs to the authenticated user
        item_user_id = item.get('userId')

        # Allow access if the user is 'anonymous' (e.g. for public tasks, adjust as needed)
        # OR if the item's userId matches the authenticated user's ID.
        if authenticated_user_id != 'anonymous' and item_user_id != authenticated_user_id:
            print(f"Forbidden: User '{authenticated_user_id}' tried to access item '{todo_id}' owned by '{item_user_id}'.")
            # Return 404 instead of 403 to not reveal the existence of the item to unauthorized users
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Not Found: To-do item not found or access denied."}),
                "headers": {"Content-Type": "application/json"}
            }

        print(f"Successfully retrieved item: {json.dumps(item)}")
        return {
            "statusCode": 200,
            "body": json.dumps(item),
            "headers": {"Content-Type": "application/json"}
        }

    except Exception as e:
        print(f"Error processing request: {str(e)}")
        # from botocore.exceptions import ClientError
        # if isinstance(e, ClientError) and e.response['Error']['Code'] == 'ResourceNotFoundException':
        #     return {"statusCode": 404, ...}
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error.", "details": str(e)}),
            "headers": {"Content-Type": "application/json"}
        }

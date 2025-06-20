import json
import os
import boto3

# Initialize DynamoDB client outside the handler
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
            except(KeyError, TypeError):
                print("Warning: principalId not found. Defaulting authenticated_userId to 'anonymous'.")
                authenticated_user_id = 'anonymous'

        # Ownership Check: Fetch the existing item to verify ownership before deleting
        get_response = table.get_item(Key={'id': todo_id})
        existing_item = get_response.get('Item')

        if not existing_item:
            print(f"Item with id '{todo_id}' not found for deletion.")
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Not Found: To-do item not found."}),
                "headers": {"Content-Type": "application/json"}
            }

        item_user_id = existing_item.get('userId')
        if authenticated_user_id != 'anonymous' and item_user_id != authenticated_user_id:
            print(f"Forbidden: User '{authenticated_user_id}' tried to delete item '{todo_id}' owned by '{item_user_id}'.")
            return {
                "statusCode": 404, # Or 403, but 404 hides existence
                "body": json.dumps({"error": "Not Found: To-do item not found or access denied."}),
                "headers": {"Content-Type": "application/json"}
            }

        # If ownership is verified, proceed with deletion
        table.delete_item(Key={'id': todo_id})

        print(f"Successfully deleted item with id '{todo_id}'.")

        # Return 204 No Content for successful deletion as per common REST practices
        return {
            "statusCode": 204,
            "body": "" # No body content for 204
        }
        # Alternatively, return 200 with a success message:
        # return {
        #     "statusCode": 200,
        #     "body": json.dumps({"message": f"To-do item with id '{todo_id}' deleted successfully."}),
        #     "headers": {"Content-Type": "application/json"}
        # }

    except Exception as e:
        print(f"Error processing request: {str(e)}")
        # Consider specific DynamoDB error handling if needed
        # from botocore.exceptions import ClientError
        # if isinstance(e, ClientError) and e.response['Error']['Code'] == 'ConditionalCheckFailedException':
        # This might happen if you add a condition to delete_item that isn't met.
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error.", "details": str(e)}),
            "headers": {"Content-Type": "application/json"}
        }

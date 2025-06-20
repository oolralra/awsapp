import json
import os
import boto3
from datetime import datetime

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

        # Parse request body
        try:
            body = json.loads(event.get('body', '{}'))
            if not body: # Ensure body is not empty
                raise json.JSONDecodeError("Request body is empty or not valid JSON.", "", 0)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid or empty JSON in request body: {e}")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Invalid or empty JSON in request body: {e.msg}"}),
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

        # Ownership Check: Fetch the existing item
        get_response = table.get_item(Key={'id': todo_id})
        existing_item = get_response.get('Item')

        if not existing_item:
            print(f"Item with id '{todo_id}' not found for update.")
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Not Found: To-do item not found."}),
                "headers": {"Content-Type": "application/json"}
            }

        item_user_id = existing_item.get('userId')
        if authenticated_user_id != 'anonymous' and item_user_id != authenticated_user_id:
            print(f"Forbidden: User '{authenticated_user_id}' tried to update item '{todo_id}' owned by '{item_user_id}'.")
            return {
                "statusCode": 404, # Or 403, but 404 hides existence
                "body": json.dumps({"error": "Not Found: To-do item not found or access denied."}),
                "headers": {"Content-Type": "application/json"}
            }

        # If ownership is verified, proceed with update
        update_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {} # For attributes that are also reserved keywords

        if 'task' in body:
            update_expression_parts.append("#task_val = :task")
            expression_attribute_values[':task'] = body['task']
            expression_attribute_names['#task_val'] = 'task' # 'task' is not a reserved word, but good practice

        if 'status' in body:
            update_expression_parts.append("#status_val = :status")
            expression_attribute_values[':status'] = body['status']
            expression_attribute_names['#status_val'] = 'status' # 'status' is a reserved word

        if not update_expression_parts:
            print("No updatable fields provided in the request body.")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Bad Request: No fields to update or invalid fields provided."}),
                "headers": {"Content-Type": "application/json"}
            }

        # Add updatedAt timestamp
        updated_at_timestamp = datetime.utcnow().isoformat()
        update_expression_parts.append("#updatedAt = :updatedAt")
        expression_attribute_values[':updatedAt'] = updated_at_timestamp
        expression_attribute_names['#updatedAt'] = 'updatedAt'

        update_expression = "SET " + ", ".join(update_expression_parts)

        # Perform the update
        update_response = table.update_item(
            Key={'id': todo_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names,
            ReturnValues='ALL_NEW'  # Returns all attributes of the item as they appear after the update
        )

        updated_item = update_response.get('Attributes')
        print(f"Successfully updated item: {json.dumps(updated_item)}")

        return {
            "statusCode": 200,
            "body": json.dumps(updated_item),
            "headers": {"Content-Type": "application/json"}
        }

    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error.", "details": str(e)}),
            "headers": {"Content-Type": "application/json"}
        }

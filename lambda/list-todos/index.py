import json
import os
import boto3
from boto3.dynamodb.conditions import Key

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
        # Extract userId from Cognito authorizer claims
        user_id = None
        try:
            # When using Lambda proxy integration with Cognito User Pool authorizer
            user_id = event['requestContext']['authorizer']['claims']['sub']
        except (KeyError, TypeError):
            # Fallback if claims are not available
            print("Warning: Cognito user ID ('sub') not found in event claims.")
            try:
                user_id = event['requestContext']['authorizer']['principalId']
                print(f"Using principalId as userId: {user_id}")
            except(KeyError, TypeError):
                print("Warning: principalId not found. Defaulting userId to 'anonymous'.")
                user_id = 'anonymous' # Or handle as an error if user must be authenticated

        items = []
        # If a specific user ID is available, query using the GSI
        if user_id and user_id != 'anonymous':
            print(f"Querying items for userId: {user_id}")
            response = table.query(
                IndexName='UserIdIndex',  # Name of the GSI on userId
                KeyConditionExpression=Key('userId').eq(user_id)
            )
            items = response.get('Items', [])
        else:
            # Fallback to scan if no specific user or for 'anonymous'
            # Note: Scan is inefficient for large tables. Consider if this case is needed.
            # If 'anonymous' should not see any todos, return an empty list or an error.
            print("Warning: Performing a table scan. This can be inefficient on large tables.")
            response = table.scan()
            items = response.get('Items', [])
            # Potentially filter further or paginate if necessary for scan operations

        print(f"Successfully retrieved {len(items)} items from DynamoDB.")

        return {
            "statusCode": 200,
            "body": json.dumps(items),
            "headers": {
                "Content-Type": "application/json"
            }
        }

    except Exception as e:
        print(f"Error processing request: {str(e)}")
        # Consider more specific error handling for DynamoDB exceptions if needed
        # from botocore.exceptions import ClientError
        # if isinstance(e, ClientError):
        # pass
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error.", "details": str(e)}),
            "headers": {
                "Content-Type": "application/json"
            }
        }

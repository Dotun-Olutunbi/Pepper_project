# src/emoex_client.py
import requests
from sseclient import SSEClient
import json

EMOEX_CHAT_API_URL = "https://api.emoexai.com/chat/assist"

def stream_chat_response(id_token, product_id, user_message):
    """
    Sends a message to the EmoEx chat API and streams the response.

    Args:
        id_token (str): The Firebase idToken for authentication.
        product_id (str): The EmoEx product ID.
        user_message (str): The message to send to the AI.

    Yields:
        str: Chunks of the AI's response message.
             Or an error message string if an API error event occurs.
    """
    if not id_token:
        yield "[Error: Missing ID Token for chat API]"
        return
    if not product_id:
        yield "[Error: Missing Product ID for chat API]"
        return

    headers = {
        "EMOEX-TOKEN": id_token,
        "Accept": "text/event-stream" # Important for SSE
    }
    data_payload = {
        "productId": product_id,
        "message": user_message
    }

    try:
        # Make the POST request with stream=True
        response = requests.post(
            EMOEX_CHAT_API_URL,
            headers=headers,
            data=data_payload,
            stream=True,
            timeout=180 # Set a timeout for the request (e.g., 3 minutes)
        )
        
        # print(f"\n[Debug] Response Status Code: {response.status_code}")
        # print(f"[Debug] Response Headers: {response.headers}")
        
        response.raise_for_status()  # Check for HTTP errors like 401, 403, 500

        # Explicitly check Content-Type header from the server
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/event-stream' not in content_type:
            yield f"[Error: Expected Content-Type 'text/event-stream' from server, but got '{response.headers.get('Content-Type')}']"
            # print(f"[Debug] Incorrect Content-Type: {response.headers.get('Content-Type')}")
            return

        # Use SSEClient to parse the event stream
        client = SSEClient(response)
        
        # print(f"[Debug] SSEClient object type: {type(client)}")
        # print(client)
        # if not hasattr(client, '__iter__'):
        #     # This is a critical check. If __iter__ is missing, the object cannot be used in a for loop.
        #     yield "[Error: SSEClient object is not iterable immediately after creation. SSEClient initialization might have failed or the response stream was invalid.]"
        #     print("[Debug] SSEClient object does NOT have __iter__ attribute. This is the cause of the 'not iterable' error.")
        #     return
        
        # print("[Debug] SSEClient appears iterable. Starting event loop.")
        
        full_response_printed = False
        for event in client.events():
            # According to EmoEx docs, relayed events from OpenAI-like API:
            # "thread.message.created", "thread.message.in_progress",
            # "thread.message.delta", "thread.message.completed",
            # "thread.message.incomplete", "error"

            if event.event == 'thread.message.delta':
                try:
                    event_json_data = json.loads(event.data)
                    if 'delta' in event_json_data and 'content' in event_json_data['delta']:
                        content_list = event_json_data['delta']['content']
                        for content_item in content_list:
                            if content_item.get('type') == 'text' and 'text' in content_item:
                                value = content_item['text'].get('value')
                                if value:
                                    yield value
                                    full_response_printed = True
                except json.JSONDecodeError:
                    print(f"\n[Debug: Non-JSON delta data: {event.data}]")
                except KeyError:
                    print(f"\n[Debug: Unexpected delta structure: {event.data}]")

            elif event.event == 'thread.message.completed':
                if not full_response_printed:
                     yield "" 
                break 

            elif event.event == 'error':
                error_message = f"[API Error: {event.data}]"
                yield error_message
                print(f"\n{error_message}") 
                break 

    except requests.exceptions.HTTPError as http_err:
        error_msg = f"[HTTP Error connecting to chat API: {http_err}]"
        try:
            # Try to get more details from the error response body if it's JSON
            error_details = http_err.response.json()
            error_msg += f" Details: {error_details.get('error', {}).get('message', http_err.response.text)}"
        except ValueError: # If response is not JSON
            error_msg += f" Raw response: {http_err.response.text}"
        yield error_msg
    except requests.exceptions.RequestException as req_err:
        yield f"[Request Error connecting to chat API: {req_err}]"
    except Exception as e: # This is where the 'TypeError: 'SSEClient' object is not iterable' was caught
        yield f"[Unexpected error during chat: {e}]" # The original error message you saw
        # print(f"[Debug] Exception caught in stream_chat_response: {type(e).__name__} - {e}")


if __name__ == '__main__':
    # For testing purposes - requires a valid idToken and product_id
    print("EmoEx Client Test Mode")
    print("This test requires a valid idToken and product_id.")
    
    mock_id_token = input("Enter a valid idToken for testing: ")
    mock_product_id = input("Enter your EmoEx Product ID for testing: ")

    if not mock_id_token or not mock_product_id:
        print("idToken and Product ID are required for this test.")
    else:
        test_message = "Hello AI, tell me a joke."
        print(f"\nSending message: '{test_message}'")
        print("AI Response Stream:")
        for chunk in stream_chat_response(mock_id_token, mock_product_id, test_message):
            print(chunk, end='', flush=True)
        print("\n--- Stream Test Complete ---")

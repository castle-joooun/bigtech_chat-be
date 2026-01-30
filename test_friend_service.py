"""
Friend Service API Test Script
"""

import requests
import json

# Base URLs
USER_SERVICE_URL = "http://localhost:8005"
FRIEND_SERVICE_URL = "http://localhost:8003"

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_friend_service():
    """Test Friend Service APIs"""

    print_section("Friend Service API Tests")

    # Step 0: Register a new user (if needed)
    print("0. Registering test user (if not exists)...")
    register_data = {
        "email": "friend_test@example.com",
        "username": "friend_testuser",
        "password": "TestPass123@",
        "display_name": "Friend Test User"
    }

    try:
        response = requests.post(
            f"{USER_SERVICE_URL}/auth/register",
            json=register_data
        )
        if response.status_code == 201:
            print(f"✅ User registered successfully")
        elif response.status_code == 400:
            print(f"ℹ️  User already exists, continuing...")
        else:
            response.raise_for_status()
    except Exception as e:
        print(f"ℹ️  User registration: {e}")

    # Step 1: Login to get access token
    print("\n1. Logging in to User Service...")
    login_data = {
        "email": "friend_test@example.com",
        "password": "TestPass123@"
    }

    try:
        response = requests.post(
            f"{USER_SERVICE_URL}/auth/login/json",
            json=login_data
        )
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data["access_token"]
        print(f"✅ Login successful")
        print(f"   Token: {access_token[:50]}...")
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return

    headers = {"Authorization": f"Bearer {access_token}"}

    # Step 2: Get friends list (should be empty initially)
    print("\n2. Getting friends list...")
    try:
        response = requests.get(f"{FRIEND_SERVICE_URL}/friends/list", headers=headers)
        response.raise_for_status()
        friends = response.json()
        print(f"✅ Friends list: {json.dumps(friends, indent=2)}")
    except Exception as e:
        print(f"❌ Get friends list failed: {e}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response.text}")

    # Step 3: Get friend requests (should be empty initially)
    print("\n3. Getting friend requests...")
    try:
        response = requests.get(f"{FRIEND_SERVICE_URL}/friends/requests", headers=headers)
        response.raise_for_status()
        requests_data = response.json()
        print(f"✅ Friend requests: {json.dumps(requests_data, indent=2)}")
    except Exception as e:
        print(f"❌ Get friend requests failed: {e}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response.text}")

    # Step 4: Send a friend request (to user_id=1)
    print("\n4. Sending friend request to user_id=1...")
    try:
        friend_request = {"user_id_2": 1}
        response = requests.post(
            f"{FRIEND_SERVICE_URL}/friends/request",
            json=friend_request,
            headers=headers
        )
        response.raise_for_status()
        friendship = response.json()
        print(f"✅ Friend request sent: {json.dumps(friendship, indent=2, default=str)}")
        friendship_id = friendship["id"]
    except Exception as e:
        print(f"❌ Send friend request failed: {e}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response.text}")
        friendship_id = None

    # Step 5: Get friend requests again (should show sent request)
    print("\n5. Getting friend requests (after sending)...")
    try:
        response = requests.get(f"{FRIEND_SERVICE_URL}/friends/requests", headers=headers)
        response.raise_for_status()
        requests_data = response.json()
        print(f"✅ Friend requests: {json.dumps(requests_data, indent=2, default=str)}")
    except Exception as e:
        print(f"❌ Get friend requests failed: {e}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response.text}")

    # Step 6: Search users
    print("\n6. Searching users with query 'test'...")
    try:
        response = requests.get(
            f"{FRIEND_SERVICE_URL}/friends/search",
            params={"query": "test", "limit": 5},
            headers=headers
        )
        response.raise_for_status()
        search_results = response.json()
        print(f"✅ Search results: {json.dumps(search_results, indent=2, default=str)}")
    except Exception as e:
        print(f"❌ Search users failed: {e}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response.text}")

    # Step 7: Cancel friend request
    if friendship_id:
        print(f"\n7. Cancelling friend request to user_id=1...")
        try:
            response = requests.delete(
                f"{FRIEND_SERVICE_URL}/friends/request/1",
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            print(f"✅ Friend request cancelled: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"❌ Cancel friend request failed: {e}")
            if hasattr(e, 'response'):
                print(f"   Response: {e.response.text}")

    print_section("Friend Service Tests Complete")

if __name__ == "__main__":
    test_friend_service()

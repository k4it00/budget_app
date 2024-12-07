import os
import sys

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from application import app

def test_health_check():
    with app.test_client() as client:
        response = client.get('/health')
        print(f"Status: {response.status_code}")
        print(f"Data: {response.data}")
        assert response.status_code == 200

if __name__ == "__main__":
    test_health_check()

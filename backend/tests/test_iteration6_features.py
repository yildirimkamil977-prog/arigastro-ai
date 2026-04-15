"""
Test iteration 6 features:
- ScraperAPI credit tracking endpoint
- User management CRUD operations
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestScraperAPICredits:
    """ScraperAPI account/credits endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "arigastro",
            "password": "Arigastro2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_scraperapi_account_returns_configured_true(self):
        """GET /api/scraperapi/account returns configured:true"""
        response = requests.get(f"{BASE_URL}/api/scraperapi/account", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("configured") == True, "ScraperAPI should be configured"
    
    def test_scraperapi_account_returns_request_count(self):
        """GET /api/scraperapi/account returns request_count"""
        response = requests.get(f"{BASE_URL}/api/scraperapi/account", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "request_count" in data, "Should have request_count field"
        assert isinstance(data["request_count"], int), "request_count should be integer"
    
    def test_scraperapi_account_returns_request_limit(self):
        """GET /api/scraperapi/account returns request_limit"""
        response = requests.get(f"{BASE_URL}/api/scraperapi/account", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "request_limit" in data, "Should have request_limit field"
        assert isinstance(data["request_limit"], int), "request_limit should be integer"
        assert data["request_limit"] > 0, "request_limit should be positive"


class TestUserManagement:
    """User management CRUD endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "arigastro",
            "password": "Arigastro2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_users_returns_list(self):
        """GET /api/users returns user list"""
        response = requests.get(f"{BASE_URL}/api/users", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Should return a list"
        assert len(data) >= 1, "Should have at least one user (admin)"
    
    def test_get_users_excludes_password_hash(self):
        """GET /api/users should not return password_hash"""
        response = requests.get(f"{BASE_URL}/api/users", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        for user in data:
            assert "password_hash" not in user, "password_hash should not be exposed"
    
    def test_create_user_success(self):
        """POST /api/users creates a new user"""
        # Create test user
        response = requests.post(f"{BASE_URL}/api/users", headers=self.headers, json={
            "username": "TEST_newuser",
            "password": "TestPass123",
            "name": "Test New User"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("username") == "test_newuser", "Username should be lowercase"
        assert data.get("name") == "Test New User"
        
        # Verify user exists
        users_response = requests.get(f"{BASE_URL}/api/users", headers=self.headers)
        users = users_response.json()
        usernames = [u["username"] for u in users]
        assert "test_newuser" in usernames, "Created user should appear in list"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/users/test_newuser", headers=self.headers)
    
    def test_create_user_short_password_fails(self):
        """POST /api/users with short password returns 400"""
        response = requests.post(f"{BASE_URL}/api/users", headers=self.headers, json={
            "username": "TEST_shortpw",
            "password": "12345",  # Less than 6 chars
            "name": "Short Password User"
        })
        assert response.status_code == 400
        assert "6 karakter" in response.json().get("detail", "")
    
    def test_create_user_duplicate_fails(self):
        """POST /api/users with existing username returns 400"""
        response = requests.post(f"{BASE_URL}/api/users", headers=self.headers, json={
            "username": "arigastro",  # Already exists
            "password": "TestPass123",
            "name": "Duplicate User"
        })
        assert response.status_code == 400
        assert "zaten mevcut" in response.json().get("detail", "")
    
    def test_change_password_success(self):
        """PUT /api/users/{username}/password changes password"""
        # Create test user first
        requests.post(f"{BASE_URL}/api/users", headers=self.headers, json={
            "username": "TEST_pwchange",
            "password": "OldPass123",
            "name": "Password Change Test"
        })
        
        # Change password
        response = requests.put(f"{BASE_URL}/api/users/test_pwchange/password", headers=self.headers, json={
            "new_password": "NewPass456"
        })
        assert response.status_code == 200
        assert response.json().get("message") == "Sifre guncellendi"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/users/test_pwchange", headers=self.headers)
    
    def test_change_password_short_fails(self):
        """PUT /api/users/{username}/password with short password returns 400"""
        response = requests.put(f"{BASE_URL}/api/users/arigastro/password", headers=self.headers, json={
            "new_password": "12345"  # Less than 6 chars
        })
        assert response.status_code == 400
        assert "6 karakter" in response.json().get("detail", "")
    
    def test_delete_user_success(self):
        """DELETE /api/users/{username} deletes user"""
        # Create test user first
        requests.post(f"{BASE_URL}/api/users", headers=self.headers, json={
            "username": "TEST_todelete",
            "password": "DeleteMe123",
            "name": "To Be Deleted"
        })
        
        # Delete user
        response = requests.delete(f"{BASE_URL}/api/users/test_todelete", headers=self.headers)
        assert response.status_code == 200
        assert response.json().get("message") == "Kullanici silindi"
        
        # Verify user is gone
        users_response = requests.get(f"{BASE_URL}/api/users", headers=self.headers)
        users = users_response.json()
        usernames = [u["username"] for u in users]
        assert "test_todelete" not in usernames, "Deleted user should not appear in list"
    
    def test_delete_self_fails(self):
        """DELETE /api/users/{username} cannot delete yourself"""
        response = requests.delete(f"{BASE_URL}/api/users/arigastro", headers=self.headers)
        assert response.status_code == 400
        assert "Kendinizi silemezsiniz" in response.json().get("detail", "")
    
    def test_delete_nonexistent_user_fails(self):
        """DELETE /api/users/{username} for nonexistent user returns 404"""
        response = requests.delete(f"{BASE_URL}/api/users/nonexistent_user_xyz", headers=self.headers)
        # API returns 404 when user not found
        assert response.status_code in [400, 404], f"Expected 400 or 404, got {response.status_code}"


class TestDashboardStats:
    """Dashboard stats endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "arigastro",
            "password": "Arigastro2026!"
        })
        assert response.status_code == 200
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_dashboard_stats_returns_expected_fields(self):
        """GET /api/dashboard/stats returns all expected fields"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        expected_fields = ["total_products", "tracked_products", "matched_products", 
                          "competitors_cheaper", "we_are_cheaper", "seo_generated"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

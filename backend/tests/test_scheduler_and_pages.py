"""
Test scheduler status API and new pages (Settings, Guide)
Tests for iteration 5 - APScheduler integration
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "arigastro",
            "password": "Arigastro2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Token not in response"
        return data["token"]
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "arigastro",
            "password": "Arigastro2026!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["username"] == "arigastro"
        assert data["role"] == "admin"
        print(f"✓ Login successful: {data['username']} ({data['role']})")


class TestSchedulerAPI:
    """Scheduler status API tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "arigastro",
            "password": "Arigastro2026!"
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    def test_scheduler_status_endpoint(self, auth_token):
        """Test GET /api/scheduler/status returns scheduler info"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/scheduler/status", headers=headers)
        
        assert response.status_code == 200, f"Scheduler status failed: {response.text}"
        data = response.json()
        
        # Check scheduler_running field
        assert "scheduler_running" in data, "Missing scheduler_running field"
        assert data["scheduler_running"] == True, "Scheduler should be running"
        print(f"✓ Scheduler running: {data['scheduler_running']}")
        
        # Check jobs field
        assert "jobs" in data, "Missing jobs field"
        assert isinstance(data["jobs"], list), "Jobs should be a list"
        assert len(data["jobs"]) == 2, f"Expected 2 jobs, got {len(data['jobs'])}"
        print(f"✓ Found {len(data['jobs'])} scheduled jobs")
        
        # Check job details
        job_ids = [job["id"] for job in data["jobs"]]
        assert "feed_sync" in job_ids, "Missing feed_sync job"
        assert "price_check_cron" in job_ids, "Missing price_check_cron job"
        
        for job in data["jobs"]:
            assert "id" in job, "Job missing id"
            assert "name" in job, "Job missing name"
            assert "next_run" in job, "Job missing next_run"
            print(f"✓ Job: {job['name']} - Next run: {job['next_run']}")
        
        # Check job names match expected format
        feed_sync_job = next((j for j in data["jobs"] if j["id"] == "feed_sync"), None)
        assert feed_sync_job is not None
        assert "12 saat" in feed_sync_job["name"], f"Feed sync job name should contain '12 saat': {feed_sync_job['name']}"
        
        price_check_job = next((j for j in data["jobs"] if j["id"] == "price_check_cron"), None)
        assert price_check_job is not None
        assert "24 saat" in price_check_job["name"], f"Price check job name should contain '24 saat': {price_check_job['name']}"
        
        print("✓ All scheduler status checks passed")
    
    def test_scheduler_status_requires_auth(self):
        """Test scheduler status requires authentication"""
        response = requests.get(f"{BASE_URL}/api/scheduler/status")
        assert response.status_code == 401, "Should require authentication"
        print("✓ Scheduler status requires authentication")


class TestFeedStatus:
    """Feed status API tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "arigastro",
            "password": "Arigastro2026!"
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    def test_feed_status_endpoint(self, auth_token):
        """Test GET /api/feed/status returns feed info"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/feed/status", headers=headers)
        
        assert response.status_code == 200, f"Feed status failed: {response.text}"
        data = response.json()
        
        assert "feed_url" in data, "Missing feed_url field"
        assert "total_products" in data, "Missing total_products field"
        assert "products_with_price" in data, "Missing products_with_price field"
        
        print(f"✓ Feed status: {data['total_products']} products, {data['products_with_price']} with price")


class TestProductsAPI:
    """Products API tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "arigastro",
            "password": "Arigastro2026!"
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    def test_products_list(self, auth_token):
        """Test GET /api/products returns products list"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/products", headers=headers)
        
        assert response.status_code == 200, f"Products list failed: {response.text}"
        data = response.json()
        
        assert "products" in data, "Missing products field"
        assert "total" in data, "Missing total field"
        assert "page" in data, "Missing page field"
        assert "pages" in data, "Missing pages field"
        
        print(f"✓ Products: {data['total']} total, page {data['page']}/{data['pages']}")
    
    def test_products_matched_filter(self, auth_token):
        """Test GET /api/products with matched_only filter"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/products?matched_only=true", headers=headers)
        
        assert response.status_code == 200, f"Matched products failed: {response.text}"
        data = response.json()
        
        # All returned products should be matched
        for product in data["products"]:
            assert product.get("akakce_matched") == True, f"Product {product.get('slug')} should be matched"
        
        print(f"✓ Matched products filter: {data['total']} matched products")
    
    def test_products_tracked_categories_filter(self, auth_token):
        """Test GET /api/products with tracked_categories_only filter"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/products?tracked_categories_only=true", headers=headers)
        
        assert response.status_code == 200, f"Tracked categories filter failed: {response.text}"
        data = response.json()
        
        print(f"✓ Tracked categories filter: {data['total']} products in tracked categories")


class TestDashboardAPI:
    """Dashboard stats API tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "arigastro",
            "password": "Arigastro2026!"
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    def test_dashboard_stats(self, auth_token):
        """Test GET /api/dashboard/stats returns stats"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=headers)
        
        assert response.status_code == 200, f"Dashboard stats failed: {response.text}"
        data = response.json()
        
        expected_fields = [
            "total_products", "tracked_products", "matched_products",
            "unmatched_products", "competitors_cheaper", "we_are_cheaper",
            "seo_generated", "total_categories", "tracked_categories"
        ]
        
        for field in expected_fields:
            assert field in data, f"Missing {field} field"
        
        print(f"✓ Dashboard stats: {data['total_products']} products, {data['matched_products']} matched")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

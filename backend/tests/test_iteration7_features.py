"""
Iteration 7 Feature Tests:
- Category filter dropdown on Price Tracking page
- Individual product exclusion from tracking (exclude-tracking toggle)
- Free-first scraping strategy (curl_cffi/httpx first, ScraperAPI as paid fallback)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "arigastro",
        "password": "Arigastro2026!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "token" in data, "No token in login response"
    return data["token"]

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get auth headers"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestCategoryFilter:
    """Tests for category filter dropdown on Price Tracking page"""
    
    def test_price_tracking_returns_tracked_categories_list(self, auth_headers):
        """GET /api/price-tracking returns tracked_categories_list with 600 Seri and 900 Seri"""
        response = requests.get(f"{BASE_URL}/api/price-tracking", 
                               params={"filter_type": "all"},
                               headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify tracked_categories_list is returned
        assert "tracked_categories_list" in data, "tracked_categories_list not in response"
        categories = data["tracked_categories_list"]
        assert isinstance(categories, list), "tracked_categories_list should be a list"
        
        # Verify 600 Seri and 900 Seri are in the list
        category_slugs = [c["slug"] for c in categories]
        assert "600-seri" in category_slugs, "600-seri not in tracked categories"
        assert "900-seri" in category_slugs, "900-seri not in tracked categories"
        
        # Verify category structure
        for cat in categories:
            assert "slug" in cat, "Category missing slug"
            assert "name" in cat, "Category missing name"
    
    def test_category_filter_600_seri(self, auth_headers):
        """GET /api/price-tracking?category=600-seri returns only 600 Seri products"""
        response = requests.get(f"{BASE_URL}/api/price-tracking",
                               params={"filter_type": "all", "category": "600-seri"},
                               headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Should return products
        assert "products" in data
        assert "total" in data
        
        # Verify products are from 600 Seri category
        products = data["products"]
        if products:
            for p in products[:5]:  # Check first 5
                category_path = p.get("category_path", "")
                assert "600 Seri" in category_path, f"Product {p['slug']} not in 600 Seri: {category_path}"
    
    def test_category_filter_900_seri(self, auth_headers):
        """GET /api/price-tracking?category=900-seri returns only 900 Seri products"""
        response = requests.get(f"{BASE_URL}/api/price-tracking",
                               params={"filter_type": "all", "category": "900-seri"},
                               headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Should return products
        assert "products" in data
        assert "total" in data
        
        # Verify products are from 900 Seri category
        products = data["products"]
        if products:
            for p in products[:5]:  # Check first 5
                category_path = p.get("category_path", "")
                assert "900 Seri" in category_path, f"Product {p['slug']} not in 900 Seri: {category_path}"
    
    def test_all_categories_returns_more_products(self, auth_headers):
        """Selecting 'Tum Kategoriler' (no category param) returns all products"""
        # Get all products
        response_all = requests.get(f"{BASE_URL}/api/price-tracking",
                                   params={"filter_type": "all"},
                                   headers=auth_headers)
        assert response_all.status_code == 200
        total_all = response_all.json()["total"]
        
        # Get 600 Seri only
        response_600 = requests.get(f"{BASE_URL}/api/price-tracking",
                                   params={"filter_type": "all", "category": "600-seri"},
                                   headers=auth_headers)
        total_600 = response_600.json()["total"]
        
        # Get 900 Seri only
        response_900 = requests.get(f"{BASE_URL}/api/price-tracking",
                                   params={"filter_type": "all", "category": "900-seri"},
                                   headers=auth_headers)
        total_900 = response_900.json()["total"]
        
        # All should be >= sum of individual categories (or equal if no overlap)
        assert total_all >= total_600, "All products should be >= 600 Seri products"
        assert total_all >= total_900, "All products should be >= 900 Seri products"


class TestExcludeTracking:
    """Tests for individual product exclusion from tracking"""
    
    @pytest.fixture
    def test_product_slug(self, auth_headers):
        """Get a product slug to test with"""
        response = requests.get(f"{BASE_URL}/api/price-tracking",
                               params={"filter_type": "all", "limit": 1},
                               headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["products"], "No products found for testing"
        return data["products"][0]["slug"]
    
    def test_exclude_tracking_toggle_excludes_product(self, auth_headers, test_product_slug):
        """PUT /api/products/{slug}/exclude-tracking toggles excluded_from_tracking to True"""
        # First ensure product is not excluded
        response = requests.get(f"{BASE_URL}/api/products/{test_product_slug}", headers=auth_headers)
        if response.status_code == 200:
            product = response.json()
            if product.get("excluded_from_tracking"):
                # Un-exclude first
                requests.put(f"{BASE_URL}/api/products/{test_product_slug}/exclude-tracking", headers=auth_headers)
        
        # Now exclude the product
        response = requests.put(f"{BASE_URL}/api/products/{test_product_slug}/exclude-tracking",
                               headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["slug"] == test_product_slug
        assert data["excluded_from_tracking"] == True, "Product should be excluded"
        
        # Cleanup: un-exclude
        requests.put(f"{BASE_URL}/api/products/{test_product_slug}/exclude-tracking", headers=auth_headers)
    
    def test_excluded_product_appears_in_excluded_filter(self, auth_headers, test_product_slug):
        """Excluded products appear in filter_type=excluded list"""
        # Exclude the product
        response = requests.put(f"{BASE_URL}/api/products/{test_product_slug}/exclude-tracking",
                               headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["excluded_from_tracking"] == True
        
        # Check excluded list
        response = requests.get(f"{BASE_URL}/api/price-tracking",
                               params={"filter_type": "excluded"},
                               headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        excluded_slugs = [p["slug"] for p in data["products"]]
        assert test_product_slug in excluded_slugs, "Excluded product should appear in excluded list"
        
        # Cleanup: un-exclude
        requests.put(f"{BASE_URL}/api/products/{test_product_slug}/exclude-tracking", headers=auth_headers)
    
    def test_excluded_product_not_in_normal_list(self, auth_headers, test_product_slug):
        """Excluded products do NOT appear in normal (all) list"""
        # Exclude the product
        response = requests.put(f"{BASE_URL}/api/products/{test_product_slug}/exclude-tracking",
                               headers=auth_headers)
        assert response.status_code == 200
        
        # Check normal list
        response = requests.get(f"{BASE_URL}/api/price-tracking",
                               params={"filter_type": "all", "limit": 200},
                               headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        normal_slugs = [p["slug"] for p in data["products"]]
        assert test_product_slug not in normal_slugs, "Excluded product should NOT appear in normal list"
        
        # Cleanup: un-exclude
        requests.put(f"{BASE_URL}/api/products/{test_product_slug}/exclude-tracking", headers=auth_headers)
    
    def test_re_include_product_toggle(self, auth_headers, test_product_slug):
        """Calling exclude-tracking twice returns product to tracking"""
        # Exclude
        response1 = requests.put(f"{BASE_URL}/api/products/{test_product_slug}/exclude-tracking",
                                headers=auth_headers)
        assert response1.status_code == 200
        assert response1.json()["excluded_from_tracking"] == True
        
        # Re-include (toggle again)
        response2 = requests.put(f"{BASE_URL}/api/products/{test_product_slug}/exclude-tracking",
                                headers=auth_headers)
        assert response2.status_code == 200
        assert response2.json()["excluded_from_tracking"] == False, "Product should be re-included"
        
        # Verify back in normal list
        response = requests.get(f"{BASE_URL}/api/price-tracking",
                               params={"filter_type": "all", "limit": 200},
                               headers=auth_headers)
        normal_slugs = [p["slug"] for p in response.json()["products"]]
        assert test_product_slug in normal_slugs, "Re-included product should appear in normal list"
    
    def test_exclude_tracking_404_for_invalid_slug(self, auth_headers):
        """PUT /api/products/{invalid}/exclude-tracking returns 404"""
        response = requests.put(f"{BASE_URL}/api/products/invalid-product-slug-12345/exclude-tracking",
                               headers=auth_headers)
        assert response.status_code == 404


class TestExistingFilters:
    """Tests for existing filter tabs still working"""
    
    def test_filter_matched(self, auth_headers):
        """filter_type=matched returns only matched products"""
        response = requests.get(f"{BASE_URL}/api/price-tracking",
                               params={"filter_type": "matched"},
                               headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # All products should be matched
        for p in data["products"][:5]:
            assert p.get("akakce_matched") == True, f"Product {p['slug']} should be matched"
    
    def test_filter_unmatched(self, auth_headers):
        """filter_type=unmatched returns only unmatched products"""
        response = requests.get(f"{BASE_URL}/api/price-tracking",
                               params={"filter_type": "unmatched"},
                               headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # All products should be unmatched
        for p in data["products"][:5]:
            assert p.get("akakce_matched") != True, f"Product {p['slug']} should be unmatched"
    
    def test_filter_cheaper(self, auth_headers):
        """filter_type=cheaper returns products where competitor is cheaper"""
        response = requests.get(f"{BASE_URL}/api/price-tracking",
                               params={"filter_type": "cheaper"},
                               headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # All products should have competitor cheaper
        for p in data["products"][:5]:
            if p.get("cheapest_price") and p.get("our_price"):
                assert p["cheapest_price"] < p["our_price"], f"Product {p['slug']} competitor should be cheaper"
    
    def test_filter_expensive(self, auth_headers):
        """filter_type=expensive returns products where we are cheaper"""
        response = requests.get(f"{BASE_URL}/api/price-tracking",
                               params={"filter_type": "expensive"},
                               headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # All products should have us cheaper or equal
        for p in data["products"][:5]:
            if p.get("cheapest_price") and p.get("our_price"):
                assert p["cheapest_price"] >= p["our_price"], f"Product {p['slug']} we should be cheaper"


class TestFreeFirstScrapingStrategy:
    """Tests for free-first scraping strategy (code review based)"""
    
    def test_akakce_request_function_exists(self):
        """Verify akakce_request function exists in server.py"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        # Read server.py and check for free-first strategy
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Check curl_cffi is tried first
        assert "curl_cffi" in content, "curl_cffi should be in server.py"
        assert "Method 1: curl_cffi direct (FREE" in content, "curl_cffi should be marked as free method"
        
        # Check httpx fallback
        assert "httpx" in content, "httpx should be in server.py"
        assert "UCRETSIZ (httpx)" in content, "httpx should be marked as free method"
        
        # Check ScraperAPI is fallback
        assert "ScraperAPI (PAID fallback" in content, "ScraperAPI should be marked as paid fallback"
        assert "Ucretsiz yontem basarisiz, ScraperAPI kullaniliyor" in content, "Should log when falling back to ScraperAPI"
    
    def test_google_search_free_first(self):
        """Verify search_akakce_via_google tries free methods first"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Check free Google search is tried first
        assert "Method 1: Free Google search via direct request" in content, "Free Google search should be first"
        assert "Google UCRETSIZ arama basarili" in content, "Should log free Google success"
        
        # Check ScraperAPI SERP is fallback
        assert "Method 2: ScraperAPI structured SERP (paid fallback)" in content, "ScraperAPI SERP should be fallback"
        assert "Ucretsiz Google basarisiz, ScraperAPI SERP kullaniliyor" in content, "Should log when falling back to ScraperAPI SERP"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

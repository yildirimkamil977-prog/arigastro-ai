#!/usr/bin/env python3
"""
Backend API Testing for ARI AI Admin Panel
Tests all authentication, sitemap import, CRUD operations, and dashboard endpoints
"""

import requests
import sys
import json
from datetime import datetime

class AriAIAPITester:
    def __init__(self, base_url="https://price-pulse-51.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=30)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict) and len(str(response_data)) < 200:
                        print(f"   Response: {response_data}")
                except:
                    pass
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error: {error_detail}")
                except:
                    print(f"   Response text: {response.text[:200]}")
                self.failed_tests.append({
                    "test": name,
                    "expected": expected_status,
                    "actual": response.status_code,
                    "error": response.text[:200]
                })

            return success, response.json() if success and response.text else {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout")
            self.failed_tests.append({"test": name, "error": "Request timeout"})
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append({"test": name, "error": str(e)})
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        success, response = self.run_test(
            "Root API Endpoint",
            "GET",
            "",
            200
        )
        return success

    def test_login(self, username, password):
        """Test login and get token"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"username": username, "password": password}
        )
        if success and 'token' in response:
            self.token = response['token']
            print(f"   Token received: {self.token[:20]}...")
            return True
        return False

    def test_get_me(self):
        """Test get current user info"""
        success, response = self.run_test(
            "Get Current User",
            "GET",
            "auth/me",
            200
        )
        return success, response

    def test_logout(self):
        """Test logout"""
        success, response = self.run_test(
            "Logout",
            "POST",
            "auth/logout",
            200
        )
        return success

    def test_import_categories(self):
        """Test importing categories from sitemap"""
        success, response = self.run_test(
            "Import Categories from Sitemap",
            "POST",
            "sitemap/import-categories",
            200
        )
        return success, response

    def test_import_products(self):
        """Test importing products from sitemap"""
        success, response = self.run_test(
            "Import Products from Sitemap",
            "POST",
            "sitemap/import-products",
            200
        )
        return success, response

    def test_list_categories(self):
        """Test listing categories"""
        success, response = self.run_test(
            "List Categories",
            "GET",
            "categories",
            200
        )
        return success, response

    def test_toggle_category_tracking(self, slug):
        """Test toggling category tracking"""
        success, response = self.run_test(
            f"Toggle Category Tracking ({slug})",
            "PUT",
            f"categories/{slug}/toggle-tracking",
            200
        )
        return success, response

    def test_list_products(self):
        """Test listing products with pagination"""
        success, response = self.run_test(
            "List Products",
            "GET",
            "products?page=1&limit=10",
            200
        )
        return success, response

    def test_update_product_price(self, slug, price):
        """Test updating product price"""
        success, response = self.run_test(
            f"Update Product Price ({slug})",
            "PUT",
            f"products/{slug}",
            200,
            data={"our_price": price}
        )
        return success, response

    def test_dashboard_stats(self):
        """Test dashboard statistics"""
        success, response = self.run_test(
            "Dashboard Statistics",
            "GET",
            "dashboard/stats",
            200
        )
        return success, response

    def test_price_tracking(self):
        """Test price tracking endpoint"""
        success, response = self.run_test(
            "Price Tracking Data",
            "GET",
            "price-tracking?page=1&limit=10",
            200
        )
        return success, response

    def test_check_akakce_price(self, slug):
        """Test Akakçe price checking for a product"""
        success, response = self.run_test(
            f"Check Akakçe Price ({slug})",
            "POST",
            f"products/{slug}/check-akakce",
            200
        )
        return success, response

    def test_seo_generation(self, slug):
        """Test SEO content generation"""
        success, response = self.run_test(
            f"Generate SEO Content ({slug})",
            "POST",
            f"seo/generate/{slug}",
            200
        )
        return success, response

    def test_get_seo_content(self, slug):
        """Test getting existing SEO content"""
        success, response = self.run_test(
            f"Get SEO Content ({slug})",
            "GET",
            f"seo/{slug}",
            200
        )
        return success, response

    def test_feed_status(self):
        """Test feed status endpoint"""
        success, response = self.run_test(
            "Feed Status",
            "GET",
            "feed/status",
            200
        )
        return success, response

    def test_sync_prices_from_feed(self):
        """Test syncing prices from Google Merchant Feed"""
        success, response = self.run_test(
            "Sync Prices from Feed",
            "POST",
            "feed/sync-prices",
            200
        )
        return success, response

    def test_products_with_search(self, search_term):
        """Test product search functionality"""
        success, response = self.run_test(
            f"Search Products ({search_term})",
            "GET",
            f"products?search={search_term}",
            200
        )
        return success, response

def main():
    print("🚀 Starting ARI AI Admin Panel API Tests")
    print("=" * 60)
    
    # Setup
    tester = AriAIAPITester()
    
    # Test credentials from environment
    admin_username = "arigastro"
    admin_password = "Arigastro2026!"
    
    # Test sequence
    print("\n📋 Phase 1: Basic API & Authentication Tests")
    
    # Test root endpoint
    if not tester.test_root_endpoint():
        print("❌ Root endpoint failed, stopping tests")
        return 1
    
    # Test login
    if not tester.test_login(admin_username, admin_password):
        print("❌ Login failed, stopping tests")
        return 1
    
    # Test get current user
    success, user_data = tester.test_get_me()
    if not success:
        print("❌ Get current user failed")
        return 1
    
    print(f"\n📋 Phase 2: Sitemap Import Tests")
    
    # Test category import
    cat_success, cat_data = tester.test_import_categories()
    if cat_success:
        print(f"   Categories imported: {cat_data.get('imported', 0)}, Total: {cat_data.get('total', 0)}")
    
    # Test product import  
    prod_success, prod_data = tester.test_import_products()
    if prod_success:
        print(f"   Products imported: {prod_data.get('imported', 0)}, Total: {prod_data.get('total', 0)}")
    
    print(f"\n📋 Phase 3: CRUD Operations Tests")
    
    # Test list categories
    cat_list_success, categories = tester.test_list_categories()
    first_category_slug = None
    if cat_list_success and categories:
        first_category_slug = categories[0].get('slug') if categories else None
        print(f"   Found {len(categories)} categories")
    
    # Test toggle category tracking if we have categories
    if first_category_slug:
        tester.test_toggle_category_tracking(first_category_slug)
    
    # Test list products
    prod_list_success, products_data = tester.test_list_products()
    first_product_slug = None
    if prod_list_success and products_data.get('products'):
        first_product_slug = products_data['products'][0].get('slug')
        print(f"   Found {products_data.get('total', 0)} products")
    
    # Test update product price if we have products
    if first_product_slug:
        tester.test_update_product_price(first_product_slug, 1500.0)
    
    print(f"\n📋 Phase 4: Feed Sync Tests (NEW FEATURES)")
    
    # Test feed status
    tester.test_feed_status()
    
    # Test feed sync functionality
    feed_success, feed_data = tester.test_sync_prices_from_feed()
    if feed_success:
        print(f"   Feed sync result: {feed_data.get('updated', 0)} updated, {feed_data.get('new_products', 0)} new products")
        print(f"   Products with prices: {feed_data.get('products_with_price', 0)}")
    
    # Test product search
    tester.test_products_with_search("tava")
    
    print(f"\n📋 Phase 5: Dashboard & Analytics Tests")
    
    # Test dashboard stats
    tester.test_dashboard_stats()
    
    # Test price tracking
    tester.test_price_tracking()
    
    print(f"\n📋 Phase 6: Advanced Features Tests")
    
    # Test Akakçe price checking (may fail due to bot protection)
    if first_product_slug:
        print("   Note: Akakçe checking may fail due to bot protection")
        tester.test_check_akakce_price(first_product_slug)
    
    # Test SEO generation (requires OpenAI API key)
    if first_product_slug:
        print("   Note: SEO generation requires valid OpenAI API key")
        tester.test_seo_generation(first_product_slug)
        tester.test_get_seo_content(first_product_slug)
    
    print(f"\n📋 Phase 7: Cleanup Tests")
    
    # Test logout
    tester.test_logout()
    
    # Print results
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.failed_tests:
        print(f"\n❌ Failed Tests:")
        for failure in tester.failed_tests:
            print(f"   - {failure['test']}: {failure.get('error', 'Unknown error')}")
    
    success_rate = (tester.tests_passed / tester.tests_run) * 100 if tester.tests_run > 0 else 0
    print(f"📈 Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("🎉 Backend API tests mostly successful!")
        return 0
    else:
        print("⚠️  Backend API has significant issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())
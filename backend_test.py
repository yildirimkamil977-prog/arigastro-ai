import requests
import sys
import json
from datetime import datetime

class AriAIAPITester:
    def __init__(self, base_url="https://price-pulse-51.preview.emergentagent.com"):
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

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict) and len(str(response_data)) < 500:
                        print(f"   Response: {response_data}")
                    elif isinstance(response_data, dict):
                        print(f"   Response keys: {list(response_data.keys())}")
                except:
                    print(f"   Response: {response.text[:200]}")
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:300]}")
                self.failed_tests.append({
                    "test": name,
                    "expected": expected_status,
                    "actual": response.status_code,
                    "response": response.text[:300]
                })

            return success, response.json() if success and response.text else {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append({
                "test": name,
                "error": str(e)
            })
            return False, {}

    def test_login(self, username, password):
        """Test login and get token"""
        success, response = self.run_test(
            "Login",
            "POST",
            "api/auth/login",
            200,
            data={"username": username, "password": password}
        )
        if success and 'token' in response:
            self.token = response['token']
            print(f"   Token obtained: {self.token[:20]}...")
            return True
        return False

    def test_auth_me(self):
        """Test auth/me endpoint"""
        success, response = self.run_test(
            "Get Current User",
            "GET",
            "api/auth/me",
            200
        )
        return success

    def test_dashboard_stats(self):
        """Test dashboard stats"""
        success, response = self.run_test(
            "Dashboard Stats",
            "GET",
            "api/dashboard/stats",
            200
        )
        return success

    def test_products_all(self):
        """Test get all products"""
        success, response = self.run_test(
            "Get All Products",
            "GET",
            "api/products",
            200
        )
        return success, response

    def test_products_matched_only(self):
        """Test get matched products only"""
        success, response = self.run_test(
            "Get Matched Products Only",
            "GET",
            "api/products?matched_only=true",
            200
        )
        return success, response

    def test_products_tracked_categories_only(self):
        """Test get products from tracked categories only"""
        success, response = self.run_test(
            "Get Products from Tracked Categories Only",
            "GET",
            "api/products?tracked_categories_only=true",
            200
        )
        return success, response

    def test_set_akakce_match(self, product_slug):
        """Test setting Akakçe match for a product"""
        test_url = "https://www.akakce.com/test-product-page.html"
        success, response = self.run_test(
            f"Set Akakçe Match for {product_slug}",
            "POST",
            f"api/products/{product_slug}/set-akakce-match",
            200,
            data={
                "akakce_product_url": test_url,
                "akakce_product_name": "Test Product"
            }
        )
        return success

    def test_check_akakce(self, product_slug):
        """Test checking Akakçe prices for a product"""
        success, response = self.run_test(
            f"Check Akakçe Prices for {product_slug}",
            "POST",
            f"api/products/{product_slug}/check-akakce",
            200
        )
        return success, response

    def test_seo_generate(self, product_slug):
        """Test SEO generation for a product"""
        success, response = self.run_test(
            f"Generate SEO for {product_slug}",
            "POST",
            f"api/seo/generate/{product_slug}",
            200
        )
        return success, response

    def test_categories(self):
        """Test get categories"""
        success, response = self.run_test(
            "Get Categories",
            "GET",
            "api/categories",
            200
        )
        return success, response

    def test_price_tracking(self):
        """Test price tracking endpoint"""
        success, response = self.run_test(
            "Get Price Tracking Data",
            "GET",
            "api/price-tracking",
            200
        )
        return success, response

def main():
    print("🚀 Starting ARI AI API Testing...")
    print("=" * 60)
    
    # Setup
    tester = AriAIAPITester()
    
    # Test credentials from review request
    username = "arigastro"
    password = "Arigastro2026!"

    # Run authentication tests
    print("\n📋 AUTHENTICATION TESTS")
    print("-" * 30)
    
    if not tester.test_login(username, password):
        print("❌ Login failed, stopping tests")
        return 1

    if not tester.test_auth_me():
        print("❌ Auth/me failed")
        return 1

    # Test dashboard
    print("\n📊 DASHBOARD TESTS")
    print("-" * 30)
    tester.test_dashboard_stats()

    # Test product endpoints
    print("\n📦 PRODUCT TESTS")
    print("-" * 30)
    
    # Get all products first
    success, all_products = tester.test_products_all()
    if not success:
        print("❌ Failed to get products")
        return 1

    # Test filtering
    tester.test_products_matched_only()
    tester.test_products_tracked_categories_only()

    # Test categories
    print("\n📂 CATEGORY TESTS")
    print("-" * 30)
    success, categories = tester.test_categories()

    # Test price tracking
    print("\n💰 PRICE TRACKING TESTS")
    print("-" * 30)
    tester.test_price_tracking()

    # Test Akakçe functionality with a real product if available
    print("\n🔗 AKAKÇE INTEGRATION TESTS")
    print("-" * 30)
    
    if all_products and 'products' in all_products and len(all_products['products']) > 0:
        test_product = all_products['products'][0]
        product_slug = test_product['slug']
        print(f"Using test product: {test_product['name']} ({product_slug})")
        
        # Test setting Akakçe match
        tester.test_set_akakce_match(product_slug)
        
        # Test checking Akakçe prices (this will likely fail due to 403 as mentioned)
        success, akakce_result = tester.test_check_akakce(product_slug)
        
        # Test SEO generation
        print("\n✨ SEO GENERATION TESTS")
        print("-" * 30)
        success, seo_result = tester.test_seo_generate(product_slug)
        if success and 'word_count' in seo_result:
            word_count = seo_result['word_count']
            keyword_density = seo_result.get('keyword_density', 0)
            print(f"   SEO Content Generated:")
            print(f"   - Word count: {word_count} (target: 400+)")
            print(f"   - Keyword density: {keyword_density}%")
            if word_count >= 400:
                print("   ✅ Word count meets requirement (400+)")
            else:
                print("   ❌ Word count below requirement")
    else:
        print("⚠️  No products available for Akakçe/SEO testing")

    # Print final results
    print("\n" + "=" * 60)
    print("📊 FINAL TEST RESULTS")
    print("=" * 60)
    print(f"Tests run: {tester.tests_run}")
    print(f"Tests passed: {tester.tests_passed}")
    print(f"Tests failed: {len(tester.failed_tests)}")
    print(f"Success rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    if tester.failed_tests:
        print("\n❌ FAILED TESTS:")
        for i, test in enumerate(tester.failed_tests, 1):
            print(f"{i}. {test['test']}")
            if 'error' in test:
                print(f"   Error: {test['error']}")
            else:
                print(f"   Expected: {test['expected']}, Got: {test['actual']}")
                print(f"   Response: {test['response']}")
    
    return 0 if len(tester.failed_tests) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
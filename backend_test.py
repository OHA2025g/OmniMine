import requests
import json
import sys
from datetime import datetime

class SmartRoutingAPITester:
    def __init__(self, base_url="https://feedback-ai-23.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.admin_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.agent_ids = []
        self.case_ids = []

    def run_test(self, name, method, endpoint, expected_status, data=None, use_admin=False):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        # Use admin token for privileged operations
        token = self.admin_token if use_admin else self.token
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"   Response: {response.json()}")
                except:
                    print(f"   Response: {response.text}")

            return success, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_login(self, email, password):
        """Test login and get token"""
        success, response = self.run_test(
            f"Login as {email}",
            "POST",
            "auth/login",
            200,
            data={"email": email, "password": password}
        )
        if success and 'access_token' in response:
            return response['access_token']
        return None

    def test_get_agent_profiles(self):
        """Test GET /api/agents/profiles"""
        success, response = self.run_test(
            "Get Agent Profiles",
            "GET",
            "agents/profiles",
            200
        )
        if success and isinstance(response, list):
            # Store agent IDs for later tests
            self.agent_ids = [agent.get('id') for agent in response if agent.get('id')]
            print(f"   Found {len(response)} agents")
            for agent in response[:2]:  # Show first 2
                print(f"   - {agent.get('name', 'Unknown')} ({agent.get('email', 'no-email')})")
        return success

    def test_get_agent_skills(self):
        """Test GET /api/agents/skills"""
        success, response = self.run_test(
            "Get Agent Skills",
            "GET",
            "agents/skills",
            200
        )
        if success and 'skills' in response:
            print(f"   Available skills: {len(response['skills'])}")
            for skill in response['skills'][:3]:  # Show first 3
                print(f"   - {skill.get('label', skill.get('value', 'Unknown'))}")
        return success

    def test_update_agent_profile(self):
        """Test PUT /api/agents/profiles/{user_id}"""
        if not self.agent_ids:
            print("⚠️  No agent IDs available for profile update test")
            return False
        
        agent_id = self.agent_ids[0]
        profile_data = {
            "skills": ["technical_support", "product_issues"],
            "max_workload": 15,
            "is_available": True,
            "shift_start": "09:00",
            "shift_end": "17:00"
        }
        
        success, response = self.run_test(
            f"Update Agent Profile ({agent_id[:8]}...)",
            "PUT",
            f"agents/profiles/{agent_id}",
            200,
            data=profile_data
        )
        return success

    def test_create_demo_case(self):
        """Create a demo case for routing tests"""
        # First create feedback
        feedback_data = {
            "content": "My account was hacked and I can't access my billing information. This is urgent!",
            "source": "support_ticket",
            "author_name": "Test User"
        }
        
        success, feedback_response = self.run_test(
            "Create Demo Feedback for Routing",
            "POST",
            "feedback",
            200,  # Note: Based on server.py, this should return 200 with Feedback model
            data=feedback_data
        )
        
        if not success:
            return False
        
        feedback_id = feedback_response.get('id')
        if not feedback_id:
            print("❌ Failed to get feedback ID")
            return False
        
        # Create case from feedback
        case_data = {
            "feedback_id": feedback_id,
            "title": "Security Issue: Account Hacked - Billing Access",
            "priority": "high"
        }
        
        success, case_response = self.run_test(
            "Create Demo Case for Routing",
            "POST",
            "cases",
            200,  # Note: Based on server.py, this should return 200 with Case model
            data=case_data
        )
        
        if success and case_response.get('id'):
            self.case_ids.append(case_response['id'])
            print(f"   Created case ID: {case_response['id'][:8]}...")
        
        return success

    def test_smart_routing_analysis(self):
        """Test POST /api/routing/analyze/{case_id}"""
        if not self.case_ids:
            print("⚠️  No case IDs available for routing analysis test")
            return False
        
        case_id = self.case_ids[0]
        success, response = self.run_test(
            f"Smart Routing Analysis ({case_id[:8]}...)",
            "POST",
            f"routing/analyze/{case_id}",
            200
        )
        
        if success:
            # Check response structure
            if 'analysis' in response:
                analysis = response['analysis']
                print(f"   AI Analysis - Category: {analysis.get('category', 'N/A')}")
                print(f"   Required Skills: {', '.join(analysis.get('required_skills', []))}")
                print(f"   Complexity: {analysis.get('complexity_score', 'N/A')}/10")
            
            if 'routing' in response and response['routing']:
                routing = response['routing']
                print(f"   Recommended Agent: {routing.get('recommended_agent_name', 'N/A')}")
                print(f"   Confidence: {routing.get('confidence_score', 0)*100:.1f}%")
        
        return success

    def test_auto_assign_case(self):
        """Test POST /api/routing/auto-assign/{case_id}"""
        if not self.case_ids:
            print("⚠️  No case IDs available for auto-assignment test")
            return False
        
        case_id = self.case_ids[0]
        success, response = self.run_test(
            f"Auto-Assign Case ({case_id[:8]}...)",
            "POST",
            f"routing/auto-assign/{case_id}",
            200
        )
        
        if success:
            print(f"   Assigned to: {response.get('agent_name', 'Unknown')}")
            print(f"   Message: {response.get('message', 'N/A')}")
        
        return success

def main():
    print("🚀 Starting Smart Routing API Tests...")
    print("=" * 60)
    
    tester = SmartRoutingAPITester()
    
    # Test login as admin
    print("\n📋 AUTHENTICATION TESTS")
    admin_token = tester.test_login("admin2@omnimine.com", "admin123")
    if not admin_token:
        print("❌ Admin login failed, stopping tests")
        return 1
    
    tester.admin_token = admin_token
    tester.token = admin_token  # Use admin for all tests
    
    # Test agent authentication 
    agent_token = tester.test_login("agent1@omnimine.com", "admin123")  # Assuming same password
    if agent_token:
        print("✅ Agent login successful")
    
    print("\n📋 AGENT MANAGEMENT TESTS")
    
    # Test agent profiles API
    if not tester.test_get_agent_profiles():
        print("❌ Agent profiles test failed")
    
    # Test agent skills API
    if not tester.test_get_agent_skills():
        print("❌ Agent skills test failed")
    
    # Test update agent profile API
    if not tester.test_update_agent_profile():
        print("❌ Update agent profile test failed")
    
    print("\n📋 SMART ROUTING TESTS")
    
    # Create demo case for routing tests
    if not tester.test_create_demo_case():
        print("❌ Demo case creation failed, skipping routing tests")
    else:
        # Test smart routing analysis
        if not tester.test_smart_routing_analysis():
            print("❌ Smart routing analysis test failed")
        
        # Test auto-assignment
        if not tester.test_auto_assign_case():
            print("❌ Auto-assignment test failed")
    
    # Print final results
    print("\n" + "=" * 60)
    print(f"📊 FINAL RESULTS")
    print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
    success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
    print(f"Success rate: {success_rate:.1f}%")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Check the logs above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
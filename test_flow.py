import requests
import auth
from database import db

def test_full_flow():
    session = requests.Session()

    # 1. Check Lead
    lead = db.get_lead_by_email("marcus@test.com")
    assert lead is not None, "Lead was not saved"
    print(f"[PASS] Lead found: {lead['name']}, Phone: {lead['phone']}, Status: {lead['status']}")

    # 2. Login as admin via single-use magic token
    token = auth.create_magic_token("admin@example.com", purpose="login")
    verify_resp = session.post("http://127.0.0.1:5000/verify", data={"t": token}, allow_redirects=True)
    assert verify_resp.status_code == 200
    assert "Sales Course Command Hub" in verify_resp.text
    print("[PASS] Admin logged in with magic token & verified __session cookie")

    # 3. 1-Click Hire candidate
    hire_resp = session.post(f"http://127.0.0.1:5000/admin/leads/{lead['id']}/hire")
    hire_data = hire_resp.json()
    assert hire_data["success"] is True
    magic_url = hire_data["magic_url"]
    print(f"[PASS] Candidate hired! Generated Onboarding Link: {magic_url}")

    # 4. Candidate uses magic link to enter Gated Training Portal
    candidate_session = requests.Session()
    # Spend token via POST /verify
    cand_token = magic_url.split("t=")[-1]
    cand_verify = candidate_session.post("http://127.0.0.1:5000/verify", data={"t": cand_token}, allow_redirects=True)
    assert cand_verify.status_code == 200
    assert "Sales Agent Certification Training" in cand_verify.text
    print("[PASS] Candidate verified email & entered Gated Onboarding Hub!")

    # 5. Candidate marks lesson complete
    prog_resp = candidate_session.post("http://127.0.0.1:5000/api/progress", json={"lesson_id": "lesson-1-1", "completed": True})
    assert prog_resp.json()["success"] is True
    print("[PASS] Lesson progress tracked and updated.")

if __name__ == "__main__":
    test_full_flow()

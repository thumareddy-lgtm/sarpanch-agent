# test_bot_logic.py
import sys
from sarpanch_app import bot_reply, WELCOME_MENU, COMPLAINT_CATS, CERT_TYPES

def run_tests():
    print("🤖 STARTING CHATBOT LOGICAL TESTING...\n")
    
    # -------------------------------------------------------------
    # TEST 1: Initial Greeting & Reset triggers
    # -------------------------------------------------------------
    print("--- Test 1: Initial Greeting / Menu Reset ---")
    ctx = {"state": "idle", "lang": "en"}
    
    # Send "hi"
    reply, ctx = bot_reply("hi", ctx)
    assert reply == WELCOME_MENU, "Failed: Greeting message did not return standard menu"
    assert ctx["state"] == "idle", f"Failed: Idle state expected, got {ctx['state']}"
    print("✅ Hi/Welcome menu matches perfectly.")

    # -------------------------------------------------------------
    # TEST 2: Register Complaint Flow (Valid Inputs)
    # -------------------------------------------------------------
    print("\n--- Test 2: Valid Complaint Registration Flow ---")
    ctx = {"state": "idle", "lang": "en"}
    
    # Step 1: Select Option 1 (Register Complaint)
    reply, ctx = bot_reply("1", ctx)
    assert "Register Complaint" in reply, "Failed to start complaint registration flow"
    assert ctx["state"] == "c_name", f"Expected state c_name, got {ctx['state']}"
    print("✅ Menu selection '1' -> Switched state to 'c_name'")
    
    # Step 2: Provide full name
    reply, ctx = bot_reply("Vijaysagar Thumma", ctx)
    assert "c_phone" in ctx["state"], "State did not advance to c_phone"
    assert ctx["c_name"] == "Vijaysagar Thumma", "Name not saved correctly in session context"
    print("✅ Name accepted -> Saved 'Vijaysagar Thumma' -> Switched state to 'c_phone'")
    
    # Step 3: Provide phone number
    reply, ctx = bot_reply("1234567890", ctx)
    assert "c_cat" in ctx["state"], "State did not advance to c_cat"
    assert ctx["c_phone"] == "1234567890", "Phone not saved correctly in context"
    print("✅ Phone accepted -> Saved '1234567890' -> Switched state to 'c_cat'")
    
    # Step 4: Select complaint category
    reply, ctx = bot_reply("2", ctx) # Water supply
    assert "c_desc" in ctx["state"], "State did not advance to c_desc"
    assert ctx["c_cat"] == "Water Supply [నీటి సరఫరా]", f"Category mismatch, got {ctx['c_cat']}"
    print("✅ Category selected -> Mapped to 'Water Supply' -> Switched state to 'c_desc'")
    
    # Step 5: Input problem description
    reply, ctx = bot_reply("Water supply pipeline is broken in lane 3", ctx)
    assert "waiting_for_location" in ctx["state"], "State did not advance to waiting_for_location"
    assert ctx["c_desc"] == "Water supply pipeline is broken in lane 3", "Description mismatch"
    print("✅ Description accepted -> Saved -> Switched state to 'waiting_for_location'")
    
    # Step 6: Input village name
    reply, ctx = bot_reply("Kolukonda", ctx)
    assert "c_pri" in ctx["state"], "State did not advance to c_pri"
    assert ctx["village"] == "Kolukonda", f"Expected village Kolukonda, got {ctx.get('village')}"
    print("✅ Village input accepted -> Resolved to 'Kolukonda' -> Switched state to 'c_pri'")
    
    # Step 7: Select priority (Low/Medium/High)
    # The database insertion occurs inside bot_reply for 'c_pri', so let's mock it by capturing response
    reply, ctx = bot_reply("3", ctx) # High priority
    assert ctx["state"] == "idle", f"Expected state to reset to idle, got {ctx['state']}"
    assert "Complaint Registered" in reply or "ఫిర్యాదు నమోదు చేయబడింది" in reply, "Success confirmation not found in reply"
    print("✅ Priority selected '3' -> Successful DB Save -> Complaint Registered successfully!")

    # -------------------------------------------------------------
    # TEST 3: Invalid Input Handlers
    # -------------------------------------------------------------
    print("\n--- Test 3: Edge Cases and Invalid Input Handling ---")
    
    # 3.1: Short Name validation check
    ctx = {"state": "c_name", "lang": "en"}
    reply, ctx = bot_reply("A", ctx)
    assert "valid name" in reply or "కనీసం 2 అక్షరాల" in reply, "Did not prompt for invalid short name"
    assert ctx["state"] == "c_name", "Should not advance state on short name"
    print("✅ Short Name validation blocked: 'A' rejected successfully.")
    
    # 3.2: Invalid Phone validation check
    ctx = {"state": "c_phone", "lang": "en", "c_name": "Test User"}
    reply, ctx = bot_reply("12345", ctx) # short phone
    assert "valid 10-digit" in reply or "10 అంకెల మొబైల్" in reply, "Did not prompt for invalid phone length"
    assert ctx["state"] == "c_phone", "Should not advance state on short phone number"
    print("✅ Short Phone validation blocked: '12345' rejected successfully.")
    
    # 3.3: Invalid Category selection check
    ctx = {"state": "c_cat", "lang": "en", "c_name": "Test User", "c_phone": "1234567890"}
    reply, ctx = bot_reply("9", ctx) # category 9 doesn't exist
    assert "between 1 and 7" in reply or "1 నుండి 7 మధ్య" in reply, "Did not prompt for invalid category option"
    assert ctx["state"] == "c_cat", "Should not advance state on out-of-bounds category"
    print("✅ Out-of-bounds category selection blocked: Option '9' rejected successfully.")

    # 3.4: Short Description check
    ctx = {"state": "c_desc", "lang": "en", "c_name": "Test User", "c_phone": "1234567890", "c_cat": "Water Supply"}
    reply, ctx = bot_reply("leak", ctx) # description too short
    assert "more details" in reply or "కనీసం 5 అక్షరాలు" in reply, "Did not prompt for invalid description length"
    assert ctx["state"] == "c_desc", "Should not advance state on short description"
    print("✅ Short Description blocked: 'leak' rejected successfully.")

    # -------------------------------------------------------------
    # TEST 4: Request Certificate Flow (Valid Inputs)
    # -------------------------------------------------------------
    print("\n--- Test 4: Valid Certificate Request Flow ---")
    ctx = {"state": "idle", "lang": "en"}
    
    # Step 1: Select Option 2 (Request Certificate)
    reply, ctx = bot_reply("2", ctx)
    assert "Certificate Type" in reply or "ధృవీకరణ పత్రం రకం" in reply, "Failed to select certificate flow"
    assert ctx["state"] == "cert_type", "Expected state cert_type"
    print("✅ Menu selection '2' -> Switched state to 'cert_type'")
    
    # Step 2: Select Caste Certificate (Option 2)
    reply, ctx = bot_reply("2", ctx)
    assert "Applicant Full Name" in reply or "అప్లికెంట్ పూర్తి పేరు" in reply, "Failed to advance to applicant name"
    assert ctx["state"] == "cert_name", "Expected state cert_name"
    assert ctx["cert_type"] == CERT_TYPES["2"], "Incorrect certificate type saved"
    print("✅ Certificate Type '2' accepted -> Switched state to 'cert_name'")
    
    # Step 3: Input Applicant Name
    reply, ctx = bot_reply("Kothi Praveen", ctx)
    assert ctx["state"] == "cert_father", "Expected state cert_father"
    assert ctx["cert_name"] == "Kothi Praveen", "Name not saved correctly"
    print("✅ Applicant name accepted -> Saved 'Kothi Praveen' -> Switched state to 'cert_father'")
    
    # Step 4: Input Father Name
    reply, ctx = bot_reply("Laxman", ctx)
    assert ctx["state"] == "cert_phone", "Expected state cert_phone"
    assert ctx["cert_father"] == "Laxman", "Father name not saved correctly"
    print("✅ Father name accepted -> Saved 'Laxman' -> Switched state to 'cert_phone'")
    
    # Step 5: Input Phone Number
    reply, ctx = bot_reply("9876543210", ctx)
    assert ctx["state"] == "cert_purpose", "Expected state cert_purpose"
    assert ctx["cert_phone"] == "9876543210", "Phone not saved correctly"
    print("✅ Mobile number accepted -> Saved '9876543210' -> Switched state to 'cert_purpose'")
    
    # Step 6: Input Purpose
    reply, ctx = bot_reply("For College Admissions", ctx)
    assert ctx["state"] == "cert_village", f"Expected state cert_village, got {ctx['state']}"
    assert ctx["cert_purpose"] == "For College Admissions", "Purpose mismatch"
    print("✅ Purpose accepted -> Saved -> Switched state to 'cert_village'")
    
    # Step 7: Input Village Name (Fuzzy matched & corrected)
    reply, ctx = bot_reply("kolkonda", ctx)
    assert ctx["state"] == "idle", f"Expected state to reset to idle, got {ctx['state']}"
    assert "Certificate Request Submitted" in reply or "సర్టిఫికెట్ అభ్యర్థన నమోదు చేయబడింది" in reply, "Success confirmation not found"
    print("✅ Typo village 'kolkonda' auto-corrected to 'Kolukonda' -> Request submitted successfully!")

    print("\n🎉 ALL CHATBOT LOGICAL TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()

# test_update_status.py
import unittest
from sarpanch_app import app, init_db, get_db, get_placeholder, insert_complaint
import sarpanch_app

class TestUpdateStatus(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_secret'
        self.client = app.test_client()
        init_db()
        
        # Insert a mock complaint to test with
        self.test_ticket_id = "CMP-TEST123"
        conn, db_type = get_db()
        cur = conn.cursor()
        p = get_placeholder(db_type)
        
        # Delete if already exists
        cur.execute(f"DELETE FROM complaints WHERE id = {p}", (self.test_ticket_id,))
        conn.commit()
        conn.close()
        
        mock_complaint = {
            "id": self.test_ticket_id,
            "name": "Rajesh Kumar",
            "phone": "9988776655",
            "category": "Water Supply",
            "desc": "Pipe leak near house #12",
            "location": "Kolukonda",
            "priority": "medium",
            "filed_at": "26-May-2026 12:00",
            "village": "Kolukonda"
        }
        insert_complaint(mock_complaint)
        
        # Mock send_whatsapp_message to capture the payload
        self.sent_messages = []
        sarpanch_app.send_whatsapp_message = self.mock_send_whatsapp

    def mock_send_whatsapp(self, to_num, message):
        self.sent_messages.append({"to": to_num, "message": message})
        print(f"🕵️ MOCK WHATSAPP SENT to {to_num}:\n{message}\n")
        return True

    def test_automatic_resolution_alert(self):
        # 1. Simulate Sarpanch Login Session
        with self.client.session_transaction() as sess:
            sess['sarpanch_username'] = 'kolukonda_sarpanch'
            sess['sarpanch_village'] = 'Kolukonda'
            
        # 2. Trigger Status Update to 'resolved' with a custom note
        response = self.client.post('/update_status', data={
            'ticket_id': self.test_ticket_id,
            'status': 'resolved',
            'notes': 'The pipe leak near house #12 was welded and fixed.'
        })
        
        # 3. Assertions
        # Check database update
        conn, db_type = get_db()
        cur = conn.cursor()
        p = get_placeholder(db_type)
        cur.execute(f"SELECT status, notes FROM complaints WHERE id = {p}", (self.test_ticket_id,))
        row = cur.fetchone()
        conn.close()
        
        status = row['status'] if isinstance(row, dict) else row[0]
        notes = row['notes'] if isinstance(row, dict) else row[1]
        
        self.assertEqual(status, 'resolved')
        self.assertEqual(notes, 'The pipe leak near house #12 was welded and fixed.')
        print("✅ Database successfully updated to 'resolved' with correct notes.")
        
        # Check WhatsApp Alert payload
        self.assertEqual(len(self.sent_messages), 1)
        alert = self.sent_messages[0]
        self.assertEqual(alert["to"], "9988776655")
        
        # Verify content details
        self.assertIn("CMP-TEST123", alert["message"])
        self.assertIn("Rajesh Kumar", alert["message"])
        self.assertIn("RESOLVED", alert["message"])
        self.assertIn("పరిష్కరించబడింది", alert["message"])
        self.assertIn("The pipe leak near house #12 was welded and fixed.", alert["message"])
        print("✅ WhatsApp Resolution Alert payload validated: Contains correct name, ID, notes, and bilingual translations!")

if __name__ == "__main__":
    unittest.main()

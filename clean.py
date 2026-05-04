import sqlite3
c = sqlite3.connect('ui_state.db')
c.execute('DELETE FROM audit_log')
c.execute("DELETE FROM opportunities WHERE id LIKE 't3_mock_%'")
c.commit()
print('cleaned')

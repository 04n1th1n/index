import sys
import os
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import main
from main import HotelManager

# Monkeypatch DATA_FILE to use scratch/temp_data.json
TEMP_DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), "temp_data.json"))
main.DATA_FILE = TEMP_DATA

# The default value for 'path' in _load is set at definition time.
# We need to monkeypatch the method to use our TEMP_DATA.
original_load = HotelManager._load
def patched_load(self, path=None):
    if path is None:
        path = main.DATA_FILE
    return original_load(self, path)
HotelManager._load = patched_load

def test_persistence():
    print("Starting persistence test...")

    # 1. Clean start
    if os.path.exists(TEMP_DATA):
        os.remove(TEMP_DATA)

    # 2. First instance: Check-in
    # This will call _load(), fail (because TEMP_DATA doesn't exist),
    # then call _generate_departments() and _save().
    mgr = HotelManager()

    # Verify it's using the right file
    if not os.path.exists(TEMP_DATA):
        print("FAIL: temp_data.json was not created by HotelManager init")
        sys.exit(1)

    room = mgr.find_by_number("101")
    if not room:
        print("FAIL: Room 101 not found")
        sys.exit(1)

    # In fresh generation, 101 is available.
    if room.status != "available":
        print(f"FAIL: Room 101 status should be available, found {room.status}")
        sys.exit(1)

    guest_name = "Test Pipeline Guest"
    mgr.check_in(room, guest_name, "2026-08-02", "2026-08-05")
    mgr._save()
    print(f"Check-in successful for {guest_name} in Room 101.")

    # 3. Second instance: Verify
    mgr2 = HotelManager()
    room2 = mgr2.find_by_number("101")

    if room2.guest == guest_name and room2.status == "occupied":
        print("SUCCESS: Data persisted correctly.")
    else:
        print(f"FAIL: Data mismatch. Found guest: {room2.guest}, status: {room2.status}")
        sys.exit(1)

if __name__ == "__main__":
    test_persistence()

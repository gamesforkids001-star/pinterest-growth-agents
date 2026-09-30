"""Pinterest Manager: board mapping check + saving own pins into their ONE matching tool board (API save; fallback = fresh pin)."""
from src.integrations.pinterest import PinterestError

def board_for(settings, slug): return (settings["pinterest"]["boards"].get("tools") or {}).get(slug)

def do_save(db, client, settings, pin, method):
    """Returns (ok, method_used, note)."""
    board = board_for(settings, pin["tool_slug"])
    if not board: return False, method, f"no board mapped for {pin['tool_slug']}"
    try:
        client.save_pin(pin["pinterest_id"], board)
        db.add_save(pin["id"], pin["tool_slug"], board, "save", True); return True, "save", ""
    except PinterestError as e:
        if e.status in (400, 403, 404, 405, 422): return False, "unsupported", str(e)
        raise

def manual_save_tasks(db, settings, pins):
    n = 0
    for p in pins:
        b = board_for(settings, p["tool_slug"])
        if b:
            db.add_task(f"Apni pin '{p['title'][:50]}' ko tool board mein save karo (board id {b}): pin ka link: https://www.pinterest.com/pin/{p['pinterest_id']}/"); n += 1
    return n

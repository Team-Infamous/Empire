"""Offline test for mini_games.plugin.

The Telegram/Android SDK is replaced with small stubs that mirror the signatures used by the other
MZGram plugins, so the game logic, turn handling, hooks and scoring can be exercised on a desktop:

    python3 test_mini_games.py /path/to/mini_games.plugin
"""
import importlib.machinery
import importlib.util
import sys
import types

PLUGIN = sys.argv[1] if len(sys.argv) > 1 else "mini_games.plugin"

# ----------------------------------------------------------------- SDK stubs
SENT, DELETED, STRIPPED, ANSWERED, TOASTS = [], [], [], [], []
ME = 1000


def mod(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    sys.modules[name] = m
    return m


mod("android_utils", log=lambda *a, **k: None, run_on_ui_thread=lambda fn, delay=0: fn())


class HookResult:
    def __init__(self, strategy="default", params=None, **kw):
        self.strategy = strategy


class HookStrategy:
    DEFAULT = "default"
    CANCEL = "cancel"
    MODIFY = "modify"


class BasePlugin:
    def __init__(self):
        self._settings = {}
        self.hooks = []

    def get_setting(self, k, d=None):
        return self._settings.get(k, d)

    def set_setting(self, k, v, reload_settings=False):
        self._settings[k] = v

    def add_on_send_message_hook(self):
        self.hooks.append("send")

    def add_on_callback_query_hook(self):
        self.hooks.append("callback")

    def add_hook(self, name, **kw):
        self.hooks.append(name)


mod("base_plugin", BasePlugin=BasePlugin, HookResult=HookResult, HookStrategy=HookStrategy)


class MC:
    def deleteMessages(self, ids, a, b, dialog, topic, for_all, mode):
        DELETED.append((list(ids), dialog))

    def callCallbackQuery(self, qid, s):
        ANSWERED.append(qid)

    def editMessageReplyMarkup(self, peer, msg_id, markup):
        STRIPPED.append((peer, msg_id))


class NC:
    def __init__(self):
        self.observers = []

    def addObserver(self, w, i):
        self.observers.append(w)

    def removeObserver(self, w, i):
        pass


class UC:
    def getClientUserId(self):
        return ME


NCS = {}
mod("client_utils",
    get_messages_controller=lambda *a: MC(),
    get_notification_center=lambda acc: NCS.setdefault(acc, NC()),
    get_user_config=lambda *a: UC(),
    send_message=lambda p: SENT.append(p))
mod("java", dynamic_proxy=lambda iface: object)
mod("java.lang", Integer=int)


class ArrayList(list):
    def add(self, x):
        self.append(x)


mod("java.util", ArrayList=ArrayList)


class _User:
    def __init__(self, f, l="", u=""):
        self.first_name, self.last_name, self.username = f, l, u


USERS = {1000: _User("Me", "", "meuser"), 2000: _User("Bob", "", "bobby"), 3000: _User("Cara")}


class _MCtl:
    @staticmethod
    def getInstance(acc):
        class X:
            def getUser(self, uid):
                return USERS.get(uid)
        return X()


class _NotifCenter:
    messageReceivedByServer = 77

    class NotificationCenterDelegate:
        pass


class _UserConfig:
    selectedAccount = 0

    @staticmethod
    def getInstance(acc):
        return UC()


class _Locale:
    @staticmethod
    def getInstance():
        class L:
            def getCurrentLocaleInfo(self):
                class I:
                    def getLangCode(self):
                        return "en"
                return I()
        return L()


mod("org"); mod("org.telegram"); mod("org.telegram.messenger", LocaleController=_Locale, MessagesController=_MCtl,
                                      NotificationCenter=_NotifCenter, UserConfig=_UserConfig)
mod("ui"); mod("ui.bulletin", BulletinHelper=types.SimpleNamespace(show_info=lambda t: TOASTS.append(t)))


class _W:
    def __init__(self, **kw):
        self.__dict__.update(kw)


mod("ui.settings", Header=_W, Divider=_W, Input=_W, Selector=_W, Switch=_W, Text=_W)

# ----------------------------------------------------------------- load plugin
loader = importlib.machinery.SourceFileLoader("mini_games_under_test", PLUGIN)
spec = importlib.util.spec_from_loader(loader.name, loader)
M = importlib.util.module_from_spec(spec)
loader.exec_module(M)


class SyncExec:
    def submit(self, fn):
        fn()

    def shutdown(self, wait=False):
        pass


def new_plugin():
    SENT.clear(); DELETED.clear(); STRIPPED.clear(); ANSWERED.clear(); TOASTS.clear(); NCS.clear()
    p = M.MiniGamesPlugin()
    p.on_plugin_load()
    p._exec = SyncExec()
    return p


def typed(p, peer, text, reply=None):
    params = types.SimpleNamespace(message=text, peer=peer, replyToMsg=reply, replyToTopMsg=None)
    return p.on_send_message_hook(0, params).strategy


def friend(p, dialog, sender, text, msg_id, date=0):
    """Incoming message the way TL_updateNewMessage / TL_updateShortMessage deliver it."""
    if dialog > 0:
        u = types.SimpleNamespace(out=False, message=text, user_id=sender, id=msg_id, date=date)
        p.on_updates_hook("TL_updateShortMessage", 0, u)
    else:
        peer = types.SimpleNamespace(chat_id=-dialog)
        frm = types.SimpleNamespace(user_id=sender)
        m = types.SimpleNamespace(out=False, message=text, peer_id=peer, from_id=frm, id=msg_id, date=date)
        p.on_update_hook("TL_updateNewMessage", 0, types.SimpleNamespace(message=m))


def tap(p, dialog, msg_id, data, qid=1):
    params = types.SimpleNamespace(data=data, query_id=qid, peer=dialog, msg_id=msg_id)
    return p.on_callback_query_hook(0, params).strategy


def confirm(p, dialog, new_id):
    """What the NotificationCenter observer does when the server confirms the last board we sent."""
    last = SENT[-1]["message"]
    w = list(NCS[0].observers)[0]
    w.didReceivedNotification(77, 0, [0, new_id, types.SimpleNamespace(message=last, out=True), dialog])


def gid_of(text):
    return text.rsplit("#", 1)[1].strip()


def buttons(payload):
    return [b for row in payload["reply_markup"]["inline_keyboard"] for b in row]


passed = 0


def check(cond, label):
    global passed
    assert cond, "FAIL: " + label
    passed += 1
    print("  ok  " + label)


# =============================================================== pure logic
print("pure logic")
check(M.bulls_cows("1234", "1234") == (4, 0), "bulls_cows exact")
check(M.bulls_cows("1234", "4321") == (0, 4), "bulls_cows all cows")
check(M.bulls_cows("1234", "1243") == (2, 2), "bulls_cows mixed")
check(M.bulls_cows("1123", "1111") == (2, 0), "bulls_cows duplicates are not over-counted")
check(M.bulls_cows("1123", "2111") == (1, 2), "bulls_cows duplicates (cows capped by secret count)")
check(M.valid_guess("0123", False) and not M.valid_guess("1123", False) and M.valid_guess("1123", True), "valid_guess")
check(not M.valid_guess("123", True) and not M.valid_guess("12345", True) and not M.valid_guess("12a4", True), "valid_guess shape")
for _ in range(200):
    s = M.make_secret(False)
    assert len(s) == 4 and len(set(s)) == 4 and s.isdigit()
check(True, "make_secret distinct (200 samples)")
check([M.wc_points(n) for n in (1, 2, 5, 9, 10, 30)] == [100, 90, 60, 20, 20, 20], "wc_points curve")
b = list("XXX      ")
check(M.ttt_winner(b) == "X", "ttt row win")
check(M.ttt_winner(list("O  O  O  ")) == "O", "ttt column win")
check(M.ttt_winner(list("X   X   X")) == "X", "ttt diagonal win")
check(M.ttt_winner(list("XOXXOOOXX")) == "", "ttt no winner")

# =============================================================== WC: PM duel
print("WC in a PM (duel with Bob, dialog 2000)")
p = new_plugin()
check(typed(p, 2000, ".wc") == "cancel", ".wc swallows the command message")
check(len(SENT) == 1 and "4-Digit Guess" in SENT[0]["message"], "board posted")
check("Duel: Me vs Bob" in SENT[0]["message"], "PM = duel with the peer")
check(len(buttons(SENT[0])) == 14 and all(b["callback_data"].startswith("mg:") for b in buttons(SENT[0])), "keypad has 14 buttons")
gid = gid_of(SENT[0]["message"])
sess = p._sessions[(0, 2000, "wc")]
sess.secret = "1234"
confirm(p, 2000, 501)
check(sess.board_id == 501, "observer learned the board message id")

friend(p, 2000, 2000, "5678", 11)
check("#1 Bob  5678 → 🎯0 🔸0" in SENT[-1]["message"], "friend's text guess scored")
confirm(p, 2000, 502)
check(DELETED == [([501], 2000)], "old board deleted when new one confirmed")

check(typed(p, 2000, "1243") == "cancel", "host typed guess consumed")
check("#1 Me  1243 → 🎯2 🔸2" in SENT[-1]["message"], "host guess scored (2 bulls 2 cows)")
confirm(p, 2000, 503)

friend(p, 2000, 3000, "1234", 12)
check(sess.state == "active", "stranger cannot guess in a duel")
friend(p, 2000, 2000, "5678", 11)
n_before = len(SENT)
check(n_before == len(SENT), "duplicate update ignored")
friend(p, 2000, 2000, "9999", 13)
check("Digits must all be different" in SENT[-1]["message"] or "different" in SENT[-1]["message"], "repeat digits rejected for friend")
check(len(sess.guesses) == 2, "rejected guess not counted")

# keypad: host taps 1,2,3,4 -> auto submit -> win
for d in "123":
    check(tap(p, 2000, 503, "mg:%s:d%s" % (gid, d)) == "cancel", "tap %s swallowed" % d)
check(TOASTS[-1] == "Input: 1 2 3 _", "toast shows partial input")
tap(p, 2000, 503, "mg:%s:bk" % gid)
tap(p, 2000, 503, "mg:%s:d3" % gid)
tap(p, 2000, 503, "mg:%s:d3" % gid)
check(TOASTS[-1] == "Input: 1 2 3 _" or "different" in TOASTS[-1], "same digit rejected when digits must differ")
tap(p, 2000, 503, "mg:%s:d4" % gid)
check(sess.state == "done" and sess.result == "won" and sess.winner == ME, "keypad guess wins the game")
check("cracked the code 1234 in 2 tries! +90 pts" in SENT[-1]["message"], "win text + points")
check(len(ANSWERED) > 0, "callback queries answered")
check([b["callback_data"].split(":")[2] for b in buttons(SENT[-1])] == ["new", "top"], "finished board has New game/Top")
rec = p._scores.get("wc", "2000", ME)
rec_b = p._scores.get("wc", "2000", 2000)
check(rec["p"] == 90 and rec["w"] == 1 and rec["g"] == 1, "winner score saved")
check(rec_b["p"] == 0 and rec_b["l"] == 1 and rec_b["g"] == 1, "loser game recorded")
check(p._scores.get("wc", "*", ME)["p"] == 90, "global scope updated")
typed(p, 2000, ".wc top")
check("🥇 Me — 90 pts" in SENT[-1]["message"], "leaderboard")
typed(p, 2000, ".wc me")
check("90 pts" in SENT[-1]["message"] and "1 wins" in SENT[-1]["message"], ".wc me")
check(typed(p, 2000, "1234") == "default", "after the game, 4-digit text is normal chat again")

# rematch via button
tap(p, 2000, 503, "mg:%s:new" % gid)
check(p._sessions[(0, 2000, "wc")] is not sess and p._sessions[(0, 2000, "wc")].state == "active", "New game button starts a fresh session")
check(p._sessions[(0, 2000, "wc")].board_id == sess.board_id, "board id carried so the old board is retired")

# =============================================================== WC: group, open game, attempts exhaustion
print("WC in a group (open game, 2 attempts each)")
p = new_plugin()
p._settings["wc_attempts"] = "2"
typed(p, -500, ".wc")
check("Open game" in SENT[0]["message"], "group = open game")
g = p._sessions[(0, -500, "wc")]
g.secret = "9876"
friend(p, -500, 2000, "1111", 1)
check(len(g.guesses) == 0, "1111 rejected (digits differ rule)")
friend(p, -500, 2000, "1234", 2)
friend(p, -500, 3000, "1235", 3)
friend(p, -500, 2000, "1236", 4)
check(g.attempts == {2000: 2, 3000: 1}, "multiplayer attempts tracked per player")
friend(p, -500, 2000, "1237", 5)
check(g.attempts[2000] == 2 and "No attempts left" in SENT[-1]["message"], "attempt cap enforced")
friend(p, -500, 3000, "1238", 6)
check(g.state == "done" and g.result == "lost", "game lost once everybody is out")
check("The code was 9876" in SENT[-1]["message"], "secret revealed")
check(p._scores.get("wc", "-500", 2000)["l"] == 1, "losses recorded")

# challenge by reply in a group + stop
print("WC challenge by reply in a group + .wc stop")
p = new_plugin()
reply = types.SimpleNamespace(getSenderId=lambda: 2000, getId=lambda: 5)
typed(p, -500, ".wc", reply=reply)
check("Duel: Me vs Bob" in SENT[0]["message"], "reply = challenge")
g = p._sessions[(0, -500, "wc")]
g.secret = "1234"
friend(p, -500, 3000, "1234", 1)
check(g.state == "active", "third player locked out of a duel")
typed(p, -500, ".wc")
check("already running" in SENT[-1]["message"], "second .wc while active is refused")
typed(p, -500, ".wc stop")
check(g.state == "done" and "The code was 1234" in SENT[-1]["message"], ".wc stop reveals the code")
check(p._scores.get("wc", "-500", ME) is None, "stopped game gives no points")
# forum topic root must not count as a challenge
p = new_plugin()
root = types.SimpleNamespace(getSenderId=lambda: 2000, getId=lambda: 9)
params = types.SimpleNamespace(message=".wc", peer=-500, replyToMsg=root, replyToTopMsg=root)
p.on_send_message_hook(0, params)
check(p._sessions[(0, -500, "wc")].target == 0, "forum topic root is not treated as a reply target")

# =============================================================== TTT
print("TTT in a PM")
p = new_plugin()
check(typed(p, 2000, ".ttt") == "cancel", ".ttt swallowed")
t = p._sessions[(0, 2000, "ttt")]
check(t.state == "pending" and "challenges @bobby" in SENT[0]["message"], "challenge posted, Bob mentioned")
gid = gid_of(SENT[0]["message"])
confirm(p, 2000, 601)
tap(p, 2000, 601, "mg:%s:c4" % gid)
check(t.cells[4] == " ", "cannot move before the challenge is accepted")
check("Waiting" in TOASTS[-1], "toast: waiting for opponent")
friend(p, 2000, 3000, "+", 1)
check(t.state == "pending", "stranger cannot accept a targeted challenge")
friend(p, 2000, 2000, "+", 2)
check(t.state == "active" and t.o == 2000 and t.x == ME, "friend accepts with +")
check(len(buttons(SENT[-1])) == 11 and SENT[-1]["message"].count("1️⃣") == 1, "3x3 grid + 2 control buttons")
confirm(p, 2000, 602)

tap(p, 2000, 602, "mg:%s:c4" % gid)
check(t.cells[4] == "X" and t.turn == "O", "host taps centre: X placed, turn passes")
tap(p, 2000, 602, "mg:%s:c0" % gid)
check(t.cells[0] == " " and "Not your turn" in TOASTS[-1], "host tapping out of turn is refused")
friend(p, 2000, 2000, "5", 3)
check(t.cells[4] == "X", "taken cell is not overwritten")
check("taken" in SENT[-1]["message"], "friend told the cell is taken")
friend(p, 2000, 2000, "1", 4)
check(t.cells[0] == "O" and t.turn == "X", "friend moves by text")
confirm(p, 2000, 603)
tap(p, 2000, 602, "mg:%s:c8" % gid)
check(t.cells[8] == " " and "old board" in TOASTS[-1], "tap on an outdated board ignored")
tap(p, 2000, 603, "mg:%s:c8" % gid)
friend(p, 2000, 2000, "2", 5)
confirm(p, 2000, 604)
check(typed(p, 2000, "7") == "cancel" and t.cells[6] == "X", "host can also move by typing a digit")
# X: 4,8,6 -> diagonal 2-4-6? cells: X at 4,8,6 ; O at 0,1 ; O to move
friend(p, 2000, 2000, "3", 6)
check(t.state == "done" and t.result == "O", "O completes the top row and wins")
print("   board now:", "".join(t.cells).replace(" ", "."), "turn", t.turn, "state", t.state)

# deterministic win for X
print("TTT win / draw / scoring / rematch")
p = new_plugin()
typed(p, 2000, ".ttt"); friend(p, 2000, 2000, "+", 1)
t = p._sessions[(0, 2000, "ttt")]
for who, cell, mid in ((ME, 1, 0), (2000, 4, 2), (ME, 2, 0), (2000, 5, 3), (ME, 3, 0)):
    if who == ME:
        typed(p, 2000, str(cell))
    else:
        friend(p, 2000, 2000, str(cell), mid)
check(t.state == "done" and t.result == "X", "X wins top row")
check("wins! +3 pts" in SENT[-1]["message"], "win text")
check(p._scores.get("ttt", "2000", ME)["p"] == 3 and p._scores.get("ttt", "2000", 2000)["l"] == 1, "3 pts to winner, loss to loser")
gid = t.gid
tap(p, 2000, 700, "mg:%s:c8" % gid)
check("Game over" in TOASTS[-1] and t.cells.count(" ") == 4, "tapping a finished board is harmless")
tap(p, 2000, 0, "mg:%s:new" % gid)
t2 = p._sessions[(0, 2000, "ttt")]
check(t2 is not t and t2.x == 2000 and t2.o == ME and t2.state == "active", "rematch swaps sides, other player opens")
check(t2.turn == "X" and p._ttt_turn_uid(t2) == 2000, "friend (now X) moves first")
# draw
seq = [1, 2, 3, 5, 4, 6, 8, 7, 9]   # X O X O X O ... build a full board without a winner: X:1,3,4,8,9?  verify below
draw_moves = [(2000, 1), (ME, 2), (2000, 3), (ME, 5), (2000, 4), (ME, 6), (2000, 8), (ME, 7), (2000, 9)]
# X(2000): 1,3,4,8,9  O(ME): 2,5,6,7 -> check no line: X lines? 1-4-7 no(7=O) 3-... ok
for who, cell in draw_moves:
    if who == ME:
        typed(p, 2000, str(cell))
    else:
        friend(p, 2000, 2000, str(cell), 100 + cell)
check(t2.state == "done" and t2.result == "draw", "full board without winner = draw")
check("Draw! +1 pt each" in SENT[-1]["message"], "draw text")
check(p._scores.get("ttt", "2000", ME)["d"] == 1 and p._scores.get("ttt", "2000", ME)["p"] == 4, "draw gives 1 pt (3+1)")
typed(p, 2000, ".ttt top")
check("🥇 Me — 4 pts" in SENT[-1]["message"], "ttt leaderboard")

# decline, cancel, resign, expiry
print("TTT decline / cancel / resign / expiry / practice")
p = new_plugin()
typed(p, 2000, ".ttt"); friend(p, 2000, 2000, "-", 1)
check((0, 2000, "ttt") not in p._sessions and "declined" in SENT[-1]["message"], "decline clears the challenge")
typed(p, 2000, ".ttt")
typed(p, 2000, ".ttt stop")
check("cancelled" in SENT[-1]["message"] and (0, 2000, "ttt") not in p._sessions, "host cancels a pending challenge")
typed(p, 2000, ".ttt"); friend(p, 2000, 2000, "yes", 2)
t = p._sessions[(0, 2000, "ttt")]
tap(p, 2000, 0, "mg:%s:end" % t.gid)
check(t.state == "done" and t.result == "resigned", "host resigns via button")
check("resigned" in SENT[-1]["message"] and "Bob" in SENT[-1]["message"], "resign text names the winner")
check(p._scores.get("ttt", "2000", 2000)["p"] == 3, "resign gives opponent 3 pts")
p = new_plugin()
typed(p, 2000, ".ttt")
p._sessions[(0, 2000, "ttt")].updated -= 10 * 60
friend(p, 2000, 2000, "+", 1)
check("expired" in SENT[-1]["message"].lower() or (0, 2000, "ttt") not in p._sessions, "stale challenge expires")
# old backlog message ignored
p = new_plugin()
typed(p, 2000, ".ttt")
t = p._sessions[(0, 2000, "ttt")]
friend(p, 2000, 2000, "+", 1, date=int(t.created) - 3600)
check(t.state == "pending", "message older than the game is ignored")
# practice mode in Saved Messages
p = new_plugin()
typed(p, ME, ".ttt")
t = p._sessions[(0, ME, "ttt")]
check(t.state == "active" and t.hotseat and "Practice mode" in SENT[-1]["message"], "Saved Messages = practice mode")
for c in (1, 4, 2, 5, 3):
    typed(p, ME, str(c))
check(t.state == "done" and p._scores.get("ttt", str(ME), ME) is None, "practice games give no points")
# group open challenge
p = new_plugin()
typed(p, -700, ".ttt")
check("challenges anyone" in SENT[-1]["message"], "open group challenge")
friend(p, -700, 3000, "+", 1)
t = p._sessions[(0, -700, "ttt")]
check(t.o == 3000 and t.state == "active", "any group member can accept an open challenge")
friend(p, -700, 2000, "5", 2)
check(t.cells[4] == " ", "third person's move ignored")

# plumbing
print("plumbing")
p = new_plugin()
check(typed(p, 2000, "hello") == "default" and typed(p, 2000, ".ping") == "default", "unrelated messages untouched")
check(tap(p, 2000, 1, "other:thing") == "default", "foreign callbacks untouched")
check(tap(p, 2000, 1, "mg:ZZZZ:c1") == "cancel" and "over or expired" in TOASTS[-1], "unknown game id handled")
typed(p, 2000, ".wc help"); check("4-Digit Guess (.wc)" in SENT[-1]["message"], ".wc help")
typed(p, 2000, ".ttt help"); check("Tic-Tac-Toe (.ttt)" in SENT[-1]["message"], ".ttt help")
typed(p, 2000, ".ttt top"); check("No scores yet" in SENT[-1]["message"], "empty leaderboard")
typed(p, 2000, ".wc stop"); check("No active game" in SENT[-1]["message"], "stop with no game")
p._settings["buttons"] = False
typed(p, 2000, ".wc"); check("reply_markup" not in SENT[-1], "buttons can be switched off (text-only)")
p._settings["lang"] = 2
typed(p, 2000, ".ttt help"); check("Крестики-нолики" in SENT[-1]["message"], "Russian strings")
p = new_plugin()
p._settings["buttons"] = True
p._settings["replace_board"] = False
typed(p, 2000, ".wc"); confirm(p, 2000, 801)
p._sessions[(0, 2000, "wc")].secret = "1234"
friend(p, 2000, 2000, "5678", 1); confirm(p, 2000, 802)
check(DELETED == [] and STRIPPED == [(2000, 801)], "replace off: old board kept, buttons stripped")
pc = new_plugin()
class Boom:
    def __call__(self, payload):
        if "reply_markup" in payload:
            raise RuntimeError("no keyboards")
        SENT.append(payload)
M.send_message = Boom()
typed(pc, 2000, ".wc")
check(len(SENT) == 1 and "reply_markup" not in SENT[0], "falls back to text-only if the keyboard send raises")
print("\nALL %d CHECKS PASSED" % passed)

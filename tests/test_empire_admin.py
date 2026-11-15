"""Offline test for empire_admin.plugin (SDK replaced by stubs).

    python3 test_empire_admin.py /path/to/empire_admin.plugin
"""
import importlib.machinery
import importlib.util
import json
import os
import re
import sys
import time
import types

PLUGIN = sys.argv[1] if len(sys.argv) > 1 else "empire_admin.plugin"
ME = 1000
SENT, REQS, DELETED, TOASTS, DOCS, HELPER = [], [], [], [], [], []
RESP = {"res": object(), "err": None, "queue": []}


def mod(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    sys.modules[name] = m
    return m


class Ns:
    def __init__(self, **kw):
        self.__dict__.update(kw)


mod("android_utils", log=lambda *a, **k: None, run_on_ui_thread=lambda fn, delay=0: fn())


class HookResult:
    def __init__(self, strategy="default", params=None, **kw):
        self.strategy = strategy


class HookStrategy:
    CANCEL = "cancel"
    DEFAULT = "default"


class BasePlugin:
    def __init__(self):
        self._s = {}

    def get_setting(self, k, d=None):
        return self._s.get(k, d)

    def set_setting(self, k, v, reload_settings=False):
        self._s[k] = v

    def add_on_send_message_hook(self):
        pass

    def add_hook(self, name, **kw):
        pass


mod("base_plugin", BasePlugin=BasePlugin, HookResult=HookResult, HookStrategy=HookStrategy)

CHATS = {}
USERS = {2000: Ns(id=2000, first_name="Bob", last_name="", username="bobby", premium=True, bot=False),
         3000: Ns(id=3000, first_name="Cara", last_name="K", username="", premium=False, bot=False),
         ME: Ns(id=ME, first_name="Me", last_name="", username="meuser", premium=False, bot=False)}


class MCtl:
    dialogs_dict = Ns(get=lambda k: Ns(top_message=0))

    def getChat(self, cid):
        return CHATS.get(cid)

    def getUser(self, uid):
        return USERS.get(uid)

    def getUserOrChat(self, name):
        for u in USERS.values():
            if u.username == name:
                return u
        return None

    def getInputPeer(self, i):
        return ("peer", i)

    def getInputChannel(self, i):
        return ("chan", i)

    def processUpdates(self, res, flag):
        pass

    def deleteMessages(self, ids, a, b, dialog, topic, all_, mode):
        DELETED.append((list(ids), dialog))

    def setParticipantBannedRole(self, *a):
        HELPER.append(a)

    def deleteParticipantFromChat(self, chat_id, peer):
        HELPER.append(("kick", chat_id, peer))


MC = MCtl()


def send_request(req, cb, account=None):
    REQS.append(req)
    if RESP["queue"]:
        res, err = RESP["queue"].pop(0)
    else:
        res, err = RESP["res"], RESP["err"]
    cb(res, err)


mod("client_utils", get_last_fragment=lambda: None, get_messages_controller=lambda *a: MC,
    get_user_config=lambda *a: Ns(getClientUserId=lambda: ME),
    send_message=lambda p: SENT.append(p),
    send_document=lambda peer, path, caption=None, account=None: DOCS.append((peer, path, caption)),
    send_request=send_request)
mod("java", jlong=lambda x: x)
mod("java.lang", Integer=int)


class AL(list):
    def add(self, x):
        self.append(x)


mod("java.util", ArrayList=AL)
LOADED_FILE = {"f": None}


class FakeFile:
    def __init__(self, path):
        self.p = path

    def exists(self):
        return os.path.exists(self.p)

    def length(self):
        return os.path.getsize(self.p)

    def getAbsolutePath(self):
        return self.p


mod("org"); mod("org.telegram")
mod("org.telegram.messenger",
    FileLoader=Ns(getInstance=lambda a: Ns(getPathToMessage=lambda o: LOADED_FILE["f"])),
    LocaleController=Ns(getInstance=lambda: Ns(getCurrentLocaleInfo=lambda: Ns(getLangCode=lambda: "en"))),
    MessagesController=Ns(getInstance=lambda a: MC, getInputChannel=lambda c: ("chan-static", 0)),
    UserConfig=Ns(selectedAccount=0, getInstance=lambda a: Ns(getClientUserId=lambda: ME)))


class _TL(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        cls = type(name, (), {"__init__": lambda self: None})
        setattr(self, name, cls)
        return cls


tl = _TL("tlrpc")
mod("org.telegram.tgnet", TLRPC=tl)
mod("ui"); mod("ui.bulletin", BulletinHelper=Ns(show_info=lambda t: TOASTS.append(t)))


class W:
    def __init__(self, **kw):
        self.__dict__.update(kw)


mod("ui.settings", Header=W, Divider=W, Input=W, Selector=W, Switch=W, Text=W)

loader = importlib.machinery.SourceFileLoader("empire_admin_under_test", PLUGIN)
spec = importlib.util.spec_from_loader(loader.name, loader)
M = importlib.util.module_from_spec(spec)
loader.exec_module(M)


class SyncExec:
    def submit(self, fn):
        fn()

    def shutdown(self, wait=False):
        pass


def new_plugin(admin=True, megagroup=True):
    for l in (SENT, REQS, DELETED, TOASTS, DOCS, HELPER):
        l.clear()
    RESP.update(res=object(), err=None, queue=[])
    CHATS.clear()
    rights = Ns(ban_users=admin, delete_messages=admin, pin_messages=admin, change_info=admin)
    for cid in (500, 600):
        CHATS[cid] = Ns(megagroup=megagroup, broadcast=False, creator=False, admin_rights=rights if admin else None)
    p = M.EmpireAdminPlugin()
    p.on_plugin_load()
    p._exec = SyncExec()
    p._later = lambda s, fn, *a: fn(*a)        # no real delay in tests
    return p


def reply_to(uid, mid=77, text="hello"):
    return Ns(getSenderId=lambda: uid, getId=lambda: mid,
              messageOwner=Ns(message=text, media=None, from_id=Ns(user_id=uid)))


def typed(p, peer, text, reply=None, top=None):
    params = Ns(message=text, peer=peer, replyToMsg=reply, replyToTopMsg=top)
    return p.on_send_message_hook(0, params).strategy


def incoming(p, dialog, sender, text, mid):
    peer = Ns(channel_id=-dialog)
    m = Ns(out=False, message=text, peer_id=peer, from_id=Ns(user_id=sender), id=mid, date=0)
    p.on_update_hook("TL_updateNewChannelMessage", 0, Ns(message=m))


def last_msg():
    return SENT[-1]["message"]


passed = 0


def check(cond, label):
    global passed
    assert cond, "FAIL: " + label
    passed += 1
    print("  ok  " + label)


# =============================================================== pure helpers
print("pure helpers")
D = M.parse_duration
check(D("30m") == 1800 and D("2h") == 7200 and D("1d12h") == 129600 and D("1w") == 604800, "parse_duration")
check(D("10s") is None and D("999d") is None and D("abc") is None and D("") is None and D("5") is None, "parse_duration rejects bad/out-of-range")
check(M.fmt_duration(90061) == "1d 1h 1m 1s" and M.fmt_duration(1800) == "30m", "fmt_duration")
check(M.split_first("  a  b c ") == ("a", "b c") and M.split_first("") == ("", ""), "split_first")
bad = M.sanitize_chat({"rules": "x" * 9999, "notes": {"ok": "t", "bad name!": "t", "e": ""},
                       "filters": {"hi": "yo", "": "no"}, "warn": {"limit": 99, "mode": "evil", "dur": 1},
                       "warns": {"123": [{"r": "a", "t": 5, "by": 1}, "junk"], "abc": []}})
check(len(bad["rules"]) == 4000 and list(bad["notes"]) == ["ok"] and list(bad["filters"]) == ["hi"], "sanitize notes/filters/rules")
check(bad["warn"] == {"limit": 20, "mode": "ban", "dur": 30} and list(bad["warns"]) == ["123"], "sanitize warn config + warns")
check(M.sanitize_chat("nope") is None, "sanitize rejects non-dict")

# =============================================================== ban family
print("ban / tban / mute / unban / kick")
p = new_plugin()
check(typed(p, -500, ".ban spam", reply=reply_to(2000)) == "cancel", ".ban swallowed")
r = REQS[-1]
check(type(r).__name__ == "TL_channels_editBanned" and r.participant == ("peer", 2000) and r.channel == ("chan", 500), "editBanned targets reply user")
check(r.banned_rights.view_messages is True and r.banned_rights.until_date == 0, "ban = view_messages, forever")
check("banned" in last_msg() and "@bobby" in last_msg() and "spam" in last_msg(), "ban announcement with reason")
typed(p, -500, ".tban 1h flood", reply=reply_to(2000))
r = REQS[-1]
check(abs(r.banned_rights.until_date - (time.time() + 3600)) < 5, "tban until = now+1h")
check("1h" in last_msg() and "flood" in last_msg(), "tban announcement")
n = len(REQS)
typed(p, -500, ".tban 5s", reply=reply_to(2000))
check(len(REQS) == n and "duration" in TOASTS[-1], "bad time -> toast, no request")
typed(p, -500, ".tmute @bobby 2d no ads")
r = REQS[-1]
check(r.participant == ("peer", 2000) and r.banned_rights.send_messages is True, "@username target resolved, mute flags set")
check(getattr(r.banned_rights, "view_messages", False) is not True, "mute does not set view_messages")
check(abs(r.banned_rights.until_date - (time.time() + 2 * 86400)) < 5, "tmute until = now+2d")
typed(p, -500, ".mute 3000 loud")
check(REQS[-1].participant == ("peer", 3000), "numeric ID target")
typed(p, -500, ".unban", reply=reply_to(2000))
r = REQS[-1]
check(r.banned_rights.until_date == 0 and not getattr(r.banned_rights, "view_messages", False)
      and not getattr(r.banned_rights, "send_messages", False), "unban sends empty rights")
check("unbanned" in last_msg(), "unban announcement")
n = len(REQS)
typed(p, -500, ".unmute", reply=reply_to(2000))
check("unmuted" in last_msg(), "unmute announcement")
n = len(REQS)
typed(p, -500, ".kick bye", reply=reply_to(2000))
check(len(REQS) == n + 2, "kick = ban then lift")
check(REQS[-2].banned_rights.view_messages is True and getattr(REQS[-1].banned_rights, "view_messages", False) is not True, "kick order ban -> free")
check("removed" in last_msg(), "kick announcement")
typed(p, -500, ".dban", reply=reply_to(2000, mid=55))
check(DELETED[-1] == ([55], -500), ".dban also deletes the replied message")
n = len(REQS); typed(p, -500, ".ban", reply=reply_to(ME))
check(len(REQS) == n and "yourself" in TOASTS[-1], "cannot target yourself")
typed(p, -500, ".ban")
check("Reply to a user" in TOASTS[-1], "no target -> hint")
typed(p, -500, ".ban @nobody")
check("Reply to a user" in TOASTS[-1], "unknown @username -> hint")

print("errors, rights, PM, settings")
p = new_plugin()
RESP["err"] = Ns(text="USER_ADMIN_INVALID")
n = len(SENT); typed(p, -500, ".ban", reply=reply_to(2000))
check(len(SENT) == n and "admin" in TOASTS[-1].lower(), "server error shown as toast, no false 'banned' post")
RESP["err"] = Ns(text="CHAT_ADMIN_REQUIRED"); typed(p, -500, ".mute", reply=reply_to(2000))
check("rights" in TOASTS[-1].lower(), "CHAT_ADMIN_REQUIRED mapped")
p = new_plugin(admin=False)
typed(p, -500, ".ban", reply=reply_to(2000))
check(not REQS and "right" in TOASTS[-1].lower(), "no admin rights -> blocked before any request")
p = new_plugin()
typed(p, 2000, ".ban", reply=reply_to(2000))
check(not REQS and "groups only" in TOASTS[-1], "moderation refused in a PM")
p = new_plugin(megagroup=False)
typed(p, -500, ".mute", reply=reply_to(2000))
check("supergroup" in TOASTS[-1].lower(), "mute refused in a basic group")
typed(p, -500, ".ban", reply=reply_to(2000))
check(HELPER and HELPER[-1][0] == "kick", "ban in a basic group = remove via client helper")
p = new_plugin(); p._s["feedback"] = 1
n = len(SENT); typed(p, -500, ".ban", reply=reply_to(2000))
check(len(SENT) == n and "banned" in TOASTS[-1], "toast-only mode posts nothing in chat")
p = new_plugin()
check(typed(p, -500, "hello") == "default" and typed(p, -500, ".ping") == "default" and typed(p, -500, ".wc") == "default",
      "other messages and other plugins' commands untouched")
root = reply_to(2000, mid=9)
check(typed(p, -500, ".ban", reply=root, top=root) == "cancel" and not REQS and "Reply to a user" in TOASTS[-1],
      "forum topic root is not treated as a reply target")

# =============================================================== warns
print("warns")
p = new_plugin()
typed(p, -500, ".warn spam", reply=reply_to(2000))
check("(1/3)" in last_msg() and "spam" in last_msg(), "warn 1/3")
typed(p, -500, ".warn", reply=reply_to(2000))
check("(2/3)" in last_msg(), "warn 2/3")
typed(p, -500, ".warnings", reply=reply_to(2000))
check("Warnings of @bobby (2/3)" in last_msg() and "1. spam" in last_msg() and "2. no reason" in last_msg(), "warnings history")
typed(p, -500, ".unwarn", reply=reply_to(2000))
check("(1 left)" in last_msg(), "unwarn removes last")
typed(p, -500, ".warn x", reply=reply_to(2000)); n = len(REQS)
typed(p, -500, ".warn y", reply=reply_to(2000))
check(len(REQS) == n + 1 and REQS[-1].banned_rights.view_messages is True, "limit reached -> ban request")
check("reached 3 warnings" in "\n".join(s["message"] for s in SENT), "limit announcement")
check(p._store.chat(-500)["warns"].get("2000") is None, "warns reset after the action succeeded")
typed(p, -500, ".warn", reply=reply_to(3000)); typed(p, -500, ".resetwarns", reply=reply_to(3000))
typed(p, -500, ".warnings", reply=reply_to(3000))
check("No warnings" in last_msg(), "resetwarns")
typed(p, -500, ".warnlimit 2"); typed(p, -500, ".warnlimit")
check("limit: 2" in last_msg(), "warnlimit set/show")
typed(p, -500, ".warnmode tban 2d")
check("tban 2d" in last_msg(), "warnmode tban")
typed(p, -500, ".warnmode tban"); check("duration" in TOASTS[-1], "warnmode tban needs a duration")
typed(p, -500, ".warnmode nonsense"); check("Use: .warnmode" in TOASTS[-1], "warnmode validates")
typed(p, -500, ".warn", reply=reply_to(3000)); typed(p, -500, ".warn", reply=reply_to(3000))
check(abs(REQS[-1].banned_rights.until_date - (time.time() + 2 * 86400)) < 5, "limit action = tban 2d")
RESP["err"] = Ns(text="USER_ADMIN_INVALID")
typed(p, -500, ".warn", reply=reply_to(2000)); typed(p, -500, ".warn", reply=reply_to(2000))
check(len(p._store.chat(-500)["warns"].get("2000", [])) == 2, "failed action keeps the warnings")
typed(p, -500, ".warnmode kick"); RESP["err"] = None
typed(p, -500, ".warn", reply=reply_to(3000)); n = len(REQS); typed(p, -500, ".warn", reply=reply_to(3000))
check(len(REQS) - n == 2, "warn mode kick = ban then lift")

# =============================================================== purge / del / pin
print("purge / del / pin / unpin")
p = new_plugin()
incoming(p, -500, 2000, "msg", 100)
typed(p, -500, ".purge", reply=reply_to(2000, mid=95))
ids, dlg = DELETED[-1]
check(ids == list(range(95, 101)) and dlg == -500, "purge from reply to newest known id")
check("Deleted up to 6" in last_msg(), "purge announcement")
typed(p, -500, ".purge 3")
check(DELETED[-1][0] == [98, 99, 100], ".purge N deletes the last N")
n = len(DELETED); typed(p, -500, ".purge 5000")
check(len(DELETED) == n and "max" in TOASTS[-1], "purge size cap")
typed(p, -500, ".purge"); check("Reply to the first message" in TOASTS[-1], "purge usage hint")
incoming(p, -500, 2000, "msg", 1500)
typed(p, -500, ".purge", reply=reply_to(2000, mid=1))
check(len(DELETED) == n and "max" in TOASTS[-1], "reply range larger than the cap is refused")
big = new_plugin(); incoming(big, -500, 2000, "x", 250)
typed(big, -500, ".purge", reply=reply_to(2000, mid=1))
check(len(DELETED) == 3 and DELETED[0][0] == list(range(1, 101)) and DELETED[2][0] == list(range(201, 251)), "purge batches in chunks of 100")
q = new_plugin(megagroup=False); incoming(q, -500, 2000, "x", 100)
typed(q, -500, ".purge", reply=reply_to(2000, mid=90))
check(not DELETED and "supergroups only" in TOASTS[-1], "purge refused outside supergroups (ids are global there)")
q = new_plugin(); typed(q, -500, ".purge 3")
check("newest message" in TOASTS[-1], "purge without a known newest id is refused")
typed(p, -500, ".del", reply=reply_to(2000, mid=42))
check(DELETED[-1] == ([42], -500), ".del deletes the replied message")
typed(p, -500, ".pin", reply=reply_to(2000, mid=42))
r = REQS[-1]
check(type(r).__name__ == "TL_messages_updatePinnedMessage" and r.id == 42 and r.unpin is False and r.silent is True, ".pin is quiet by default")
typed(p, -500, ".pin loud", reply=reply_to(2000, mid=43)); check(REQS[-1].silent is False, ".pin loud notifies")
typed(p, -500, ".unpin", reply=reply_to(2000, mid=42)); check(REQS[-1].unpin is True and REQS[-1].id == 42, ".unpin one")
typed(p, -500, ".unpin all"); check(type(REQS[-1]).__name__ == "TL_messages_unpinAllMessages", ".unpin all")
typed(p, -500, ".pin"); check("Reply to a message" in TOASTS[-1], ".pin needs a reply")

# =============================================================== rules / notes / filters
print("rules / notes / filters")
p = new_plugin()
typed(p, -500, ".rules"); check("No rules" in last_msg(), "no rules yet")
typed(p, -500, ".setrules 1. Be kind\n2. No spam"); typed(p, -500, ".rules")
check("📜 Rules:" in last_msg() and "No spam" in last_msg(), "setrules + rules")
typed(p, -500, ".setrules", reply=reply_to(2000, text="Rule from reply")); typed(p, -500, ".rules")
check("Rule from reply" in last_msg(), "setrules from a replied message")
typed(p, -500, ".clearrules"); typed(p, -500, ".rules"); check("No rules" in last_msg(), "clearrules")
typed(p, -500, ".save hello Hi there!")
check(typed(p, -500, "#hello") == "cancel" and last_msg() == "Hi there!", "#note typed by you posts the note")
typed(p, -500, ".get hello"); check(last_msg() == "Hi there!", ".get")
typed(p, -500, ".notes"); check("#hello" in last_msg(), ".notes")
typed(p, -500, ".save"); check("Usage" in TOASTS[-1], ".save usage")
typed(p, -500, ".clear hello"); check(typed(p, -500, "#hello") == "default", ".clear removes the note")
typed(p, -500, ".filter price It's $5", ); n = len(SENT)
incoming(p, -500, 2000, "what is the Price?", 1)
check(len(SENT) == n + 1 and last_msg() == "It's $5", "filter answers a matching message from someone else")
incoming(p, -500, 2000, "price again", 2); check(len(SENT) == n + 1, "filter cooldown prevents spam")
p._cool.clear(); incoming(p, -500, 2000, "pricey stuff", 3); check(len(SENT) == n + 1, "whole-word match only")
incoming(p, -500, ME, "price", 4); p._cool.clear(); check(len(SENT) == n + 1, "never answers your own messages")
p._s["autoreply"] = False; p._cool.clear(); incoming(p, -500, 2000, "price", 5)
check(len(SENT) == n + 1, "auto-reply switch off")
p._s["autoreply"] = True; incoming(p, -999, 2000, "price", 6); check(len(SENT) == n + 1, "filters are per chat")
typed(p, -500, ".filters"); check("price" in last_msg(), ".filters")
typed(p, -500, ".stop price"); check("removed" in last_msg(), ".stop")

# =============================================================== report / admins / info / id
print("report / admins / info / id")
p = new_plugin()
RESP["res"] = Ns(users=[Ns(id=2000, username="bobby", first_name="Bob", last_name="", bot=False),
                        Ns(id=4000, username="helper_bot", first_name="Helper", last_name="", bot=True),
                        Ns(id=3000, username="", first_name="Cara", last_name="", bot=False),
                        Ns(id=5000, username="outsider", first_name="Out", last_name="", bot=False)],
                 participants=[Ns(user_id=2000), Ns(user_id=4000), Ns(peer=Ns(user_id=3000))])
typed(p, -500, ".report being rude", reply=reply_to(3000, mid=9))
msg = SENT[-1]
check(type(REQS[-1]).__name__ == "TL_channels_getParticipants", "admins fetched with getParticipants")
check("Report from @meuser about Cara K" in msg["message"] and "being rude" in msg["message"], "report text")
check("@bobby" in msg["message"] and "helper_bot" not in msg["message"] and "outsider" not in msg["message"], "pings human admins only")
check(msg.get("replyToMsg") is not None, "report replies to the reported message")
n = len(REQS); typed(p, -500, ".admins")
check(len(REQS) == n and "@bobby" in last_msg(), "admin list cached")
typed(p, -500, ".report", ); check("Reply to a message" in TOASTS[-1], "report needs a reply")
typed(p, -500, ".info", reply=reply_to(2000))
check("ID: 2000" in last_msg() and "@bobby" in last_msg() and "premium" in last_msg() and "tg://user?id=2000" in last_msg(), ".info")
typed(p, -500, ".warn", reply=reply_to(2000)); typed(p, -500, ".info @bobby")
check("Warnings here: 1/3" in last_msg(), ".info shows warns")
typed(p, -500, ".id", reply=reply_to(2000)); check("Chat ID: -500" in last_msg() and "User ID: 2000" in last_msg(), ".id")

# =============================================================== export / import
print("export / import")
p = new_plugin()
typed(p, -500, ".setrules Be nice"); typed(p, -500, ".save faq Read the rules"); typed(p, -500, ".filter hi Hello!")
typed(p, -500, ".warn spam", reply=reply_to(2000)); typed(p, -500, ".warnlimit 5")
typed(p, -500, ".export")
peer, path, cap = DOCS[-1]
check(peer == ME and os.path.exists(path), "export goes to Saved Messages by default")
data = json.load(open(path, encoding="utf-8"))
c = data["chats"]["-500"]
check(data["format"] == M.FORMAT and c["rules"] == "Be nice" and c["notes"] == {"faq": "Read the rules"}
      and c["filters"] == {"hi": "Hello!"} and c["warn"]["limit"] == 5 and "2000" in c["warns"], "export content")
typed(p, -500, ".export here"); check(DOCS[-1][0] == -500, ".export here sends to the chat")
text = open(path, encoding="utf-8").read()
q = new_plugin()
typed(q, -600, ".import", reply=reply_to(ME, text=text))
c2 = q._store.chat(-600)
check(c2["rules"] == "Be nice" and c2["notes"] == {"faq": "Read the rules"} and c2["warn"]["limit"] == 5, "import from a pasted JSON message into another chat")
check("Imported: 1 rules, 1 notes, 1 filters, 1 warned users" in last_msg(), "import summary")
q2 = new_plugin()
LOADED_FILE["f"] = FakeFile(path)
doc_msg = Ns(getSenderId=lambda: ME, getId=lambda: 5, messageOwner=Ns(message="", media=Ns(document=object())))
typed(q2, -600, ".import", reply=doc_msg)
check(q2._store.chat(-600)["filters"] == {"hi": "Hello!"}, "import from a downloaded document")
LOADED_FILE["f"] = None
typed(q2, -600, ".import", reply=doc_msg); check("Download the file first" in TOASTS[-1], "document not downloaded yet")
typed(q2, -600, ".import"); check("Reply to an exported" in TOASTS[-1], "import needs a reply")
typed(q2, -600, ".import", reply=reply_to(ME, text="not json")); check("not a valid" in TOASTS[-1], "garbage rejected")
typed(q2, -600, ".import", reply=reply_to(ME, text=json.dumps({"format": "other", "version": 1, "chats": {}})))
check("not a valid" in TOASTS[-1], "wrong format rejected")
# replace vs merge
q3 = new_plugin(); typed(q3, -600, ".save old keep me")
typed(q3, -600, ".import", reply=reply_to(ME, text=text)); check("old" in q3._store.chat(-600)["notes"], "merge keeps existing notes")
typed(q3, -600, ".import replace", reply=reply_to(ME, text=text)); check("old" not in q3._store.chat(-600)["notes"], "replace wipes existing notes")
# export all + multi-chat
typed(p, -600, ".save two 2"); typed(p, -500, ".export all"); alltext = open(DOCS[-1][1], encoding="utf-8").read()
check(set(json.loads(alltext)["chats"]) == {"-500", "-600"}, "export all holds every chat")
r = new_plugin()
typed(r, -600, ".import", reply=reply_to(ME, text=alltext)); check("several chats" in TOASTS[-1], "multi-chat file needs .import all")
typed(r, -600, ".import all", reply=reply_to(ME, text=alltext))
check(r._store.peek(-500)["rules"] == "Be nice" and r._store.peek(-600)["notes"] == {"two": "2"} and "Imported 2 chats" in last_msg(), ".import all restores by original ids")
# hostile file
evil = json.dumps({"format": M.FORMAT, "version": 1, "chats": {"-1": {"rules": 5, "notes": {"../../x": "t", "ok": ["list"]},
                   "filters": "str", "warn": "x", "warns": {"1": "nope"}}}})
r2 = new_plugin(); typed(r2, -600, ".import", reply=reply_to(ME, text=evil))
c3 = r2._store.chat(-600)
check(c3["notes"] == {} and c3["rules"] == "" and c3["warns"] == {} and c3["warn"]["mode"] == "ban", "malformed import fields are dropped, not trusted")
# persistence
s1 = new_plugin(); typed(s1, -500, ".setrules persist")
s2 = M.EmpireAdminPlugin(); s2._s = s1._s; s2.on_plugin_load()
check(s2._store.peek(-500)["rules"] == "persist", "data persists through plugin settings")
s2._reset_all(); check(s2._store.db == {"chats": {}}, "reset erases everything")

# =============================================================== strings
print("strings")
src = open(PLUGIN, encoding="utf-8").read()
used = set(re.findall(r'self\.T\("([a-z_0-9]+)"', src)) | set(re.findall(r'T\("([a-z_0-9]+)"', src))
used |= {k for k in re.findall(r'"([a-z_]+)"', "".join(re.findall(r'_simple_restrict\([^)]*\)', src))) if k in M.STR["en"]}
missing = [k for k in used if k not in M.STR["en"] or k not in M.STR["ru"]]
check(not missing, "every string key exists in EN and RU (%d keys)" % len(used))
check(set(M.STR["en"]) == set(M.STR["ru"]), "EN and RU have identical key sets")
for lang in ("en", "ru"):
    p = new_plugin(); p._s["lang"] = 1 if lang == "en" else 2
    typed(p, -500, ".adminhelp"); check(len(last_msg()) > 100, ".adminhelp renders (%s)" % lang)
print("\nALL %d CHECKS PASSED" % passed)

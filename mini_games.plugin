import json
import random
import re
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from android_utils import log, run_on_ui_thread
from base_plugin import BasePlugin, HookResult, HookStrategy
from client_utils import (
    get_messages_controller,
    get_notification_center,
    get_user_config,
    send_message,
)
from java import dynamic_proxy
from java.lang import Integer
from java.util import ArrayList
from org.telegram.messenger import LocaleController, MessagesController, NotificationCenter, UserConfig
from ui.bulletin import BulletinHelper
from ui.settings import Divider, Header, Input, Selector, Switch, Text

__id__ = "mini_games"
__name__ = "Mini Games: .wc & .ttt"
__description__ = (
    "Two chat mini-games with inline buttons and score tables.\n"
    "• .wc  - 4-digit guessing game (hints: 🎯 right place, 🔸 wrong place)\n"
    "• .ttt - Tic-Tac-Toe\n"
    "Challenge a friend in a PM, or reply to someone in a group with the command.\n"
    "Extra: .wc help / top / me / stop (same for .ttt). Points are plain game scores."
)
__author__ = "@mzgram_community"
__version__ = "1.0.0"
__min_version__ = "11.12.0"
__icon__ = "uniposting/54"
__category__ = ["fun"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CB = "mg"                      # callback_data prefix:  mg:<gid>:<action>
TTL_ACTIVE = 30 * 60           # an idle game is dropped after 30 minutes
TTL_PENDING = 5 * 60           # an unanswered challenge expires after 5 minutes
MAX_HISTORY_LINES = 8
SCORE_KEEP = 200               # rows kept per leaderboard scope
GID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

CMD_RE = re.compile(r"^\.(wc|ttt)(?:\s+(.*))?$", re.IGNORECASE | re.DOTALL)
GUESS_RE = re.compile(r"^\d{4}$")
CELL_RE = re.compile(r"^[1-9]$")
ACCEPT_WORDS = {"+", "yes", "y", "accept", "join", "play", "да", "д", "го"}
DECLINE_WORDS = {"-", "no", "n", "decline", "нет", "н"}

TTT_LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))
NUM_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
MARK = {"X": "❌", "O": "⭕"}

STR = {
    "en": {
        "busy": "⏳ A game is already running here. Finish it or send {cmd} stop.",
        "nothing": "No active game here. Start one with {cmd}.",
        "stopped_by": "🛑 Game stopped.",
        "only_host": "Only the game's host can stop it.",
        # WC
        "wc_title": "🔢 4-Digit Guess",
        "wc_open": "👥 Open game: anyone in this chat can guess",
        "wc_duel": "⚔️ Duel: {a} vs {b}",
        "wc_solo": "🧩 Solo game",
        "wc_legend": "🎯 right digit & place · 🔸 right digit, wrong place",
        "wc_rule_same": "Digits may repeat.",
        "wc_rule_diff": "All 4 digits are different (0 may lead).",
        "wc_left": "Attempts left: {items}",
        "wc_prompt": "✍️ Send 4 digits (e.g. 4071) or use the keypad",
        "wc_none": "No guesses yet.",
        "wc_won": "🏆 {name} cracked the code {secret} in {n} tries! +{pts} pts",
        "wc_lost": "💥 Out of attempts! The code was {secret}",
        "wc_stop": "🏳 Game over. The code was {secret}",
        "wc_bad_repeat": "⚠️ Digits must all be different.",
        "wc_no_attempts": "🚫 No attempts left.",
        "wc_input": "Input: {buf}",
        "wc_name": "4-Digit Guess",
        # TTT
        "ttt_title": "❌⭕ Tic-Tac-Toe",
        "ttt_challenge": "🎮 {a} challenges {b} to Tic-Tac-Toe!",
        "ttt_anyone": "anyone",
        "ttt_accept": "Reply + to accept (or - to decline). Expires in 5 min.",
        "ttt_players": "{x} {xn}  vs  {o} {on}",
        "ttt_turn": "▶️ Turn: {name}. Send a number 1-9 or tap a cell",
        "ttt_win": "🏆 {name} wins! +3 pts",
        "ttt_draw": "🤝 Draw! +1 pt each",
        "ttt_practice": "Practice mode (no points)",
        "ttt_taken": "⚠️ That cell is taken.",
        "ttt_not_turn": "⏳ Not your turn.",
        "ttt_wait": "Waiting for the opponent to accept.",
        "ttt_declined": "🙅 Challenge declined.",
        "ttt_cancelled": "🛑 Challenge cancelled.",
        "ttt_resigned": "🏳 {name} resigned. {other} wins! +3 pts",
        "ttt_expired": "⌛ Challenge expired.",
        # buttons / misc
        "b_top": "🏆 Top",
        "b_giveup": "🏳 Give up",
        "b_new": "🔁 New game",
        "b_rematch": "🔁 Rematch",
        "b_cancel": "❌ Cancel",
        "b_resign": "🏳 Resign",
        "cb_gone": "This game is over or expired.",
        "cb_stale": "That's an old board, use the latest one.",
        "cb_over": "Game over.",
        "top_title": "🏆 {game}: top players ({scope})",
        "scope_chat": "this chat",
        "scope_all": "all chats",
        "top_empty": "No scores yet. Play a game!",
        "top_row": "{medal} {name} — {p} pts · {w}W {l}L {d}D",
        "me_row": "📊 {name} in {game} ({scope}): {p} pts · {w} wins · {l} losses · {d} draws · {g} games",
        "me_none": "No games played yet.",
        "pts": "pts",
        "help_wc": (
            "🔢 4-Digit Guess (.wc)\n"
            "I hide a 4-digit code, you crack it.\n"
            "• .wc: start (in a PM it's a duel; reply to a friend in a group to challenge them)\n"
            "• Guess: send 4 digits, or tap the keypad (host)\n"
            "• 🎯 right digit & place · 🔸 right digit, wrong place\n"
            "• Win: up to 100 pts, fewer tries = more points\n"
            "• .wc top [all] · .wc me · .wc stop"
        ),
        "help_ttt": (
            "❌⭕ Tic-Tac-Toe (.ttt)\n"
            "• .ttt: challenge (in a PM it's your friend; reply to someone in a group)\n"
            "• Opponent accepts by replying +\n"
            "• Move: send a number 1-9 (1 = top-left, 9 = bottom-right) or tap a cell\n"
            "• Win 3 pts · draw 1 pt\n"
            "• .ttt top [all] · .ttt me · .ttt stop"
        ),
        # settings
        "s_head": "Mini Games",
        "s_lang": "Message language",
        "s_lang_items": ["Auto", "English", "Русский"],
        "s_buttons": "Inline buttons",
        "s_buttons_sub": "Off: text-only games (type your guesses / moves).",
        "s_replace": "Replace old board",
        "s_replace_sub": "On: the previous board message is deleted when a new one is posted. Off: it stays, buttons removed.",
        "s_repeat": "WC: allow repeated digits",
        "s_attempts": "WC: attempts per player",
        "s_attempts_sub": "1 to 30",
        "s_reset_wc": "Reset .wc scores",
        "s_reset_ttt": "Reset .ttt scores",
        "s_done": "Scores reset",
        "s_foot": "Points are plain game scores with no monetary value. The host's device keeps the game state.",
    },
    "ru": {
        "busy": "⏳ Здесь уже идёт игра. Закончите её или отправьте {cmd} stop.",
        "nothing": "Активной игры нет. Начните: {cmd}.",
        "stopped_by": "🛑 Игра остановлена.",
        "only_host": "Остановить игру может только её хозяин.",
        "wc_title": "🔢 Угадай 4 цифры",
        "wc_open": "👥 Открытая игра: угадывать может любой в чате",
        "wc_duel": "⚔️ Дуэль: {a} vs {b}",
        "wc_solo": "🧩 Одиночная игра",
        "wc_legend": "🎯 цифра на месте · 🔸 цифра есть, но не на месте",
        "wc_rule_same": "Цифры могут повторяться.",
        "wc_rule_diff": "Все 4 цифры разные (0 может быть первым).",
        "wc_left": "Осталось попыток: {items}",
        "wc_prompt": "✍️ Отправьте 4 цифры (напр. 4071) или жмите на клавиатуру",
        "wc_none": "Пока нет попыток.",
        "wc_won": "🏆 {name} взломал(а) код {secret} за {n} поп.! +{pts} очк.",
        "wc_lost": "💥 Попытки кончились! Код был {secret}",
        "wc_stop": "🏳 Игра окончена. Код был {secret}",
        "wc_bad_repeat": "⚠️ Все цифры должны быть разными.",
        "wc_no_attempts": "🚫 Попыток не осталось.",
        "wc_input": "Ввод: {buf}",
        "wc_name": "Угадай 4 цифры",
        "ttt_title": "❌⭕ Крестики-нолики",
        "ttt_challenge": "🎮 {a} вызывает {b} на крестики-нолики!",
        "ttt_anyone": "любого желающего",
        "ttt_accept": "Ответьте + чтобы принять (или - чтобы отказаться). Вызов истекает через 5 мин.",
        "ttt_players": "{x} {xn}  vs  {o} {on}",
        "ttt_turn": "▶️ Ход: {name}. Отправьте число 1-9 или нажмите клетку",
        "ttt_win": "🏆 Победил(а) {name}! +3 очк.",
        "ttt_draw": "🤝 Ничья! +1 очко каждому",
        "ttt_practice": "Тренировка (без очков)",
        "ttt_taken": "⚠️ Клетка занята.",
        "ttt_not_turn": "⏳ Сейчас не ваш ход.",
        "ttt_wait": "Ждём, пока соперник примет вызов.",
        "ttt_declined": "🙅 Вызов отклонён.",
        "ttt_cancelled": "🛑 Вызов отменён.",
        "ttt_resigned": "🏳 {name} сдался(лась). Победил(а) {other}! +3 очк.",
        "ttt_expired": "⌛ Вызов истёк.",
        "b_top": "🏆 Топ",
        "b_giveup": "🏳 Сдаться",
        "b_new": "🔁 Новая игра",
        "b_rematch": "🔁 Реванш",
        "b_cancel": "❌ Отмена",
        "b_resign": "🏳 Сдаться",
        "cb_gone": "Игра закончена или устарела.",
        "cb_stale": "Это старая доска, используйте последнюю.",
        "cb_over": "Игра окончена.",
        "top_title": "🏆 {game}: лучшие игроки ({scope})",
        "scope_chat": "этот чат",
        "scope_all": "все чаты",
        "top_empty": "Очков пока нет. Сыграйте!",
        "top_row": "{medal} {name} — {p} очк. · {w}П {l}Пр {d}Н",
        "me_row": "📊 {name} в «{game}» ({scope}): {p} очк. · {w} побед · {l} поражений · {d} ничьих · {g} игр",
        "me_none": "Вы ещё не играли.",
        "pts": "очк.",
        "help_wc": (
            "🔢 Угадай 4 цифры (.wc)\n"
            "Я загадываю 4-значный код, вы его взламываете.\n"
            "• .wc: старт (в ЛС это дуэль; в группе ответьте на сообщение друга, чтобы бросить вызов)\n"
            "• Попытка: отправьте 4 цифры или жмите клавиатуру (хозяин игры)\n"
            "• 🎯 цифра на месте · 🔸 цифра есть, но не на месте\n"
            "• Победа: до 100 очков, меньше попыток = больше очков\n"
            "• .wc top [all] · .wc me · .wc stop"
        ),
        "help_ttt": (
            "❌⭕ Крестики-нолики (.ttt)\n"
            "• .ttt: вызов (в ЛС это ваш собеседник; в группе ответьте на сообщение)\n"
            "• Соперник принимает ответом +\n"
            "• Ход: число 1-9 (1 = верх-лево, 9 = низ-право) или нажатие на клетку\n"
            "• Победа 3 очка · ничья 1 очко\n"
            "• .ttt top [all] · .ttt me · .ttt stop"
        ),
        "s_head": "Мини-игры",
        "s_lang": "Язык сообщений",
        "s_lang_items": ["Авто", "English", "Русский"],
        "s_buttons": "Inline-кнопки",
        "s_buttons_sub": "Выкл: только текст (вводите ходы сообщениями).",
        "s_replace": "Заменять старую доску",
        "s_replace_sub": "Вкл: предыдущая доска удаляется при публикации новой. Выкл: остаётся, кнопки убираются.",
        "s_repeat": "WC: разрешить повтор цифр",
        "s_attempts": "WC: попыток на игрока",
        "s_attempts_sub": "От 1 до 30",
        "s_reset_wc": "Сбросить очки .wc",
        "s_reset_ttt": "Сбросить очки .ttt",
        "s_done": "Очки сброшены",
        "s_foot": "Очки это просто игровой счёт без денежной ценности. Состояние игры хранится на устройстве хозяина.",
    },
}


# ---------------------------------------------------------------------------
# Pure game logic (no Telegram / Android calls in this block)
# ---------------------------------------------------------------------------

def make_secret(allow_repeat: bool) -> str:
    digits = "0123456789"
    if allow_repeat:
        return "".join(random.choice(digits) for _ in range(4))
    return "".join(random.sample(digits, 4))


def valid_guess(guess: str, allow_repeat: bool) -> bool:
    if not GUESS_RE.match(guess):
        return False
    return allow_repeat or len(set(guess)) == 4


def bulls_cows(secret: str, guess: str) -> Tuple[int, int]:
    """bulls = right digit & place, cows = right digit elsewhere (duplicate-safe)."""
    bulls = sum(1 for a, b in zip(secret, guess) if a == b)
    common = sum(min(secret.count(d), guess.count(d)) for d in set(guess))
    return bulls, common - bulls


def wc_points(attempts: int) -> int:
    return max(20, 100 - 10 * (attempts - 1))


def ttt_winner(board: List[str]) -> str:
    for a, b, c in TTT_LINES:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    return ""


class Session:
    """State of one game in one chat. Mutated only while the plugin lock is held."""

    def __init__(self, kind: str, account: int, dialog: int, host: int):
        self.kind = kind
        self.account = account
        self.dialog = dialog
        self.host = host
        self.gid = kind[0].upper() + "".join(random.choice(GID_ALPHABET) for _ in range(3))
        self.created = time.time()
        self.updated = self.created
        self.state = "active"        # pending | active | done
        self.result = ""             # won | lost | stopped | X | O | draw | resigned | declined | cancelled
        self.board_id = 0            # message id of the newest board (learned via NotificationCenter)
        self.rev = 0                 # publish counter; lets the sender drop stale renders
        self.target = 0              # challenged user id (0 = anyone)
        # .wc
        self.secret = ""
        self.allow_repeat = False
        self.max_attempts = 10
        self.guesses: List[Tuple[int, str, int, int, int]] = []   # uid, guess, bulls, cows, nth attempt
        self.attempts: Dict[int, int] = {}
        self.input = ""
        self.winner = 0
        self.points = 0
        # .ttt
        self.x = 0
        self.o = 0
        self.cells = [" "] * 9
        self.turn = "X"

    def touch(self):
        self.updated = time.time()

    @property
    def hotseat(self) -> bool:
        return self.kind == "ttt" and self.x == self.o

    def expired(self) -> bool:
        if self.state == "done":
            return False
        ttl = TTL_PENDING if self.state == "pending" else TTL_ACTIVE
        return time.time() - self.updated > ttl


class ScoreStore:
    """Persistent non-monetary score tables, kept as JSON in the plugin settings."""

    def __init__(self, plugin):
        self.plugin = plugin
        self.lock = threading.Lock()

    def _load(self, kind: str) -> dict:
        try:
            data = json.loads(self.plugin.get_setting("scores_" + kind, "{}"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save(self, kind: str, data: dict):
        self.plugin.set_setting("scores_" + kind, json.dumps(data, ensure_ascii=False))

    def record_many(self, kind: str, dialog: int, entries: List[Tuple[int, str, int, str]]):
        """entries: (uid, display name, points, outcome) with outcome in win|loss|draw."""
        with self.lock:
            data = self._load(kind)
            for scope in (str(dialog), "*"):
                bucket = data.setdefault(scope, {})
                for uid, name, pts, outcome in entries:
                    r = bucket.setdefault(str(uid), {"n": name, "p": 0, "w": 0, "l": 0, "d": 0, "g": 0})
                    r["n"] = name or r.get("n", "")
                    r["p"] += pts
                    r["g"] += 1
                    key = {"win": "w", "loss": "l", "draw": "d"}[outcome]
                    r[key] += 1
                if len(bucket) > SCORE_KEEP:
                    keep = sorted(bucket.items(), key=lambda kv: kv[1].get("p", 0), reverse=True)[:SCORE_KEEP]
                    data[scope] = dict(keep)
            self._save(kind, data)

    def top(self, kind: str, scope: str, n: int = 10) -> List[Tuple[str, dict]]:
        with self.lock:
            bucket = self._load(kind).get(scope, {})
        rows = sorted(bucket.items(), key=lambda kv: (kv[1].get("p", 0), kv[1].get("w", 0)), reverse=True)
        return rows[:n]

    def get(self, kind: str, scope: str, uid: int) -> Optional[dict]:
        with self.lock:
            return self._load(kind).get(scope, {}).get(str(uid))

    def reset(self, kind: str):
        with self.lock:
            self._save(kind, {})


# ---------------------------------------------------------------------------
# NotificationCenter observer: learns the real id of a board we just sent
# ---------------------------------------------------------------------------

def _to_int(value) -> int:
    try:
        return int(str(value))
    except Exception:
        return 0


class _SentWatcher(dynamic_proxy(NotificationCenter.NotificationCenterDelegate)):
    def __init__(self, plugin, account):
        super().__init__()
        self.plugin = plugin
        self.account = account

    def didReceivedNotification(self, id, account, args):
        try:
            if id != NotificationCenter.messageReceivedByServer:
                return
            new_id = _to_int(args[1])
            msg = args[2]
            dialog = _to_int(args[3]) if len(args) > 3 else 0
            text = getattr(msg, "message", None)
            if not new_id or not text:
                return
            self.plugin.on_board_confirmed(self.account, dialog, new_id, str(text))
        except Exception as e:
            log("[MiniGames] watcher: %s" % e)


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class MiniGamesPlugin(BasePlugin):

    # ----- lifecycle -------------------------------------------------------

    def on_plugin_load(self):
        self._lock = threading.RLock()
        self._sessions: Dict[Tuple[int, int, str], Session] = {}
        self._exec = ThreadPoolExecutor(max_workers=1)   # one worker = strictly ordered sends
        self._seen = deque(maxlen=400)
        self._seen_set = set()
        self._watchers: Dict[int, Any] = {}
        self._names: Dict[int, str] = {}
        self._usernames: Dict[int, str] = {}
        self._auto_lang = None
        self._scores = ScoreStore(self)

        self.add_on_send_message_hook()
        try:
            self.add_on_callback_query_hook()
        except Exception as e:
            log("[MiniGames] callback hook unavailable: %s" % e)
        for name in ("TL_updateNewMessage", "TL_updateNewChannelMessage",
                     "TL_updateShortMessage", "TL_updateShortChatMessage"):
            try:
                self.add_hook(name)
            except Exception as e:
                log("[MiniGames] add_hook(%s): %s" % (name, e))
        try:
            self._ensure_watcher(UserConfig.selectedAccount)
        except Exception as e:
            log("[MiniGames] watcher: %s" % e)
        log("[MiniGames] loaded")

    def on_plugin_unload(self):
        try:
            for account, watcher in list(self._watchers.items()):
                center = get_notification_center(account)
                run_on_ui_thread(lambda c=center, w=watcher: c.removeObserver(w, NotificationCenter.messageReceivedByServer))
            self._watchers.clear()
            with self._lock:
                self._sessions.clear()
            self._exec.shutdown(wait=False)
        except Exception as e:
            log("[MiniGames] unload: %s" % e)

    def _ensure_watcher(self, account: int):
        if account in self._watchers:
            return
        watcher = _SentWatcher(self, account)
        center = get_notification_center(account)
        run_on_ui_thread(lambda: center.addObserver(watcher, NotificationCenter.messageReceivedByServer))
        self._watchers[account] = watcher

    # ----- settings --------------------------------------------------------

    def create_settings(self):
        t = lambda k: STR[self._lang()][k]
        return [
            Header(text=t("s_head")),
            Selector(key="lang", text=t("s_lang"), default=0, items=t("s_lang_items"), icon="msg_language"),
            Switch(key="buttons", text=t("s_buttons"), default=True, subtext=t("s_buttons_sub"), icon="msg_list"),
            Switch(key="replace_board", text=t("s_replace"), default=True, subtext=t("s_replace_sub"), icon="msg_delete"),
            Divider(),
            Switch(key="wc_repeat", text=t("s_repeat"), default=False, icon="msg_edit"),
            Input(key="wc_attempts", text=t("s_attempts"), default="10", subtext=t("s_attempts_sub"), icon="msg_recent"),
            Divider(),
            Text(text=t("s_reset_wc"), on_click=lambda _: self._reset_scores("wc"), icon="msg_clear"),
            Text(text=t("s_reset_ttt"), on_click=lambda _: self._reset_scores("ttt"), icon="msg_clear"),
            Divider(text=t("s_foot")),
        ]

    def _reset_scores(self, kind: str):
        try:
            self._scores.reset(kind)
            self._toast(STR[self._lang()]["s_done"])
        except Exception as e:
            log("[MiniGames] reset: %s" % e)

    def _int_setting(self, key: str, default: int, lo: int, hi: int) -> int:
        try:
            v = int(str(self.get_setting(key, str(default))).strip())
        except Exception:
            v = default
        return max(lo, min(hi, v))

    # ----- small helpers ---------------------------------------------------

    def _lang(self) -> str:
        try:
            choice = int(self.get_setting("lang", 0))
        except Exception:
            choice = 0
        if choice == 1:
            return "en"
        if choice == 2:
            return "ru"
        if self._auto_lang is None:
            try:
                code = str(LocaleController.getInstance().getCurrentLocaleInfo().getLangCode())
            except Exception:
                code = "en"
            self._auto_lang = "ru" if code.lower().startswith(("ru", "uk", "be")) else "en"
        return self._auto_lang

    def T(self, key: str, **kw) -> str:
        text = STR[self._lang()].get(key) or STR["en"].get(key, key)
        return text.format(**kw) if kw else text

    def _toast(self, text: str):
        try:
            run_on_ui_thread(lambda: BulletinHelper.show_info(text))
        except Exception as e:
            log("[MiniGames] toast: %s" % e)

    def _me(self, account: int) -> int:
        try:
            return int(UserConfig.getInstance(account).getClientUserId())
        except Exception:
            try:
                return int(get_user_config().getClientUserId())
            except Exception:
                return 0

    def _load_user(self, account: int, uid: int):
        try:
            user = MessagesController.getInstance(account).getUser(uid)
        except Exception:
            user = None
        if user is None:
            return
        first = str(getattr(user, "first_name", "") or "")
        last = str(getattr(user, "last_name", "") or "")
        full = (first + " " + last).strip()
        uname = str(getattr(user, "username", "") or "")
        if full:
            self._names[uid] = full
        elif uname:
            self._names[uid] = uname
        if uname:
            self._usernames[uid] = uname

    def _name(self, account: int, uid: int) -> str:
        if uid not in self._names:
            self._load_user(account, uid)
        return self._names.get(uid) or ("User %d" % uid)

    def _mention(self, account: int, uid: int) -> str:
        self._name(account, uid)
        uname = self._usernames.get(uid)
        return "@" + uname if uname else self._name(account, uid)

    def _submit(self, fn, *args):
        def run():
            try:
                fn(*args)
            except Exception as e:
                import traceback
                log("[MiniGames] task error: %s\n%s" % (e, traceback.format_exc()))
        try:
            self._exec.submit(run)
        except Exception as e:
            log("[MiniGames] submit: %s" % e)

    def _live(self, key) -> Optional[Session]:
        """Active or pending session for this chat/game, or None (expired ones are dropped)."""
        s = self._sessions.get(key)
        if s is None:
            return None
        if s.expired():
            if s.state == "pending":
                self._say(s.account, s.dialog, self.T("ttt_expired"))
            self._sessions.pop(key, None)
            return None
        return s if s.state in ("pending", "active") else None

    # ----- sending ---------------------------------------------------------

    def _payload(self, account: int, dialog: int, text: str) -> dict:
        p = {"peer": dialog, "message": text}
        try:
            if account != UserConfig.selectedAccount:
                p["account"] = account
        except Exception:
            pass
        return p

    def _say(self, account: int, dialog: int, text: str):
        self._submit(lambda: send_message(self._payload(account, dialog, text)))

    def _send_board(self, account: int, dialog: int, text: str, rows):
        payload = self._payload(account, dialog, text)
        if rows and self.get_setting("buttons", True):
            with_kb = dict(payload)
            with_kb["reply_markup"] = {"inline_keyboard": rows}
            try:
                send_message(with_kb)
                return
            except Exception as e:
                log("[MiniGames] send with keyboard failed (%s), sending text only" % e)
        send_message(payload)

    def _publish(self, s: Session):
        """Queue a fresh board for this session. Only the newest queued render is actually sent."""
        s.touch()
        s.rev += 1
        self._submit(self._do_publish, s, s.rev)

    def _do_publish(self, s: Session, rev: int):
        with self._lock:
            if s.rev != rev:
                return
            text, rows = self._render(s)
        self._send_board(s.account, s.dialog, text, rows)

    def on_board_confirmed(self, account: int, dialog: int, new_id: int, text: str):
        """Called from the NotificationCenter observer when one of our messages got a real id."""
        with self._lock:
            for s in self._sessions.values():
                if s.account == account and s.dialog == dialog and ("#" + s.gid) in text:
                    prev = s.board_id
                    s.board_id = new_id
                    if prev and prev != new_id:
                        self._submit(self._retire, account, dialog, prev)
                    return

    def _retire(self, account: int, dialog: int, msg_id: int):
        """Get rid of an outdated board: delete it, or at least strip its buttons."""
        replace = self.get_setting("replace_board", True)

        def work():
            if replace:
                try:
                    ids = ArrayList()
                    ids.add(Integer(msg_id))
                    get_messages_controller().deleteMessages(ids, None, None, dialog, 0, True, 0)
                    return
                except Exception as e:
                    log("[MiniGames] delete failed (%s), stripping buttons" % e)
            try:
                get_messages_controller().editMessageReplyMarkup(dialog, msg_id, None)
            except Exception as e:
                log("[MiniGames] strip buttons: %s" % e)

        run_on_ui_thread(work)

    # ----- rendering -------------------------------------------------------

    def _render(self, s: Session) -> Tuple[str, List[List[dict]]]:
        return self._render_wc(s) if s.kind == "wc" else self._render_ttt(s)

    @staticmethod
    def _btn(text: str, gid: str, action: str) -> dict:
        return {"text": text, "callback_data": "%s:%s:%s" % (CB, gid, action)}

    def _players_wc(self, s: Session) -> List[int]:
        ids = [s.host]
        if s.target and s.target != s.host:
            ids.append(s.target)
        for uid in s.attempts:
            if uid not in ids:
                ids.append(uid)
        return ids

    def _render_wc(self, s: Session):
        a = s.account
        lines = [self.T("wc_title")]
        if s.target and s.target != s.host:
            lines.append(self.T("wc_duel", a=self._name(a, s.host), b=self._name(a, s.target)))
        elif s.dialog == s.host:
            lines.append(self.T("wc_solo"))
        else:
            lines.append(self.T("wc_open"))
        lines.append(self.T("wc_rule_same" if s.allow_repeat else "wc_rule_diff"))
        lines.append(self.T("wc_legend"))
        lines.append("━━━━━━━━━━")
        if not s.guesses:
            lines.append(self.T("wc_none"))
        else:
            if len(s.guesses) > MAX_HISTORY_LINES:
                lines.append("…")
            for uid, guess, b, c, n in s.guesses[-MAX_HISTORY_LINES:]:
                lines.append("#%d %s  %s → 🎯%d 🔸%d" % (n, self._name(a, uid), guess, b, c))
        lines.append("━━━━━━━━━━")
        if s.state == "active":
            items = ", ".join("%s %d" % (self._name(a, u), max(0, s.max_attempts - s.attempts.get(u, 0)))
                              for u in self._players_wc(s))
            lines.append(self.T("wc_left", items=items))
            lines.append(self.T("wc_prompt"))
            rows = [
                [self._btn(str(d), s.gid, "d%d" % d) for d in (1, 2, 3)],
                [self._btn(str(d), s.gid, "d%d" % d) for d in (4, 5, 6)],
                [self._btn(str(d), s.gid, "d%d" % d) for d in (7, 8, 9)],
                [self._btn("⌫", s.gid, "bk"), self._btn("0", s.gid, "d0"), self._btn("✖", s.gid, "cl")],
                [self._btn(self.T("b_top"), s.gid, "top"), self._btn(self.T("b_giveup"), s.gid, "end")],
            ]
        else:
            if s.result == "won":
                lines.append(self.T("wc_won", name=self._name(a, s.winner), secret=s.secret,
                                    n=s.attempts.get(s.winner, 0), pts=s.points))
            elif s.result == "lost":
                lines.append(self.T("wc_lost", secret=s.secret))
            else:
                lines.append(self.T("wc_stop", secret=s.secret))
            rows = [[self._btn(self.T("b_new"), s.gid, "new"), self._btn(self.T("b_top"), s.gid, "top")]]
        lines.append("#" + s.gid)
        return "\n".join(lines), rows

    def _ttt_board_text(self, s: Session) -> str:
        out = []
        for r in range(3):
            out.append(" ".join(MARK[c] if c in MARK else NUM_EMOJI[r * 3 + i]
                                for i, c in enumerate(s.cells[r * 3:r * 3 + 3])))
        return "\n".join(out)

    def _ttt_name(self, s: Session, mark: str) -> str:
        return self._name(s.account, s.x if mark == "X" else s.o)

    def _render_ttt(self, s: Session):
        a = s.account
        lines = [self.T("ttt_title"), ""]
        if s.state == "pending":
            who = self._mention(a, s.target) if s.target else self.T("ttt_anyone")
            lines.append(self.T("ttt_challenge", a=self._name(a, s.host), b=who))
            lines.append(self.T("ttt_accept"))
            rows = [[self._btn(self.T("b_cancel"), s.gid, "end")]]
        else:
            lines.append(self._ttt_board_text(s))
            lines.append("")
            lines.append(self.T("ttt_players", x=MARK["X"], xn=self._ttt_name(s, "X"),
                                o=MARK["O"], on=self._ttt_name(s, "O")))
            if s.hotseat:
                lines.append(self.T("ttt_practice"))
            if s.state == "active":
                lines.append(self.T("ttt_turn", name=MARK[s.turn] + " " + self._ttt_name(s, s.turn)))
                rows = []
                for r in range(3):
                    row = []
                    for i in range(r * 3, r * 3 + 3):
                        label = MARK[s.cells[i]] if s.cells[i] in MARK else NUM_EMOJI[i]
                        row.append(self._btn(label, s.gid, "c%d" % i))
                    rows.append(row)
                rows.append([self._btn(self.T("b_resign"), s.gid, "end"), self._btn(self.T("b_top"), s.gid, "top")])
            else:
                if s.result in ("X", "O"):
                    lines.append(self.T("ttt_win", name=MARK[s.result] + " " + self._ttt_name(s, s.result)))
                elif s.result == "draw":
                    lines.append(self.T("ttt_draw"))
                elif s.result == "resigned":
                    loser = s.turn
                    winner = "O" if loser == "X" else "X"
                    lines.append(self.T("ttt_resigned", name=self._ttt_name(s, loser), other=self._ttt_name(s, winner)))
                else:
                    lines.append(self.T("stopped_by"))
                rows = [[self._btn(self.T("b_rematch"), s.gid, "new"), self._btn(self.T("b_top"), s.gid, "top")]]
        lines.append("#" + s.gid)
        return "\n".join(lines), rows

    # ----- commands (typed by the plugin user) -----------------------------

    def on_send_message_hook(self, account, params):
        try:
            raw = getattr(params, "message", None)
            if not isinstance(raw, str):
                return HookResult()
            text = raw.strip()
            peer = _to_int(getattr(params, "peer", 0))
            if not peer:
                return HookResult()
            m = CMD_RE.match(text)
            if m:
                self._ensure_watcher(account)
                with self._lock:
                    self._command(account, peer, m.group(1).lower(), (m.group(2) or "").strip(), params)
                return HookResult(strategy=HookStrategy.CANCEL)
            with self._lock:
                if self._host_text(account, peer, text):
                    return HookResult(strategy=HookStrategy.CANCEL)
        except Exception as e:
            import traceback
            log("[MiniGames] send hook: %s\n%s" % (e, traceback.format_exc()))
        return HookResult()

    def _reply_uid(self, params) -> int:
        reply = getattr(params, "replyToMsg", None)
        if reply is None or isinstance(reply, (int, str)):
            return 0
        top = getattr(params, "replyToTopMsg", None)
        try:
            if top is not None and int(reply.getId()) == int(top.getId()):
                return 0          # forum topic root, not a reply to a person
        except Exception:
            pass
        uid = 0
        try:
            uid = int(reply.getSenderId())
        except Exception:
            try:
                uid = int(reply.messageOwner.from_id.user_id)
            except Exception:
                uid = 0
        return uid if uid > 0 else 0

    def _command(self, account: int, dialog: int, kind: str, arg: str, params):
        cmd = "." + kind
        words = arg.lower().split()
        sub = words[0] if words else ""
        me = self._me(account)
        if sub in ("help", "?", "rules", "h"):
            self._say(account, dialog, self.T("help_" + kind))
        elif sub in ("top", "lb", "leaders", "board"):
            self._send_top(account, dialog, kind, all_chats=("all" in words[1:]))
        elif sub in ("me", "stats", "score"):
            self._send_me(account, dialog, kind, me, all_chats=("all" in words[1:]))
        elif sub in ("stop", "end", "cancel", "giveup", "quit"):
            s = self._live((account, dialog, kind))
            if s is None:
                self._say(account, dialog, self.T("nothing", cmd=cmd))
            else:
                self._stop(s)
        else:
            reply_uid = self._reply_uid(params)
            if kind == "wc":
                self._start_wc(account, dialog, me, reply_uid)
            else:
                self._start_ttt(account, dialog, me, reply_uid)

    def _host_text(self, account: int, dialog: int, text: str) -> bool:
        """The plugin user typed a plain guess/move. True = it was a valid game input (swallow it)."""
        me = self._me(account)
        if GUESS_RE.match(text):
            s = self._live((account, dialog, "wc"))
            if s and s.state == "active" and self._wc_allowed(s, me):
                return self._wc_guess(s, me, text)
        if CELL_RE.match(text):
            s = self._live((account, dialog, "ttt"))
            if s and s.state == "active" and self._ttt_turn_uid(s) == me:
                status = self._ttt_move(s, me, int(text) - 1)
                if status == "taken":
                    self._toast(self.T("ttt_taken"))
                return True
        return False

    # ----- incoming messages (friends / group members) ---------------------

    def on_update_hook(self, update_name, account, update):
        try:
            if update_name in ("TL_updateNewMessage", "TL_updateNewChannelMessage"):
                m = getattr(update, "message", None)
                if m is None or bool(getattr(m, "out", False)):
                    return HookResult()
                text = getattr(m, "message", None)
                if not text:
                    return HookResult()
                dialog = self._peer_dialog(getattr(m, "peer_id", None))
                sender = self._sender_of(m, dialog)
                self._incoming(account, dialog, sender, str(text),
                               _to_int(getattr(m, "date", 0)), _to_int(getattr(m, "id", 0)))
        except Exception as e:
            log("[MiniGames] update hook: %s" % e)
        return HookResult()

    def on_updates_hook(self, container_name, account, updates):
        try:
            if bool(getattr(updates, "out", False)):
                return HookResult()
            text = getattr(updates, "message", None)
            if not text:
                return HookResult()
            if container_name == "TL_updateShortMessage":
                uid = _to_int(getattr(updates, "user_id", 0))
                self._incoming(account, uid, uid, str(text),
                               _to_int(getattr(updates, "date", 0)), _to_int(getattr(updates, "id", 0)))
            elif container_name == "TL_updateShortChatMessage":
                chat = _to_int(getattr(updates, "chat_id", 0))
                self._incoming(account, -chat, _to_int(getattr(updates, "from_id", 0)), str(text),
                               _to_int(getattr(updates, "date", 0)), _to_int(getattr(updates, "id", 0)))
        except Exception as e:
            log("[MiniGames] updates hook: %s" % e)
        return HookResult()

    @staticmethod
    def _peer_dialog(peer) -> int:
        try:
            if peer is None:
                return 0
            if hasattr(peer, "channel_id") and peer.channel_id:
                return -_to_int(peer.channel_id)
            if hasattr(peer, "chat_id") and peer.chat_id:
                return -_to_int(peer.chat_id)
            if hasattr(peer, "user_id") and peer.user_id:
                return _to_int(peer.user_id)
        except Exception:
            pass
        return 0

    @staticmethod
    def _sender_of(msg, dialog: int) -> int:
        try:
            frm = getattr(msg, "from_id", None)
            if frm is not None and hasattr(frm, "user_id") and frm.user_id:
                return _to_int(frm.user_id)
        except Exception:
            pass
        return dialog if dialog > 0 else 0

    def _incoming(self, account: int, dialog: int, sender: int, text: str, date: int, msg_id: int):
        if not dialog or sender <= 0:
            return
        text = text.strip()
        if not text or len(text) > 12:
            return                                   # no game input is longer than this
        key = (account, dialog, msg_id)
        with self._lock:
            if msg_id:
                if key in self._seen_set:
                    return
                if len(self._seen) == self._seen.maxlen:
                    self._seen_set.discard(self._seen[0])
                self._seen.append(key)
                self._seen_set.add(key)
            if sender == self._me(account):
                return
            low = text.lower()
            ttt = self._live((account, dialog, "ttt"))
            if ttt is not None and self._fresh(ttt, date):
                if ttt.state == "pending":
                    self._ttt_answer(ttt, sender, low)
                elif ttt.state == "active" and CELL_RE.match(text):
                    if self._ttt_turn_uid(ttt) == sender:
                        status = self._ttt_move(ttt, sender, int(text) - 1)
                        if status == "taken":
                            self._say(account, dialog, self.T("ttt_taken"))
                    return
            wc = self._live((account, dialog, "wc"))
            if (wc is not None and wc.state == "active" and GUESS_RE.match(text)
                    and self._fresh(wc, date) and self._wc_allowed(wc, sender)):
                self._wc_guess(wc, sender, text)

    @staticmethod
    def _fresh(s: Session, date: int) -> bool:
        """Ignore backlog messages that were written before the game started."""
        return not date or date >= int(s.created) - 30

    # ----- .wc -------------------------------------------------------------

    def _start_wc(self, account: int, dialog: int, host: int, reply_uid: int):
        key = (account, dialog, "wc")
        if self._live(key) is not None:
            self._say(account, dialog, self.T("busy", cmd=".wc"))
            return
        old = self._sessions.get(key)
        s = Session("wc", account, dialog, host)
        s.allow_repeat = bool(self.get_setting("wc_repeat", False))
        s.max_attempts = self._int_setting("wc_attempts", 10, 1, 30)
        s.secret = make_secret(s.allow_repeat)
        if dialog > 0 and dialog != host:
            s.target = dialog                         # PM: a duel with the person you are talking to
        elif reply_uid and reply_uid != host:
            s.target = reply_uid                      # group: reply to someone to challenge them
        if old is not None:
            s.board_id = old.board_id                 # old board gets retired when the new one lands
        self._sessions[key] = s
        self._publish(s)

    def _wc_allowed(self, s: Session, uid: int) -> bool:
        if uid <= 0:
            return False
        if s.target:
            return uid in (s.host, s.target)
        return True

    def _wc_reject(self, s: Session, uid: int, text: str):
        if uid == self._me(s.account):
            self._toast(text)
        else:
            self._say(s.account, s.dialog, "%s %s" % (self._name(s.account, uid), text))

    def _wc_guess(self, s: Session, uid: int, text: str) -> bool:
        """Apply one guess. True when the input counted as a game move (even a rejected one)."""
        if s.state != "active":
            return False
        if not valid_guess(text, s.allow_repeat):
            self._wc_reject(s, uid, self.T("wc_bad_repeat"))
            return True
        used = s.attempts.get(uid, 0)
        if used >= s.max_attempts:
            self._wc_reject(s, uid, self.T("wc_no_attempts"))
            return True
        bulls, cows = bulls_cows(s.secret, text)
        s.attempts[uid] = used + 1
        s.guesses.append((uid, text, bulls, cows, used + 1))
        if uid == s.host:
            s.input = ""
        if bulls == 4:
            self._wc_finish(s, "won", uid)
            return True
        players = set(s.attempts)
        if s.target:
            players |= {s.host, s.target}
        if all(s.attempts.get(p, 0) >= s.max_attempts for p in players):
            self._wc_finish(s, "lost", 0)
            return True
        self._publish(s)
        return True

    def _wc_finish(self, s: Session, result: str, winner: int):
        s.state = "done"
        s.result = result
        s.winner = winner
        s.points = wc_points(s.attempts.get(winner, 1)) if result == "won" else 0
        if result in ("won", "lost"):
            entries = []
            for uid in s.attempts:
                if result == "won" and uid == winner:
                    entries.append((uid, self._name(s.account, uid), s.points, "win"))
                else:
                    entries.append((uid, self._name(s.account, uid), 0, "loss"))
            try:
                self._scores.record_many("wc", s.dialog, entries)
            except Exception as e:
                log("[MiniGames] score save: %s" % e)
        self._publish(s)

    def _wc_keypad(self, s: Session, action: str):
        if action == "bk":
            s.input = s.input[:-1]
        elif action == "cl":
            s.input = ""
        else:
            digit = action[1:]
            if not s.allow_repeat and digit in s.input:
                self._toast(self.T("wc_bad_repeat"))
                return
            s.input += digit
        if len(s.input) == 4:
            guess, s.input = s.input, ""
            self._wc_guess(s, s.host, guess)
            return
        buf = " ".join(list(s.input) + ["_"] * (4 - len(s.input)))
        self._toast(self.T("wc_input", buf=buf))

    # ----- .ttt ------------------------------------------------------------

    def _start_ttt(self, account: int, dialog: int, host: int, reply_uid: int):
        key = (account, dialog, "ttt")
        if self._live(key) is not None:
            self._say(account, dialog, self.T("busy", cmd=".ttt"))
            return
        old = self._sessions.get(key)
        s = Session("ttt", account, dialog, host)
        s.x = host
        if dialog == host:                            # Saved Messages: practice against yourself
            s.o = host
            s.state = "active"
        else:
            s.state = "pending"
            if dialog > 0:
                s.target = dialog
            elif reply_uid and reply_uid != host:
                s.target = reply_uid
        if old is not None:
            s.board_id = old.board_id
        self._sessions[key] = s
        self._publish(s)

    def _ttt_answer(self, s: Session, sender: int, low: str):
        """Message from someone else while a challenge is pending."""
        if s.target and sender != s.target:
            return
        if low in ACCEPT_WORDS:
            s.o = sender
            s.state = "active"
            self._publish(s)
        elif low in DECLINE_WORDS:
            s.state = "done"
            s.result = "declined"
            self._say(s.account, s.dialog, self.T("ttt_declined"))
            self._sessions.pop((s.account, s.dialog, "ttt"), None)

    def _ttt_turn_uid(self, s: Session) -> int:
        return s.x if s.turn == "X" else s.o

    def _ttt_move(self, s: Session, uid: int, idx: int) -> str:
        """Returns ok | taken | notturn | over."""
        if s.state != "active":
            return "over"
        if uid != self._ttt_turn_uid(s):
            return "notturn"
        if not 0 <= idx <= 8 or s.cells[idx] != " ":
            return "taken"
        s.cells[idx] = s.turn
        winner = ttt_winner(s.cells)
        if winner:
            self._ttt_finish(s, winner)
        elif " " not in s.cells:
            self._ttt_finish(s, "draw")
        else:
            s.turn = "O" if s.turn == "X" else "X"
            self._publish(s)
        return "ok"

    def _ttt_finish(self, s: Session, result: str):
        s.state = "done"
        s.result = result
        if not s.hotseat and result in ("X", "O", "draw", "resigned"):
            winner_mark = result
            if result == "resigned":
                winner_mark = "O" if s.turn == "X" else "X"
            entries = []
            for mark, uid in (("X", s.x), ("O", s.o)):
                name = self._name(s.account, uid)
                if result == "draw":
                    entries.append((uid, name, 1, "draw"))
                elif mark == winner_mark:
                    entries.append((uid, name, 3, "win"))
                else:
                    entries.append((uid, name, 0, "loss"))
            try:
                self._scores.record_many("ttt", s.dialog, entries)
            except Exception as e:
                log("[MiniGames] score save: %s" % e)
        self._publish(s)

    # ----- stop / rematch --------------------------------------------------

    def _stop(self, s: Session):
        if s.kind == "wc":
            if s.state == "active":
                self._wc_finish(s, "stopped", 0)
        elif s.state == "pending":
            s.state = "done"
            s.result = "cancelled"
            self._say(s.account, s.dialog, self.T("ttt_cancelled"))
            self._sessions.pop((s.account, s.dialog, "ttt"), None)
            if s.board_id:
                self._retire(s.account, s.dialog, s.board_id)
        elif s.state == "active":
            if s.hotseat:
                s.state = "done"
                s.result = "stopped"
                self._publish(s)
            else:
                # whoever's turn it is gives up (the host pressed resign)
                host_mark = "X" if s.x == s.host else "O"
                s.turn = host_mark
                self._ttt_finish(s, "resigned")

    def _rematch(self, s: Session):
        key = (s.account, s.dialog, s.kind)
        if self._live(key) is not None:
            return
        if s.kind == "wc":
            self._start_wc(s.account, s.dialog, s.host, s.target)
        else:
            n = Session("ttt", s.account, s.dialog, s.host)
            n.x, n.o = s.o, s.x                      # swap sides so the other player opens
            n.target = s.target
            n.state = "active"
            n.board_id = s.board_id
            self._sessions[key] = n
            self._publish(n)

    # ----- leaderboards ----------------------------------------------------

    def _game_name(self, kind: str) -> str:
        return self.T("wc_name") if kind == "wc" else "Tic-Tac-Toe" if self._lang() == "en" else "Крестики-нолики"

    def _send_top(self, account: int, dialog: int, kind: str, all_chats: bool):
        scope = "*" if all_chats else str(dialog)
        rows = self._scores.top(kind, scope)
        head = self.T("top_title", game=self._game_name(kind),
                      scope=self.T("scope_all" if all_chats else "scope_chat"))
        if not rows:
            self._say(account, dialog, head + "\n\n" + self.T("top_empty"))
            return
        medals = ["🥇", "🥈", "🥉"]
        lines = [head, ""]
        for i, (uid, r) in enumerate(rows):
            lines.append(self.T("top_row", medal=medals[i] if i < 3 else "%d." % (i + 1),
                                name=r.get("n") or ("User %s" % uid), p=r.get("p", 0),
                                w=r.get("w", 0), l=r.get("l", 0), d=r.get("d", 0)))
        self._say(account, dialog, "\n".join(lines))

    def _send_me(self, account: int, dialog: int, kind: str, uid: int, all_chats: bool):
        scope = "*" if all_chats else str(dialog)
        r = self._scores.get(kind, scope, uid)
        if not r:
            self._say(account, dialog, self.T("me_none"))
            return
        self._say(account, dialog, self.T("me_row", name=self._name(account, uid),
                                          game=self._game_name(kind),
                                          scope=self.T("scope_all" if all_chats else "scope_chat"),
                                          p=r.get("p", 0), w=r.get("w", 0), l=r.get("l", 0),
                                          d=r.get("d", 0), g=r.get("g", 0)))

    # ----- inline button taps ----------------------------------------------

    def on_callback_query_hook(self, account, params):
        try:
            data = getattr(params, "data", None)
            if data is None:
                return HookResult()
            if not isinstance(data, str):
                try:
                    data = bytes(data).decode("utf-8")
                except Exception:
                    data = str(data)
            if not data.startswith(CB + ":"):
                return HookResult()
            try:
                get_messages_controller().callCallbackQuery(params.query_id, "")
            except Exception:
                pass
            dialog = _to_int(getattr(params, "peer", 0))
            msg_id = _to_int(getattr(params, "msg_id", 0))
            with self._lock:
                self._on_tap(account, dialog, msg_id, data)
            return HookResult(strategy=HookStrategy.CANCEL)
        except Exception as e:
            import traceback
            log("[MiniGames] callback hook: %s\n%s" % (e, traceback.format_exc()))
        return HookResult()

    def _on_tap(self, account: int, dialog: int, msg_id: int, data: str):
        parts = data.split(":")
        if len(parts) != 3:
            return
        _, gid, action = parts
        s = None
        for cand in self._sessions.values():
            if cand.account == account and cand.dialog == dialog and cand.gid == gid:
                s = cand
                break
        if s is None or (s.expired() and s.state != "done"):
            self._toast(self.T("cb_gone"))
            if msg_id:
                self._retire(account, dialog, msg_id)
            return
        if s.board_id and msg_id and msg_id != s.board_id:
            self._toast(self.T("cb_stale"))
            return
        if not s.board_id and msg_id:
            s.board_id = msg_id
        me = self._me(account)

        if action == "top":
            self._send_top(account, dialog, s.kind, all_chats=False)
            return
        if action == "new":
            if s.state == "done":
                self._rematch(s)
            return
        if action == "end":
            if s.state != "done":
                self._stop(s)
            return
        if s.state == "done":
            self._toast(self.T("cb_over"))
            return

        if s.kind == "wc":
            if action in ("bk", "cl") or (action.startswith("d") and action[1:].isdigit()):
                if self._wc_allowed(s, me):
                    self._wc_keypad(s, action)
            return

        if s.kind == "ttt" and action.startswith("c") and action[1:].isdigit():
            if s.state == "pending":
                self._toast(self.T("ttt_wait"))
                return
            status = self._ttt_move(s, me, int(action[1:]))
            if status == "taken":
                self._toast(self.T("ttt_taken"))
            elif status == "notturn":
                self._toast(self.T("ttt_not_turn"))

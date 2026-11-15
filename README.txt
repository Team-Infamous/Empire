Empire - new plugins
====================
Copy into your repo (same folder layout as MZGram-Plugins):
  plugins/mini_games/1.0.0/mini_games.plugin     (.wc and .ttt games)
  plugins/empire_admin/1.0.0/empire_admin.plugin (Rose-style admin tools + chat export/import)
Then add the two objects from index_entries.json to the "plugins" array of your index.json.
If you edit a plugin file later, recompute its sha256 and size in the index entry.
tests/ holds offline test scripts: python3 tests/test_empire_admin.py plugins/empire_admin/1.0.0/empire_admin.plugin

Creator
-------
Telegram: @Dillu
GitHub:   https://github.com/Endtrz

# Secrets

SP-Farms stores passwords, access tokens, cookies, API keys, recovery secrets, and network credentials in the operating system keyring. On Windows, `keyring` uses Windows Credential Manager. SQLite stores only a random vault reference and non-sensitive metadata: type, owner, identity, and lifecycle timestamps.

Normal metadata exports never resolve vault references. Diagnostics and logging apply sensitive-value redaction, but callers must still avoid submitting secret objects as log fields.

Secret transfer is an explicit operator action. Each exported value is protected with AES-256-GCM; its key is derived from an operator-provided passphrase using scrypt and a random salt. Archives contain only version, salt, nonce, and ciphertext. Passphrases are never stored. Import fails when authentication or the passphrase is invalid.

Temporary clipboard reveal defaults to 30 seconds. It clears only when the clipboard still contains the revealed value, preventing deletion of content the operator copied afterward. GUI implementations must schedule clearing on the Qt thread.

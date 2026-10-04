#!/usr/bin/env python3
"""sign_update.py <key json> <update.dmg>
Prints the Sparkle <enclosure> attributes for a Mac update: sparkle:edSignature (ed25519 over the file bytes,
verified by the app against SUPublicEDKey in Info.plist) and length.
The key json (SUPublicEDKey + private_seed_b64) stays on Xrero's PC - never commit it, never upload it."""
import base64, json, os, sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization as s

key = json.load(open(sys.argv[1], encoding="utf-8"))
k = Ed25519PrivateKey.from_private_bytes(base64.b64decode(key["private_seed_b64"]))
pub = base64.b64encode(k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)).decode()
if pub != key["SUPublicEDKey"]:
    raise SystemExit("key file is inconsistent")
data = open(sys.argv[2], "rb").read()
sig = base64.b64encode(k.sign(data)).decode()
print('sparkle:edSignature="%s" length="%d"' % (sig, os.path.getsize(sys.argv[2])))
